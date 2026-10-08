"""#210, prima parte: l'intervista dai dispositivi veri, un nome per ciascuno.

Tre cose da fissare: i dispositivi vengono da Home Assistant e non dal modello,
un nome entra negli alias solo dopo il «si'», e l'`entity_id` che si salva e'
sempre quello vero, qualunque cosa scriva chi risponde.
"""

import pytest

import shinra.services.interview_engine as modulo
from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_alias import (
    LIMITE_DISPOSITIVI,
    alias_proposto,
    dispositivi_senza_nome,
    passo_alias,
)
from shinra.services.intervista_passi import INTERVIEW_STEPS

VUOTA = {"profili": [], "stanze": [], "fatti": []}


@pytest.fixture()
def archivio(tmp_path) -> DataStore:
    importazione.crea_vuoto(tmp_path / "shinra.db")
    yield DataStore()


def _stato(entity_id: str, nome: str = "", stato: str = "off") -> dict:
    return {"entity_id": entity_id, "state": stato, "attributes": {"friendly_name": nome or entity_id}}


# ------------------------------------------- i dispositivi da nominare


@pytest.mark.asyncio
async def test_si_chiedono_solo_dispositivi_veri_e_senza_nome(archivio, monkeypatch) -> None:
    archivio.salva_alias({"alias": "salotto", "entity_id": "light.salotto", "room": "", "domain": "light"})
    stati = [
        _stato("light.salotto", "Luce salotto"),  # ha gia' un alias
        _stato("light.cucina", "Luce cucina"),
        _stato("sensor.temperatura", "Temperatura"),  # non si chiama per nome
        _stato("switch.presa", "Presa", stato="unavailable"),  # non risponde
        _stato("cover.tapparella", "Tapparella"),
    ]

    async def letti():
        return stati

    monkeypatch.setattr("shinra.skills.entita.stati_noti", letti)
    monkeypatch.setattr("shinra.infra.data_store.data_store", archivio)

    ids = [d["entity_id"] for d in await dispositivi_senza_nome()]

    assert ids == ["light.cucina", "cover.tapparella"]


@pytest.mark.asyncio
async def test_non_se_ne_chiedono_piu_del_limite(archivio, monkeypatch) -> None:
    stati = [_stato(f"light.l{n:02d}", f"Luce {n:02d}") for n in range(40)]

    async def letti():
        return stati

    monkeypatch.setattr("shinra.skills.entita.stati_noti", letti)
    monkeypatch.setattr("shinra.infra.data_store.data_store", archivio)

    assert len(await dispositivi_senza_nome()) == LIMITE_DISPOSITIVI


@pytest.mark.asyncio
async def test_con_home_assistant_spento_non_si_chiede_niente(archivio, monkeypatch) -> None:
    async def guasto():
        raise ConnectionError("Home Assistant non risponde")

    monkeypatch.setattr("shinra.skills.entita.stati_noti", guasto)
    monkeypatch.setattr("shinra.infra.data_store.data_store", archivio)

    assert await dispositivi_senza_nome() == []


# ------------------------------------------------- il nome scritto


@pytest.mark.parametrize(
    "scritto, atteso",
    [
        ("  la luce del corridoio  ", "la luce del corridoio"),
        ("«lampada»", "lampada"),
        ("Luce Acquario.", "Luce Acquario"),
        ("a", None),
        ("", None),
        ("quando mi siedo sul divano accendo quella lampada la sera tardi", None),
        ("x" * 80, None),
    ],
)
def test_un_nome_e_breve_e_ripulito(scritto, atteso) -> None:
    assert alias_proposto(scritto) == atteso


# --------------------------------------------- dentro l'intervista


def _motore(archivio, monkeypatch, dispositivi) -> tuple:
    monkeypatch.setattr(modulo, "data_store", archivio)
    monkeypatch.setattr(modulo, "dati_della_casa", lambda _store: VUOTA)
    motore = LearningInterviewEngine()
    motore.start_session("prova", dispositivi)
    sessione = motore.get_session("prova")
    # Si salta alle domande sui dispositivi: le altre le prova test_intervista_una_domanda.
    sessione["current_step_index"] = len(INTERVIEW_STEPS)
    return motore, sessione


CUCINA = {"entity_id": "light.cucina", "friendly_name": "Luce cucina"}
PRESA = {"entity_id": "switch.sonoff_100053af52", "friendly_name": "Sonoff 100053af52"}


def test_i_dispositivi_diventano_passi_dopo_le_domande_fisse(archivio, monkeypatch) -> None:
    _, sessione = _motore(archivio, monkeypatch, [CUCINA, PRESA])

    assert len(sessione["passi"]) == len(INTERVIEW_STEPS) + 2
    primo = sessione["passi"][len(INTERVIEW_STEPS)]
    assert primo["kind"] == "alias"
    assert primo["entity_id"] == "light.cucina"
    assert primo["question"].count("?") == 1


@pytest.mark.asyncio
async def test_un_si_salva_il_nome_sull_entita_vera(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch, [CUCINA])

    chiesta = await motore.process_answer("prova", "la luce della cucina")
    assert chiesta["fase"] == "conferma"
    assert archivio.get_aliases() == [], "ha salvato prima del si'"

    esito = await motore.process_answer("prova", "sì")

    alias = archivio.get_aliases()
    assert [(a["alias"], a["entity_id"], a["domain"]) for a in alias] == [
        ("la luce della cucina", "light.cucina", "light")
    ]
    assert "la luce della cucina" in esito["message"]
    assert esito["is_complete"] is True
    assert "Ho dato un nome a 1 dispositivo" in esito["message"]


@pytest.mark.asyncio
async def test_il_modello_non_puo_inventare_un_dispositivo(archivio, monkeypatch) -> None:
    """Chi risponde scrive un nome, mai un `entity_id`: anche se scrive «light.finta»
    quella e' una parte del nome, e l'entita' resta quella del passo."""
    motore, _ = _motore(archivio, monkeypatch, [CUCINA])

    await motore.process_answer("prova", "light.finta")
    await motore.process_answer("prova", "sì")

    assert [a["entity_id"] for a in archivio.get_aliases()] == ["light.cucina"]


@pytest.mark.asyncio
async def test_un_no_non_salva_niente_e_si_passa_oltre(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch, [CUCINA, PRESA])

    await motore.process_answer("prova", "lampada")
    esito = await motore.process_answer("prova", "no")

    assert archivio.get_aliases() == [], "un alias rifiutato e' entrato nel database"
    assert esito["step"]["entity_id"] == PRESA["entity_id"], "non e' passato al dispositivo dopo"


@pytest.mark.asyncio
async def test_salta_lascia_il_dispositivo_com_e(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch, [CUCINA])

    esito = await motore.process_answer("prova", "salta")

    assert archivio.get_aliases() == []
    assert esito["is_complete"] is True
    assert "Ho dato un nome" not in esito["message"]


@pytest.mark.asyncio
async def test_un_nome_gia_usato_da_un_altro_dispositivo_si_rifiuta(archivio, monkeypatch) -> None:
    archivio.salva_alias({"alias": "Lampada", "entity_id": "light.salotto", "room": "", "domain": "light"})
    motore, _ = _motore(archivio, monkeypatch, [CUCINA])

    esito = await motore.process_answer("prova", "lampada")

    assert esito["fase"] == "domanda", "ha chiesto conferma per un nome gia' preso"
    assert "light.salotto" in esito["message"]
    assert len(archivio.get_aliases()) == 1


@pytest.mark.asyncio
async def test_una_frase_non_e_un_nome_e_si_insiste_una_volta_sola(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch, [CUCINA, PRESA])
    frase = "quando mi siedo sul divano accendo quella lampada la sera tardi"

    primo = await motore.process_answer("prova", frase)
    secondo = await motore.process_answer("prova", frase)

    assert primo["step"]["entity_id"] == CUCINA["entity_id"], "non ha insistito"
    assert secondo["step"]["entity_id"] == PRESA["entity_id"], "ha insistito una seconda volta"
    assert archivio.get_aliases() == []


@pytest.mark.asyncio
async def test_una_correzione_sola_poi_si_lascia_com_e(archivio, monkeypatch) -> None:
    motore, _ = _motore(archivio, monkeypatch, [CUCINA, PRESA])

    await motore.process_answer("prova", "lampada")
    await motore.process_answer("prova", "luce cucina")  # correzione: ancora in conferma
    esito = await motore.process_answer("prova", "luce della cucina grande")  # oltre il limite

    assert archivio.get_aliases() == []
    assert esito["step"]["entity_id"] == PRESA["entity_id"]


def test_il_passo_alias_non_porta_mai_il_nome_scelto_dal_modello() -> None:
    """L'`entity_id` del passo e' quello che ha scritto Home Assistant."""
    passo = passo_alias({"entity_id": "cover.tapparella", "friendly_name": "Tapparella"})
    assert passo["entity_id"] == "cover.tapparella"
    assert passo["dominio"] == "cover"
