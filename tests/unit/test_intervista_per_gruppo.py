"""Una conferma per gruppo di domande (provato in casa, 2026-10-11: «poco fluida»).

Dopo ogni risposta l'intervista mostrava «Ho capito questo, e' giusto?»: tredici domande, ventisei turni. Adesso le
risposte di uno stesso argomento si raccolgono senza salvare niente, e alla fine del gruppo si mostra un riepilogo unico.
**Niente entra nel database senza il «si'»**: e' la ragione per cui la conferma esiste (#170), e qui si prova che resta.
"""

import pytest

import shinra.services.interview_engine as modulo
from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_gruppo import numero_da_togliere
from shinra.services.intervista_passi import INTERVIEW_STEPS

VUOTA = {"profili": [], "stanze": [], "fatti": []}


@pytest.fixture()
def archivio(tmp_path) -> DataStore:
    importazione.crea_vuoto(tmp_path / "shinra.db")
    yield DataStore()


def _motore(archivio, monkeypatch, dispositivi=None, lingua=""):
    monkeypatch.setattr(modulo, "data_store", archivio)
    monkeypatch.setattr(modulo, "dati_della_casa", lambda _store: VUOTA)
    motore = LearningInterviewEngine()
    numero = []

    async def modello(prompt, system="", temperature=0.1):
        numero.append(1)
        return {"facts": [{"text": f"Fatto numero {len(numero)}"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    motore.start_session("prova", dispositivi, lingua=lingua)
    return motore


async def _rispondi_al_gruppo_casa(motore) -> dict:
    """Le tre domande del gruppo «casa»: l'ultima risposta porta al riepilogo."""
    prima = await motore.process_answer("prova", "Arezzo")
    seconda = await motore.process_answer("prova", "Secondo piano")
    terza = await motore.process_answer("prova", "Salotto e cucina")
    return {"prima": prima, "seconda": seconda, "terza": terza}


def _voci(archivio):
    return [f["text"] for f in archivio.get_knowledge()]


# ----------------------------------------------------------- raccogliere


@pytest.mark.asyncio
async def test_le_risposte_di_un_gruppo_non_chiedono_conferma_una_per_una(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    esiti = await _rispondi_al_gruppo_casa(motore)

    assert esiti["prima"]["fase"] == "domanda" and esiti["seconda"]["fase"] == "domanda"
    assert esiti["prima"]["step"]["id"] == "casa_piano" and esiti["seconda"]["step"]["id"] == "casa_stanze"
    assert "Ti mostro tutto alla fine" in esiti["prima"]["message"]
    assert "Ti mostro tutto" not in esiti["seconda"]["message"], "l'avviso va detto una volta per gruppo"
    assert esiti["terza"]["fase"] == "conferma"


@pytest.mark.asyncio
async def test_niente_si_salva_prima_del_si(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)
    assert _voci(archivio) == [], "una risposta e' entrata nel database prima della conferma"


@pytest.mark.asyncio
async def test_il_riepilogo_elenca_tutte_le_voci_numerate(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    esiti = await _rispondi_al_gruppo_casa(motore)

    messaggio = esiti["terza"]["message"]
    assert (
        "1. Fatto numero 1" in messaggio
        and "2. Fatto numero 2" in messaggio
        and "3. Fatto numero 3" in messaggio
    )
    assert len(esiti["terza"]["capiti"]) == 3


@pytest.mark.asyncio
async def test_un_si_salva_tutto_il_gruppo_e_si_passa_al_successivo(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)

    esito = await motore.process_answer("prova", "sì")

    assert _voci(archivio) == ["Fatto numero 1", "Fatto numero 2", "Fatto numero 3"]
    assert esito["step"]["id"] == "casa_altri_luoghi"
    assert esito["fase"] == "domanda"


@pytest.mark.asyncio
async def test_un_no_scarta_tutto_il_gruppo(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)

    esito = await motore.process_answer("prova", "no")

    assert _voci(archivio) == []
    assert esito["message"].startswith("Va bene, non salvo niente di questa parte.")
    assert esito["step"]["id"] == "casa_altri_luoghi"


@pytest.mark.asyncio
async def test_togli_due_toglie_la_seconda_voce_e_rimostra_il_riepilogo(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)

    rimostrato = await motore.process_answer("prova", "togli 2")

    assert rimostrato["fase"] == "conferma"
    assert "Tolto: «Fatto numero 2»." in rimostrato["message"]
    assert "1. Fatto numero 1" in rimostrato["message"] and "2. Fatto numero 3" in rimostrato["message"]
    assert _voci(archivio) == [], "ha salvato togliendo"

    await motore.process_answer("prova", "sì")
    assert _voci(archivio) == ["Fatto numero 1", "Fatto numero 3"]


@pytest.mark.asyncio
async def test_togliere_l_ultima_voce_rimasta_scarta_il_gruppo(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)
    await motore.process_answer("prova", "togli 1")
    await motore.process_answer("prova", "togli 1")
    esito = await motore.process_answer("prova", "togli 1")

    assert _voci(archivio) == []
    assert esito["step"]["id"] == "casa_altri_luoghi", "e' rimasto fermo sul riepilogo vuoto"


@pytest.mark.asyncio
async def test_un_numero_che_non_c_e_non_toglie_niente(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)

    esito = await motore.process_answer("prova", "togli 9")

    assert esito["fase"] == "conferma"
    assert "1. Fatto numero 1" in esito["message"] and "3. Fatto numero 3" in esito["message"]


@pytest.mark.asyncio
async def test_riscrivere_l_ultima_risposta_sostituisce_solo_quella(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)

    rimostrato = await motore.process_answer("prova", "Salotto, cucina e studio")

    assert rimostrato["fase"] == "conferma"
    assert "1. Fatto numero 1" in rimostrato["message"] and "2. Fatto numero 2" in rimostrato["message"]
    assert "3. Fatto numero 4" in rimostrato["message"], "l'ultima voce non e' stata riletta"
    assert "Fatto numero 3" not in rimostrato["message"]


@pytest.mark.asyncio
async def test_una_sola_riscrittura_poi_si_salva_com_e(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch)
    await _rispondi_al_gruppo_casa(motore)
    await motore.process_answer("prova", "Una prima riscrittura")  # ancora in conferma
    esito = await motore.process_answer("prova", "Una seconda riscrittura")  # oltre il limite

    assert len(_voci(archivio)) == 3, "non ha salvato, e chi risponde resta fermo all'infinito"
    assert esito["step"]["id"] == "casa_altri_luoghi"


# ------------------------------------------------------- l'intervista intera


@pytest.mark.asyncio
async def test_l_intervista_intera_ha_una_conferma_per_gruppo_non_una_per_risposta(
    archivio, monkeypatch
) -> None:
    motore = _motore(archivio, monkeypatch)
    turni = conferme = 0
    esito = {"is_complete": False}
    while not esito["is_complete"]:
        esito = await motore.process_answer(
            "prova", "sì" if esito.get("fase") == "conferma" else "Una risposta valida"
        )
        turni += 1
        conferme += esito.get("fase") == "conferma"

    assert (
        conferme == 5
    ), f"i gruppi sono cinque (casa, luoghi, famiglia, abitudini, dati tecnici): {conferme}"
    assert turni == len(INTERVIEW_STEPS) + 5, f"{turni} turni invece di {2 * len(INTERVIEW_STEPS)}"
    assert len(_voci(archivio)) == len(INTERVIEW_STEPS)


@pytest.mark.asyncio
async def test_un_nome_di_dispositivo_chiude_il_gruppo_prima(archivio, monkeypatch) -> None:
    """Un nome si conferma da solo: il riepilogo del gruppo precedente si mostra prima di cominciare i nomi."""
    cucina = {"entity_id": "light.cucina", "friendly_name": "Luce cucina"}
    motore = _motore(archivio, monkeypatch, dispositivi=[cucina])
    sessione = motore.get_session("prova")
    sessione["current_step_index"] = [p["id"] for p in sessione["passi"]].index("tecnico_wifi")

    await motore.process_answer("prova", "CasaMia_Guest")
    await motore.process_answer("prova", "Nel sottoscala")
    riepilogo = await motore.process_answer("prova", "L'idraulico e' Rossi")
    assert riepilogo["fase"] == "conferma" and riepilogo["step"]["id"] == "tecnico_contatto"

    dopo = await motore.process_answer("prova", "sì")
    assert dopo["step"]["kind"] == "alias"


@pytest.mark.asyncio
async def test_una_risposta_non_interpretata_in_fondo_al_gruppo_mostra_comunque_il_riepilogo(
    archivio, monkeypatch
) -> None:
    motore = _motore(archivio, monkeypatch)
    sessione = motore.get_session("prova")
    sessione["current_step_index"] = [p["id"] for p in sessione["passi"]].index("casa_piano")
    await motore.process_answer("prova", "Secondo piano")  # raccolta, in attesa

    async def spento(prompt, system="", temperature=0.1):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", spento)
    await motore.process_answer("prova", "Salotto")  # insiste una volta
    esito = await motore.process_answer(
        "prova", "Salotto e cucina"
    )  # il modello non interpreta: si salva grezza

    assert esito["fase"] == "conferma", "le voci in attesa sono rimaste senza riepilogo"
    assert "Fatto numero 1" in esito["message"]
    assert len(esito["new_facts"]) == 1, "la risposta non interpretata va salvata e detta"


# ----------------------------------------------------------- in inglese


@pytest.mark.asyncio
async def test_il_gruppo_in_inglese_si_conferma_e_si_toglie_in_inglese(archivio, monkeypatch) -> None:
    motore = _motore(archivio, monkeypatch, lingua="en")
    esiti = await _rispondi_al_gruppo_casa(motore)
    assert "I'll show you everything at the end of this part." in esiti["prima"]["message"]
    assert "Here is what I understood:" in esiti["terza"]["message"]

    tolto = await motore.process_answer("prova", "remove 1")
    assert "Removed: «Fatto numero 1»." in tolto["message"]
    await motore.process_answer("prova", "yes")
    assert _voci(archivio) == ["Fatto numero 2", "Fatto numero 3"]


# ---------------------------------------------------------- l'opzione


@pytest.mark.asyncio
async def test_con_conferma_per_risposta_si_torna_a_una_per_una(archivio, monkeypatch) -> None:
    from shinra.config import settings as impostazioni

    monkeypatch.setattr(impostazioni.settings.assistant, "intervista_conferma", "risposta")
    motore = _motore(archivio, monkeypatch)

    prima = await motore.process_answer("prova", "Arezzo")

    assert prima["fase"] == "conferma", "con `risposta` si conferma subito"


# --------------------------------------------------------- «togli N»


@pytest.mark.parametrize(
    "testo, atteso",
    [
        ("togli 2", 2),
        ("Togli 3.", 3),
        ("no 1", 1),
        ("rimuovi n. 4", 4),
        ("elimina #2", 2),
        ("togli", None),
        ("togli due", None),
        ("no", None),
        ("salvo 2", None),
    ],
)
def test_numero_da_togliere(testo, atteso) -> None:
    assert numero_da_togliere(testo, "it") == atteso


def test_remove_in_inglese() -> None:
    assert numero_da_togliere("remove 2", "en") == 2
    assert numero_da_togliere("take out 1", "en") == 1
    assert numero_da_togliere("togli 2", "en") is None
