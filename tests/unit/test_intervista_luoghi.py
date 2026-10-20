"""L'intervista e i luoghi (#345): la citta' detta diventa il luogo principale, e si chiede degli altri luoghi.

La citta' non e' una frase in piu': registra il luogo «Casa» (il centro della citta', con la precisione dichiarata di 5 km),
**solo se non ce n'e' gia' uno**, e dice a chi risponde che la posizione precisa va rifatta dal telefono. Un guasto della
geocodifica non deve fermare l'intervista.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from shinra.infra.data_store import DataStore
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import interview_engine as modulo
from shinra.services import luoghi, registro
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_noto import cosa_si_sa
from shinra.services.intervista_passi import passi_per

GEOCODIFICA = "https://geocoding-api.open-meteo.com/v1/search"
AREZZO = {"results": [{"name": "Arezzo", "latitude": 43.4631, "longitude": 11.8781, "country": "Italia"}]}


@pytest.fixture(autouse=True)
def pulito():
    deposito.sostituisci_tutto([])
    yield
    deposito.sostituisci_tutto([])


def _motore(monkeypatch, lingua: str = ""):
    archivio = DataStore()
    monkeypatch.setattr(modulo, "data_store", archivio)
    monkeypatch.setattr(
        modulo,
        "dati_della_casa",
        lambda _s: {"profili": [], "stanze": [], "fatti": [], "luoghi": [], "luogo_principale": ""},
    )
    motore = LearningInterviewEngine()

    async def modello(prompt, system="", temperature=0.1):
        return {"facts": [{"text": "La casa si trova ad Arezzo"}]}

    monkeypatch.setattr(motore.ollama, "genera_json", modello)
    motore.start_session("prova", lingua=lingua)
    return motore


async def _rispondi_alla_citta(motore, risposta="Vivo ad Arezzo"):
    """Le tre domande del gruppo casa, poi la conferma: e' qui che il fatto si salva."""
    await motore.process_answer("prova", risposta)
    await motore.process_answer("prova", "Secondo piano")
    await motore.process_answer("prova", "Salotto e cucina")
    return await motore.process_answer("prova", "si")


@respx.mock
async def test_la_citta_detta_diventa_il_luogo_principale(monkeypatch):
    respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json=AREZZO))
    esito = await _rispondi_alla_citta(_motore(monkeypatch))

    (casa,) = luoghi.elenco()
    assert casa["nome"] == "Casa" and casa["principale"] and casa["origine"] == "intervista"
    assert casa["precisione_m"] == 5000 and casa["citta"] == "Arezzo"
    assert (
        "Casa" in esito["message"] and "non la tua casa" in esito["message"]
    ), "non dice che e' il centro della citta'"


@respx.mock
async def test_al_servizio_esterno_va_solo_il_nome_della_citta(monkeypatch):
    rotta = respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json=AREZZO))
    await _rispondi_alla_citta(_motore(monkeypatch), "Arezzo")
    richiesta = rotta.calls[0].request
    assert richiesta.url.params["name"] == "Arezzo"
    assert set(richiesta.url.params) == {
        "name",
        "count",
        "language",
        "format",
    }, "al servizio vanno solo il nome e le opzioni"


@respx.mock
async def test_non_sovrascrive_un_luogo_principale_gia_registrato(monkeypatch):
    luoghi.registra({"nome": "Casa", "latitudine": 45.1, "longitudine": 9.1, "origine": "telefono"})
    rotta = respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json=AREZZO))
    await _rispondi_alla_citta(_motore(monkeypatch))
    (casa,) = luoghi.elenco()
    assert casa["origine"] == "telefono" and casa["latitudine"] == 45.1, "ha sovrascritto la posizione vera"
    assert not rotta.called, "non doveva nemmeno chiedere al servizio esterno"


@respx.mock
async def test_un_guasto_della_geocodifica_non_ferma_l_intervista(monkeypatch):
    respx.get(GEOCODIFICA).mock(side_effect=httpx.ConnectError("giu'"))
    esito = await _rispondi_alla_citta(_motore(monkeypatch))
    assert luoghi.elenco() == []
    assert esito["step"]["id"] == "casa_altri_luoghi", "l'intervista deve proseguire"
    assert "Ho registrato" not in esito["message"]


@respx.mock
async def test_una_citta_sconosciuta_non_registra_niente(monkeypatch):
    respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json={}))
    await _rispondi_alla_citta(_motore(monkeypatch), "Vivo a Qwertyuiop")
    assert luoghi.elenco() == []


@respx.mock
async def test_in_inglese_la_frase_e_in_inglese(monkeypatch):
    respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json=AREZZO))
    motore = _motore(monkeypatch, "en")
    await motore.process_answer("prova", "I live in Arezzo")
    await motore.process_answer("prova", "Second floor")
    await motore.process_answer("prova", "Living room and kitchen")
    esito = await motore.process_answer("prova", "yes")
    assert "main place" in esito["message"] and "city centre" in esito["message"]


@respx.mock
async def test_il_registro_dice_che_e_stato_registrato_non_dove(monkeypatch):
    respx.get(GEOCODIFICA).mock(return_value=httpx.Response(200, json=AREZZO))
    await _rispondi_alla_citta(_motore(monkeypatch))
    voci = [v for v in registro.voci(limite=10) if v["azione"] == "luogo.registrato"]
    assert voci and voci[0]["dettagli"]["origine"] == "intervista"
    assert "43.46" not in str(voci[0]) and "Arezzo" not in str(voci[0])


# ------------------------------------------------------------------ le domande


def test_l_intervista_chiede_degli_altri_luoghi_e_propone_di_registrarli_da_dove_si_e():
    passo = next(p for p in passi_per("it") if p["id"] == "casa_altri_luoghi")
    assert "altre abitazioni" in passo["question"] and passo["question"].count("?") == 1
    assert "Luoghi" in passo["hint"], "il suggerimento deve dire dove registrarli"
    inglese = next(p for p in passi_per("en") if p["id"] == "casa_altri_luoghi")
    assert "Places" in inglese["hint"]


def test_se_la_casa_conosce_gia_la_citta_non_la_richiede():
    passo = next(p for p in passi_per("it") if p["id"] == "casa_citta")
    dati = {"fatti": [], "luogo_principale": "Casa"}
    assert cosa_si_sa(passo, dati) == "So gia' dove si trova la casa: Casa"
    assert cosa_si_sa(passo, {"fatti": [], "luogo_principale": ""}) is None


def test_gli_altri_luoghi_si_saltano_solo_se_ce_ne_sono_piu_di_uno():
    passo = next(p for p in passi_per("it") if p["id"] == "casa_altri_luoghi")
    assert cosa_si_sa(passo, {"fatti": [], "luoghi": ["Casa"]}) is None
    assert "Casa e Casa al mare" in (
        cosa_si_sa(passo, {"fatti": [], "luoghi": ["Casa", "Casa al mare"]}) or ""
    )


async def test_un_errore_imprevisto_nel_registrare_il_luogo_non_ferma_l_intervista(monkeypatch):
    async def rotto(*a, **k):
        raise RuntimeError("database in manutenzione")

    monkeypatch.setattr(luoghi, "registra_dalla_citta", rotto)
    esito = await _rispondi_alla_citta(_motore(monkeypatch))
    assert esito["step"]["id"] == "casa_altri_luoghi" and "Ho registrato" not in esito["message"]
