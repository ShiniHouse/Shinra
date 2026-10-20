"""#210: un'abitudine detta a parole diventa una routine letta dal CODICE, non indovinata dal modello.

Il caso della scheda: «la sera chiudo le tapparelle e accendo la luce del corridoio» deve diventare una routine che la prova a secco
percorre fino in fondo. Sul server, con il modello da 3 miliardi di parametri, quella frase (e altre simili) diventava dei fatti
(«le serrature siano chiuse») e mai una routine.
"""

from __future__ import annotations

import pytest

import shinra.services.interview_engine as modulo
from shinra.domain.abitudine import routine_dalla_frase
from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.infra.lingue import schemi
from shinra.services import intervista_routine as ir
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_comune import sezione

ENTITA = {
    "light.corridoio": "Luce corridoio",
    "light.cucina": "Luce cucina",
    "light.salotto": "Luce salotto",
    "cover.salotto": "Tapparella salotto",
    "cover.camera": "Tapparella camera",
    "lock.ingresso": "Serratura ingresso",
    "climate.soggiorno": "Termostato",
}
ALIAS = [{"alias": "la luce lunga", "entity_id": "light.corridoio"}]
FRASE = "la sera chiudo le tapparelle e accendo la luce del corridoio"


def leggi(frase, entita=ENTITA, alias=ALIAS, lingua="it"):
    return routine_dalla_frase(frase, entita, alias, sezione(lingua)["abitudine"], "Sera")


def azioni(r):
    return [(a["entity_id"], a["action"]) for a in (r or {}).get("actions", [])]


# ------------------------------------------------------------------ il parser


def test_il_caso_della_scheda_due_tapparelle_e_una_luce():
    r = leggi(FRASE)
    assert azioni(r) == [
        ("cover.salotto", "close_cover"),
        ("cover.camera", "close_cover"),
        ("light.corridoio", "turn_on"),
    ]
    assert r["name"] == "Sera"


def test_un_alias_vale_come_un_nome():
    assert azioni(leggi("accendo la luce lunga")) == [("light.corridoio", "turn_on")]


def test_il_verbo_si_eredita_dalla_parte_prima():
    r = leggi("accendo la luce del corridoio e della cucina")
    assert azioni(r) == [("light.corridoio", "turn_on"), ("light.cucina", "turn_on")]


def test_spegnere_e_aprire():
    assert azioni(leggi("spengo la luce della cucina, poi apro le tapparelle")) == [
        ("light.cucina", "turn_off"),
        ("cover.salotto", "open_cover"),
        ("cover.camera", "open_cover"),
    ]


def test_un_oggetto_ambiguo_non_si_indovina():
    """«la luce» con tre luci in casa non ne accende una a caso, e non le accende tutte."""
    r = leggi("accendo la luce")
    assert azioni(r) == [("luce", "turn_on")], "deve restare un riferimento ignoto, che il controllo scarta"


def test_il_plurale_vale_piu_dispositivi():
    r = leggi("spengo tutte le luci")
    assert {e for e, _ in azioni(r)} == {"light.corridoio", "light.cucina", "light.salotto"}


def test_il_verbo_decide_il_tipo_di_dispositivo():
    assert azioni(leggi("chiudo la luce della cucina")) == [("luce cucina", "close_cover")]
    assert azioni(leggi("accendo la tapparella del salotto")) == [("tapparella salotto", "turn_on")]


def test_cio_che_non_c_e_in_casa_resta_un_riferimento_ignoto():
    r = leggi("accendo il forno")
    assert azioni(r) == [("forno", "turn_on")]


@pytest.mark.parametrize(
    "frase",
    [
        "",
        "mi sveglio alle sette",
        "guardiamo un film",
        "la sera facciamo colazione",
        "accendo",
        "la luce del corridoio",
    ],
)
def test_senza_un_verbo_con_un_oggetto_non_c_e_nessuna_routine(frase):
    assert leggi(frase) is None


def test_non_ripete_la_stessa_azione():
    assert azioni(leggi("accendo la luce del corridoio e accendo la luce del corridoio")) == [
        ("light.corridoio", "turn_on")
    ]


def test_in_inglese_funziona_con_le_sue_parole():
    entita = {"light.hall": "Hall light", "cover.living": "Living room blind"}
    r = leggi("in the evening close the blind and turn the hall light on", entita, [], "en")
    assert azioni(r) == [("cover.living", "close_cover"), ("light.hall", "turn_on")]


# ------------------------------------------------------------------ dal parser alla routine proposta


@pytest.fixture()
def archivio(tmp_path, monkeypatch) -> DataStore:
    importazione.crea_vuoto(tmp_path / "shinra.db")

    async def leggi_casa(_archivio):
        return ENTITA, ALIAS

    monkeypatch.setattr(ir, "leggi_la_casa", leggi_casa)
    yield DataStore()


async def test_la_frase_della_scheda_diventa_una_routine_che_la_prova_a_secco_percorre(archivio):
    r = await ir.routine_dalla_risposta(FRASE, archivio, "Sera")
    assert r is not None, "la frase della scheda non e' diventata una routine"
    assert [a["entity_id"] for a in r["actions"]] == ["cover.salotto", "cover.camera", "light.corridoio"]
    assert "prova" in r and r["anteprima"], "serve l'anteprima e l'esito della prova a secco"


async def test_una_serratura_non_entra_nemmeno_se_nominata(archivio):
    r = await ir.routine_dalla_risposta(
        "la sera chiudo le tapparelle e apro la serratura ingresso", archivio, "Sera"
    )
    assert [a["entity_id"] for a in r["actions"]] == ["cover.salotto", "cover.camera"]


async def test_solo_cose_delicate_o_ignote_non_producono_una_proposta(archivio):
    assert await ir.routine_dalla_risposta("accendo il forno", archivio, "Sera") is None
    assert await ir.routine_dalla_risposta("mi sveglio alle sette", archivio, "Sera") is None


async def test_con_home_assistant_spento_non_si_propone_niente(monkeypatch, archivio):
    async def guasto(_archivio):
        raise ConnectionError("Home Assistant non risponde")

    monkeypatch.setattr(ir, "leggi_la_casa", guasto)
    assert await ir.routine_dalla_risposta(FRASE, archivio, "Sera") is None


# ------------------------------------------------------------------ nell'intervista


def _passo(id_):
    return next(p for p in modulo.passi_per("it") if p["id"] == id_)


async def test_nell_intervista_il_codice_propone_la_routine_anche_senza_modello(archivio, monkeypatch):
    """Il modello non risponde: la risposta resta un fatto, e l'abitudine diventa comunque una routine."""
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def senza_modello(*a, **k):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", senza_modello)
    estratto = await motore._extract_knowledge_and_routines(_passo("notte_cosa"), FRASE, "")
    assert estratto["interpretato"] is False and estratto["facts"]
    assert [a["entity_id"] for a in estratto["proposed_routine"]["actions"]][-1] == "light.corridoio"


async def test_se_il_modello_non_propone_niente_di_valido_la_legge_il_codice(archivio, monkeypatch):
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def modello_pasticcione(*a, **k):
        return {
            "facts": [{"text": "Le serrature siano chiuse", "category": "abitudini"}],
            "proposed_routine": None,
        }

    monkeypatch.setattr(motore.ollama, "genera_json", modello_pasticcione)
    estratto = await motore._extract_knowledge_and_routines(_passo("notte_cosa"), FRASE, "")
    assert estratto["proposed_routine"] is not None


async def test_il_codice_non_legge_abitudini_nelle_domande_che_non_lo_sono(archivio, monkeypatch):
    """Solo i passi delle abitudini: «ho una casa al mare e accendo la luce» in un passo sulla casa non diventa una routine."""
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()

    async def senza_modello(*a, **k):
        return None

    monkeypatch.setattr(motore.ollama, "genera_json", senza_modello)
    estratto = await motore._extract_knowledge_and_routines(_passo("casa_piano"), FRASE, "")
    assert estratto["proposed_routine"] is None


def test_le_parole_dell_abitudine_stanno_in_ogni_lingua():
    for lingua in ("it", "en"):
        lessico = sezione(lingua)["abitudine"]
        assert lessico["verbi"] and lessico["separatori"] and lessico["vuote"] and lessico["plurali"], lingua
    assert schemi("it").lingua == "it"
