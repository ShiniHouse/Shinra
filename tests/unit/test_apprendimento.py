"""La Modalita' Apprendimento deve arrivare in fondo.

Era la funzione piu' recente del progetto e non aveva mai completato un passo:
`interview_engine` chiamava due metodi inesistenti — `add_knowledge_item` su
DataStore e `generate` su OllamaClient. Il primo produceva un 500 a ogni
risposta; il secondo, catturato, faceva cadere sempre nel ripiego, rendendo
codice morto il prompt di estrazione.
"""

from __future__ import annotations

import pytest

from core.data_store import DataStore
from core.interview_engine import INTERVIEW_STEPS, LearningInterviewEngine
from core.ollama_client import OllamaClient


@pytest.fixture()
def archivio(tmp_path, monkeypatch) -> DataStore:
    """Un DataStore isolato: i test non toccano la conoscenza vera della casa."""
    import core.data_store as modulo

    monkeypatch.setattr(modulo, "DATA_DIR", tmp_path)
    monkeypatch.setattr(modulo, "EXAMPLES_DIR", tmp_path / "examples")
    monkeypatch.setattr(modulo, "KNOWLEDGE_FILE", tmp_path / "knowledge.json")
    (tmp_path / "knowledge.json").write_text("[]", encoding="utf-8")
    return DataStore()


# ------------------------------------------------------------------- BLK-01


def test_aggiunge_un_fatto(archivio: DataStore) -> None:
    salvato = archivio.add_knowledge_item("La sveglia nei feriali e' alle 7:00", "abitudini")
    assert salvato["text"] == "La sveglia nei feriali e' alle 7:00"
    assert salvato["category"] == "abitudini"
    assert salvato["enabled"] is True
    assert salvato["id"]
    assert archivio.get_knowledge() == [salvato]


def test_non_duplica_un_fatto_gia_presente(archivio: DataStore) -> None:
    """Durante un'intervista capita di ripetersi, e ogni fatto finisce nel
    prompt di sistema: i doppioni si pagano a ogni risposta."""
    primo = archivio.add_knowledge_item("Il contatore e' nel sottoscala")
    secondo = archivio.add_knowledge_item("  il contatore E' NEL SOTTOSCALA  ")
    assert primo["id"] == secondo["id"]
    assert len(archivio.get_knowledge()) == 1


def test_gli_identificativi_restano_unici_dopo_una_cancellazione(archivio: DataStore) -> None:
    """Con identificativi basati sul conteggio, cancellare un fatto e
    aggiungerne un altro produce un identificativo gia' usato: modificare il
    nuovo sovrascriverebbe un fatto diverso."""
    a = archivio.add_knowledge_item("Primo fatto")
    b = archivio.add_knowledge_item("Secondo fatto")
    archivio.save_knowledge([f for f in archivio.get_knowledge() if f["id"] != a["id"]])
    c = archivio.add_knowledge_item("Terzo fatto")
    assert len({a["id"], b["id"], c["id"]}) == 3


def test_un_fatto_vuoto_viene_rifiutato(archivio: DataStore) -> None:
    with pytest.raises(ValueError):
        archivio.add_knowledge_item("   ")


# ------------------------------------------------------------------- BLK-02


@pytest.mark.asyncio
async def test_estrae_i_fatti_dalla_risposta(monkeypatch) -> None:
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {
            "facts": [
                {"text": "La sveglia nei feriali e' alle 7:00", "category": "abitudini"},
                {"text": "Al risveglio si accende la luce in cucina", "category": "abitudini"},
            ],
            "proposed_routine": {
                "name": "Buongiorno",
                "trigger_phrases": ["buongiorno"],
                "actions": [{"type": "ha_device", "entity_id": "light.cucina", "action": "turn_on"}],
            },
        }

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    esito = await motore._extract_knowledge_and_routines(INTERVIEW_STEPS[2], "Mi sveglio alle 7")

    assert len(esito["facts"]) == 2
    assert esito["proposed_routine"]["name"] == "Buongiorno"


@pytest.mark.asyncio
async def test_con_ollama_spento_la_risposta_non_va_persa(monkeypatch) -> None:
    """Meglio conservare la frase dell'utente non elaborata che perderla."""
    motore = LearningInterviewEngine()

    async def spento(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", spento)
    esito = await motore._extract_knowledge_and_routines(INTERVIEW_STEPS[0], "Vivo ad Arezzo")
    assert esito["facts"][0]["text"] == "Vivo ad Arezzo"
    assert esito["proposed_routine"] is None


@pytest.mark.parametrize(
    "grezzi",
    [None, "non una lista", [None, 123], [{"text": "  "}], [{"senza": "testo"}], [""]],
)
def test_scarta_i_fatti_inutilizzabili(grezzi) -> None:
    """Un modello piccolo restituisce spesso stringhe o campi vuoti: senza
    filtro finirebbero nella conoscenza e da li' nel prompt di ogni risposta."""
    assert LearningInterviewEngine._fatti_validi(grezzi, INTERVIEW_STEPS[0]) == []


def test_accetta_i_fatti_scritti_come_stringhe() -> None:
    fatti = LearningInterviewEngine._fatti_validi(["Vivo ad Arezzo"], INTERVIEW_STEPS[0])
    assert fatti == [{"text": "Vivo ad Arezzo", "category": INTERVIEW_STEPS[0]["category"]}]


@pytest.mark.parametrize("grezza", [None, "testo", {}, {"name": "  "}, {"actions": []}])
def test_scarta_le_routine_senza_nome(grezza) -> None:
    assert LearningInterviewEngine._routine_valida(grezza) is None


def test_una_routine_senza_azioni_resta_proponibile() -> None:
    """Il nome basta: le azioni si scelgono nell'editor prima di confermarla."""
    r = LearningInterviewEngine._routine_valida({"name": "Cinema"})
    assert r["name"] == "Cinema"
    assert r["actions"] == []


# --------------------------------------------------- l'intervista per intero


@pytest.mark.asyncio
async def test_l_intervista_arriva_in_fondo(archivio: DataStore, monkeypatch) -> None:
    """La prova che non era mai riuscita: sei passi, nessun errore.

    Prima di questa correzione la prima risposta sollevava AttributeError e
    l'utente vedeva un 500.
    """
    import core.interview_engine as modulo

    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": f"Fatto dal passo {len(archivio.get_knowledge())}"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)

    avvio = motore.start_session("prova")
    assert avvio["is_active"] and avvio["step_index"] == 0

    for _ in INTERVIEW_STEPS:
        esito = await motore.process_answer("prova", "Una risposta abbastanza lunga da valere.")
        assert "message" in esito

    assert esito["is_complete"] is True
    assert len(archivio.get_knowledge()) == len(INTERVIEW_STEPS)
    assert not motore.is_session_active("prova")


@pytest.mark.asyncio
async def test_un_fatto_non_salvabile_non_ferma_l_intervista(archivio, monkeypatch) -> None:
    """Era esattamente il difetto BLK-01: l'errore arrivava all'utente come 500."""
    import core.interview_engine as modulo

    def rifiuta(*a, **k):
        raise OSError("disco pieno")

    monkeypatch.setattr(archivio, "add_knowledge_item", rifiuta)
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": "Un fatto qualsiasi"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    motore.start_session("prova")
    esito = await motore.process_answer("prova", "Una risposta valida.")
    assert esito["is_active"] is True


# ------------------------------------------------- il JSON che torna davvero


@pytest.mark.asyncio
async def test_json_avvolto_in_un_blocco_di_codice(monkeypatch) -> None:
    """Anche con format=json alcuni modelli aggiungono l'involucro markdown."""
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": True, "content": '```json\n{"facts": []}\n```'}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") == {"facts": []}


@pytest.mark.asyncio
async def test_json_preceduto_da_una_frase(monkeypatch) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {
            "success": True,
            "content": 'Ecco il risultato: {"facts": [{"text": "ciao"}]} spero vada bene',
        }

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") == {"facts": [{"text": "ciao"}]}


@pytest.mark.parametrize("contenuto", ["", "non json affatto", "[1, 2, 3]", "{rotto", "null"])
@pytest.mark.asyncio
async def test_risposte_inutilizzabili_danno_none(monkeypatch, contenuto: str) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": True, "content": contenuto}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") is None


@pytest.mark.asyncio
async def test_ollama_irraggiungibile_da_none(monkeypatch) -> None:
    client = OllamaClient()

    async def risposta(messages, tools=None, temperature=None, formato=None):
        return {"success": False, "error": "connessione rifiutata"}

    monkeypatch.setattr(client, "chat", risposta)
    assert await client.genera_json("x") is None
