"""#207, prima parte: l'intervista si svolge per intero nella lingua di chi risponde.

Le domande, i riepiloghi, i saluti, i rifiuti, i nomi dei dispositivi e le routine erano frasi italiane scritte nel
codice: una persona inglese le riceveva cosi' com'erano. Qui un'intervista inglese si percorre dall'inizio alla fine
e si cerca l'italiano in tutto cio' che viene restituito.
"""

import re

import pytest

import shinra.services.interview_engine as modulo
from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.infra.lingue import schemi
from shinra.services import intervista_routine as ir
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_passi import INTERVIEW_STEPS, STRUTTURA, passi_per

VUOTA = {"profili": [], "stanze": [], "fatti": []}

# Parole che in un'intervista inglese non devono comparire: sono le frasi italiane del codice di prima.
ITALIANO = re.compile(
    r"\b(Rispondi|Ho capito|Ho letto|Ricevuto|Intervista|giusto|tua casa|salto la domanda|Per esempio|"
    r"Modalità|Va bene|Salvo|Fatto:|lascio|dispositiv[oi]|Vuoi che|Prova a secco|Ho scartato|domanda|tua|il tuo)\b",
    re.IGNORECASE,
)


@pytest.fixture()
def archivio(tmp_path) -> DataStore:
    importazione.crea_vuoto(tmp_path / "shinra.db")
    yield DataStore()


def _motore(archivio, monkeypatch, fatto="Something to remember") -> tuple:
    monkeypatch.setattr(modulo, "data_store", archivio)
    monkeypatch.setattr(modulo, "dati_della_casa", lambda _store: VUOTA)
    motore = LearningInterviewEngine()
    visti = []

    async def modello(prompt, system="", temperature=0.1):
        visti.append((prompt, system))
        # Un fatto diverso a ogni chiamata: il database non salva due volte lo stesso.
        return {"facts": [{"text": f"{fatto} {len(visti)}"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    return motore, visti


def _testo_visibile(esito: dict) -> str:
    """Tutto quello che una persona legge in una risposta dell'intervista."""
    pezzi = [esito.get("message", ""), esito.get("suggerimento") or ""]
    passo = esito.get("step") or {}
    pezzi += [passo.get("title", ""), passo.get("question", ""), passo.get("hint", "")]
    pezzi += [f["text"] for f in esito.get("capiti", [])]
    return "\n".join(str(p) for p in pezzi)


# ------------------------------------------------ l'intervista per intero


@pytest.mark.asyncio
async def test_un_profilo_inglese_fa_tutta_l_intervista_in_inglese(archivio, monkeypatch) -> None:
    motore, visti = _motore(archivio, monkeypatch)
    avvio = motore.start_session("john", lingua="en")
    letto = [_testo_visibile(avvio)]
    assert avvio["step"]["question"] == "In which city or area is your home?"

    while True:
        risposta = await motore.process_answer("john", "Something I want to say here")
        letto.append(_testo_visibile(risposta))
        if risposta["is_complete"]:
            break
        conferma = await motore.process_answer("john", "yes")
        letto.append(_testo_visibile(conferma))
        if conferma["is_complete"]:
            risposta = conferma
            break

    assert risposta["is_complete"] is True
    assert "Interview complete" in risposta["message"]
    italiano = [t for t in letto if ITALIANO.search(t)]
    assert italiano == [], f"frasi italiane in un'intervista inglese: {italiano[:2]}"
    assert len(archivio.get_knowledge()) == len(INTERVIEW_STEPS)
    assert visti, "il modello non e' stato interrogato"


@pytest.mark.asyncio
async def test_il_prompt_per_il_modello_e_in_inglese(archivio, monkeypatch) -> None:
    motore, visti = _motore(archivio, monkeypatch)
    motore.start_session("john", lingua="en")

    await motore.process_answer("john", "I live in Arezzo")

    prompt, sistema = visti[0]
    assert prompt.startswith("You are the AI assistant Shinra")
    assert "Sei l'assistente" not in prompt
    assert sistema.startswith("Answer only with valid JSON")


@pytest.mark.asyncio
async def test_un_profilo_italiano_resta_in_italiano(archivio, monkeypatch) -> None:
    motore, visti = _motore(archivio, monkeypatch, fatto="Una cosa da ricordare")
    avvio = motore.start_session("sonia", lingua="it")
    assert avvio["step"]["question"] == "In quale città o zona si trova la tua casa?"
    assert "Modalità Apprendimento attivata" in avvio["message"]

    await motore.process_answer("sonia", "Vivo ad Arezzo")
    assert visti[0][0].startswith("Sei l'assistente IA Shinra")


@pytest.mark.asyncio
async def test_il_si_di_un_profilo_inglese_e_yes_non_si(archivio, monkeypatch) -> None:
    """Ogni lingua capisce le sue parole: in inglese «sì» e' una correzione, non una conferma."""
    motore, _ = _motore(archivio, monkeypatch)
    motore.start_session("john", lingua="en")
    chiesta = await motore.process_answer("john", "I live in Arezzo")
    assert chiesta["fase"] == "conferma"

    corretta = await motore.process_answer("john", "sì")

    assert archivio.get_knowledge() == [] or corretta["fase"] == "conferma", "un «sì» italiano ha confermato"


@pytest.mark.asyncio
async def test_no_in_inglese_non_salva_e_lo_dice_in_inglese(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch)
    motore.start_session("john", lingua="en")
    await motore.process_answer("john", "I live in Arezzo")

    esito = await motore.process_answer("john", "no")

    assert archivio.get_knowledge() == []
    assert esito["message"].startswith("All right, I won't save anything")


@pytest.mark.asyncio
async def test_una_risposta_povera_insiste_in_inglese_una_volta(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch)
    monkeypatch.setattr(motore.ollama, "genera_json", _vuoto)
    motore.start_session("john", lingua="en")

    primo = await motore.process_answer("john", "not sure")

    assert "I'll try once more, then move on." in primo["message"]
    assert "For example: «I live in Arezzo.»" in primo["message"]


async def _vuoto(prompt, system="", temperature=0.1):
    return {"facts": []}


# ----------------------------------------------------- cosa la casa sa gia'


def test_i_salti_si_dicono_in_inglese(archivio, monkeypatch) -> None:
    dati = {"profili": ["Alessio", "Sonia"], "stanze": ["kitchen", "lounge"], "fatti": []}
    monkeypatch.setattr(modulo, "data_store", archivio)
    monkeypatch.setattr(modulo, "dati_della_casa", lambda _store: dati)
    motore = LearningInterviewEngine()

    avvio = motore.start_session("john", lingua="en")
    sessione = motore.get_session("john")
    sessione["current_step_index"] = [p["id"] for p in sessione["passi"]].index("casa_piano")
    avanti = motore._avanza(sessione, "", [], None, True)

    assert avvio["step"]["id"] == "casa_citta"
    assert "I already know these rooms: kitchen and lounge: I'll skip the question." in avanti["message"]
    assert "The house already has Alessio and Sonia: I'll skip the question." in avanti["message"]


# ------------------------------------------- i nomi dei dispositivi e le routine

CUCINA = {"entity_id": "light.cucina", "friendly_name": "Kitchen light"}


@pytest.mark.asyncio
async def test_i_dispositivi_si_chiedono_in_inglese(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch)
    motore.start_session("john", [CUCINA], lingua="en")
    motore.get_session("john")["current_step_index"] = len(INTERVIEW_STEPS)
    passo = motore.get_session("john")["passi"][len(INTERVIEW_STEPS)]
    assert passo["question"] == "What do you call «Kitchen light» (light) at home?"

    chiesta = await motore.process_answer("john", "the big light")
    assert chiesta["message"] == "You'll call it «the big light». Is that right?"
    fatto = await motore.process_answer("john", "yes")

    assert [a["alias"] for a in archivio.get_aliases()] == ["the big light"]
    assert "Done: from now on «the big light» is this device." in fatto["message"]
    assert "I gave a name to 1 device" in fatto["message"]
    assert not ITALIANO.search(_testo_visibile(fatto))


@pytest.mark.asyncio
async def test_skip_in_inglese_e_salta_in_italiano(archivio, monkeypatch) -> None:
    for lingua, parola in (("en", "skip"), ("it", "salta")):
        motore, _ = _motore(archivio, monkeypatch)
        motore.start_session("u", [CUCINA], lingua=lingua)
        motore.get_session("u")["current_step_index"] = len(INTERVIEW_STEPS)
        esito = await motore.process_answer("u", parola)
        assert archivio.get_aliases() == []
        assert esito["is_complete"] is True

    motore, _ = _motore(archivio, monkeypatch)
    motore.start_session("u", [CUCINA], lingua="en")
    motore.get_session("u")["current_step_index"] = len(INTERVIEW_STEPS)
    esito = await motore.process_answer("u", "salta")
    assert esito["fase"] == "conferma", "«salta» ha saltato in inglese"


ENTITA = {"light.corridoio": "Hallway light", "lock.ingresso": "Front door lock"}


@pytest.mark.asyncio
async def test_una_routine_proposta_si_descrive_in_inglese(archivio, monkeypatch) -> None:
    async def casa(_archivio):
        return ENTITA, []

    monkeypatch.setattr(ir, "leggi_la_casa", casa)
    grezza = {
        "name": "Good night",
        "actions": [
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_off"},
            {"type": "delay", "seconds": 30},
            {"type": "ha_device", "entity_id": "lock.ingresso", "action": "unlock"},
            {"type": "tts", "message": "Good night"},
        ],
    }

    proposta = await ir.controlla_proposta(grezza, archivio, "en")

    assert proposta["anteprima"].splitlines() == [
        "1. turns off «Hallway light»",
        "2. waits 30 seconds",
        "3. says: «Good night»",
    ]
    assert proposta["prova"] == "3 steps, tried without touching the house"
    assert proposta["scartate"] == ["«Front door lock»: I can't do «unlock»"]
    assert not ITALIANO.search(proposta["anteprima"] + proposta["prova"] + " ".join(proposta["scartate"]))


@pytest.mark.asyncio
async def test_la_proposta_di_routine_nel_messaggio_e_in_inglese(archivio, monkeypatch) -> None:
    async def casa(_archivio):
        return ENTITA, []

    monkeypatch.setattr(ir, "leggi_la_casa", casa)
    motore, _ = _motore(archivio, monkeypatch)
    motore.start_session("john", lingua="en")
    proposta = await ir.controlla_proposta(
        {
            "name": "Hallway",
            "actions": [{"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"}],
        },
        archivio,
        "en",
    )

    esito = motore._avanza(motore.get_session("john"), "", [], proposta, True)

    assert "I noticed a possible routine, «Hallway»:" in esito["message"]
    assert (
        "Dry run: 1 steps, tried without touching the house." in esito["message"]
        or "Dry run:" in esito["message"]
    )
    assert "Shall I create it?" in esito["message"]
    assert not ITALIANO.search(esito["message"])


# ------------------------------------------------------- la struttura


def test_le_due_lingue_hanno_gli_stessi_passi() -> None:
    ids = [i for i, _, _ in STRUTTURA]
    for lingua in ("it", "en"):
        assert sorted(schemi(lingua).intervista["passi"]) == sorted(ids), f"{lingua}: i passi non coincidono"
        assert [p["id"] for p in passi_per(lingua)] == ids


def test_ogni_passo_inglese_ha_una_sola_domanda() -> None:
    sbagliati = [p["id"] for p in passi_per("en") if p["question"].count("?") != 1]
    assert sbagliati == [], f"passi inglesi con piu' (o meno) di una domanda: {sbagliati}"


def test_lo_stesso_passo_ha_gli_stessi_saltati_in_entrambe_le_lingue() -> None:
    """Le parole del «gia' noto» cambiano da lingua a lingua, ma i passi che le hanno sono gli stessi."""
    con_parole = {lingua: {p["id"] for p in passi_per(lingua) if p.get("parole")} for lingua in ("it", "en")}
    assert con_parole["it"] == con_parole["en"]
