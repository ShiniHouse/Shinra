"""#210, seconda parte: una routine detta a parole, controllata contro la casa vera.

Il modello inventa dispositivi e azioni. Qui si fissa che nessuna di queste cose
arriva alla persona, nessuna si salva, e che la prova a secco non tocca la casa.
"""

import pytest

import shinra.services.interview_engine as modulo
from shinra.infra.data_store import DataStore
from shinra.infra.db import importazione
from shinra.services import intervista_routine as ir
from shinra.services.interview_engine import LearningInterviewEngine
from shinra.services.intervista_routine import (
    controlla_proposta,
    controlla_routine,
    descrivi,
    prova_a_secco,
    routine_come_grafo,
    routine_da_salvare,
)

ENTITA = {
    "light.corridoio": "Luce corridoio",
    "cover.salotto": "Tapparella salotto",
    "lock.ingresso": "Serratura ingresso",
    "cover.garage": "Porta del garage",
    "climate.soggiorno": "Termostato",
}
ALIAS = [{"alias": "la luce lunga", "entity_id": "light.corridoio"}]


@pytest.fixture()
def archivio(tmp_path) -> DataStore:
    importazione.crea_vuoto(tmp_path / "shinra.db")
    yield DataStore()


def _routine(*azioni) -> dict:
    return {"name": "Buonasera", "trigger_phrases": ["buonasera"], "actions": list(azioni)}


def _casa(monkeypatch, guasto=False) -> None:
    async def leggi(_archivio):
        if guasto:
            raise ConnectionError("Home Assistant non risponde")
        return ENTITA, ALIAS

    monkeypatch.setattr(ir, "leggi_la_casa", leggi)


# ------------------------------------------------ i filtri sul modello


def test_un_dispositivo_inventato_si_scarta_e_si_dice() -> None:
    routine, scartate = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
            {"type": "ha_device", "entity_id": "light.finta", "action": "turn_on"},
        ),
        ENTITA,
        ALIAS,
    )
    assert [a["entity_id"] for a in routine["actions"]] == ["light.corridoio"]
    assert any("light.finta" in s for s in scartate)


def test_un_alias_si_risolve_nell_entita_vera() -> None:
    routine, _ = controlla_routine(
        _routine({"type": "ha_device", "entity_id": "La Luce Lunga", "action": "turn_off"}), ENTITA, ALIAS
    )
    assert routine["actions"][0]["entity_id"] == "light.corridoio"


def test_un_alias_che_punta_a_un_dispositivo_che_non_c_e_piu_non_vale() -> None:
    alias = [{"alias": "fantasma", "entity_id": "light.sparita"}]
    routine, scartate = controlla_routine(
        _routine({"type": "ha_device", "entity_id": "fantasma", "action": "turn_on"}), ENTITA, alias
    )
    assert routine is None and scartate


def test_una_serratura_non_entra_in_una_routine() -> None:
    routine, scartate = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "lock.ingresso", "action": "turn_on"},
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
        ),
        ENTITA,
        ALIAS,
    )
    assert [a["entity_id"] for a in routine["actions"]] == ["light.corridoio"]
    assert any("delicata" in s for s in scartate)


def test_un_garage_si_scarta_anche_se_e_una_cover() -> None:
    """Una `cover` ammessa non basta: quella che apre una porta e' delicata.

    La serratura la ferma gia' il dominio; il garage no, ed e' per lui che c'e'
    il controllo sulla sensibilita'.
    """
    routine, scartate = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "cover.garage", "action": "open_cover"},
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
        ),
        ENTITA,
        ALIAS,
    )
    assert [a["entity_id"] for a in routine["actions"]] == ["cover.salotto"]
    assert any("garage" in s.lower() for s in scartate)


def test_un_comando_che_non_esiste_si_scarta() -> None:
    routine, scartate = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "explode"},
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
        ),
        ENTITA,
        ALIAS,
    )
    assert [a["action"] for a in routine["actions"]] == ["close_cover"]
    assert any("explode" in s for s in scartate)


def test_i_valori_fuori_dai_limiti_non_passano() -> None:
    routine, _ = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on", "brightness": 500},
            {"type": "ha_device", "entity_id": "climate.soggiorno", "action": "turn_on", "temperature": 90},
            {"type": "delay", "seconds": 999999},
            {"type": "delay", "seconds": 30},
            {"type": "tts", "message": "x" * 500},
            {"type": "tts", "message": "Buonanotte"},
            {"type": "reboot"},
        ),
        ENTITA,
        ALIAS,
    )
    tipi = [a["type"] for a in routine["actions"]]
    assert tipi == ["ha_device", "ha_device", "delay", "tts"]
    assert "brightness" not in routine["actions"][0]
    assert "temperature" not in routine["actions"][1]
    assert routine["actions"][2]["seconds"] == 30


def test_senza_azioni_sui_dispositivi_non_c_e_una_routine() -> None:
    """Una pausa o un annuncio da soli non sono un'abitudine."""
    routine, _ = controlla_routine(_routine({"type": "delay", "seconds": 5}), ENTITA, ALIAS)
    assert routine is None


# ------------------------------------------- grafo, prova a secco, testo


def test_il_grafo_ha_un_innesco_e_le_azioni_in_fila() -> None:
    routine, _ = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
            {"type": "delay", "seconds": 10},
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on", "brightness": 40},
        ),
        ENTITA,
        ALIAS,
    )
    nodi, archi = routine_come_grafo(routine)
    assert [n["type"] for n in nodi] == ["trigger", "ha_device", "delay", "ha_device"]
    assert [(a["from"], a["to"]) for a in archi] == [("n0", "n1"), ("n1", "n2"), ("n2", "n3")]


@pytest.mark.asyncio
async def test_la_prova_a_secco_percorre_tutta_la_routine(monkeypatch) -> None:
    chiamate = []

    async def servizio(*a, **k):  # se qualcuno chiamasse Home Assistant, si vedrebbe
        chiamate.append(a)

    monkeypatch.setattr("shinra.infra.homeassistant.client.HomeAssistantClient.call_service", servizio)
    routine, _ = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
        ),
        ENTITA,
        ALIAS,
    )
    ok, esito = await prova_a_secco(routine)
    assert ok, esito
    assert "2 passi" in esito
    assert chiamate == [], "la prova a secco ha toccato la casa"


def test_il_testo_dice_cosa_farebbe_con_i_nomi_veri() -> None:
    routine, _ = controlla_routine(
        _routine(
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on", "brightness": 40},
            {"type": "tts", "message": "Buonanotte"},
        ),
        ENTITA,
        ALIAS,
    )
    assert descrivi(routine, ENTITA).splitlines() == [
        "1. chiude «Tapparella salotto»",
        "2. accende «Luce corridoio» al 40%",
        "3. dice: «Buonanotte»",
    ]


# ------------------------------------------------------ dentro l'intervista


@pytest.mark.asyncio
async def test_con_home_assistant_spento_non_si_propone_niente(archivio, monkeypatch) -> None:
    _casa(monkeypatch, guasto=True)
    grezza = _routine({"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"})
    assert await controlla_proposta(grezza, archivio) is None


@pytest.mark.asyncio
async def test_una_proposta_buona_porta_anteprima_e_prova(archivio, monkeypatch) -> None:
    _casa(monkeypatch)
    grezza = _routine({"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"})
    proposta = await controlla_proposta(grezza, archivio)
    assert proposta["anteprima"] == "1. accende «Luce corridoio»"
    assert "provati senza toccare la casa" in proposta["prova"]


@pytest.mark.asyncio
async def test_il_messaggio_mostra_i_passi_prima_di_salvare(archivio, monkeypatch) -> None:
    _casa(monkeypatch)
    monkeypatch.setattr(modulo, "data_store", archivio)
    motore = LearningInterviewEngine()
    motore.start_session("prova")
    proposta = await controlla_proposta(
        _routine(
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
            {"type": "ha_device", "entity_id": "light.finta", "action": "turn_on"},
        ),
        archivio,
    )
    sessione = motore.get_session("prova")
    sessione["current_step_index"] = 0

    esito = motore._avanza(sessione, "", [], proposta, True)

    assert "1. accende «Luce corridoio»" in esito["message"]
    assert "Prova a secco" in esito["message"]
    assert "light.finta" in esito["message"], "non dice cosa ha scartato"
    assert archivio.get_modes() == [], "ha salvato prima della conferma"


# ---------------------------------------------------------- il salvataggio


@pytest.mark.asyncio
async def test_si_salva_il_grafo_ricontrollato_non_quello_arrivato(archivio, monkeypatch) -> None:
    """La proposta torna dal browser: un dispositivo aggiunto strada facendo non passa."""
    _casa(monkeypatch)
    monkeypatch.setattr(modulo, "data_store", archivio)
    manomessa = _routine(
        {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
        {"type": "ha_device", "entity_id": "light.finta", "action": "turn_on"},
    )
    manomessa.update(anteprima="1. accende tutto", prova="ok", scartate=[])

    esito = await LearningInterviewEngine().conferma_routine_proposta(manomessa)

    assert esito["success"] is True
    salvata = archivio.get_modes()[0]
    ids = [n["data"].get("entity_id") for n in salvata["nodes"] if n["type"] == "ha_device"]
    assert ids == ["light.corridoio"]
    assert salvata["actions"] == []
    assert "anteprima" not in salvata


@pytest.mark.asyncio
async def test_una_proposta_senza_dispositivi_veri_non_si_salva(archivio, monkeypatch) -> None:
    _casa(monkeypatch)
    monkeypatch.setattr(modulo, "data_store", archivio)
    finta = _routine({"type": "ha_device", "entity_id": "light.finta", "action": "turn_on"})

    esito = await LearningInterviewEngine().conferma_routine_proposta(finta)

    assert esito["success"] is False
    assert archivio.get_modes() == [], "una routine con un dispositivo inventato e' entrata nel database"


@pytest.mark.asyncio
async def test_il_grafo_salvato_regge_la_validazione_dell_editor(archivio, monkeypatch) -> None:
    from shinra.domain import grafo

    _casa(monkeypatch)
    pulita = await routine_da_salvare(
        _routine(
            {"type": "ha_device", "entity_id": "cover.salotto", "action": "close_cover"},
            {"type": "ha_device", "entity_id": "light.corridoio", "action": "turn_on"},
        ),
        archivio,
    )
    assert grafo.valida(pulita["nodes"], pulita["edges"]) == []
