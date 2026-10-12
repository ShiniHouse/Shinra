"""#207: gli strumenti dicono il loro esito nella lingua di chi ha chiesto.

Due profili, uno italiano e uno inglese, comandano **la stessa serratura**: ciascuno riceve il messaggio di esito nella
propria lingua. La lingua viaggia nel contesto della richiesta, come l'attore e il canale, e gli strumenti la leggono
senza che nessuno gliela passi.
"""

from __future__ import annotations

import pytest

from shinra.domain import contesto
from shinra.infra.db import depositi
from shinra.infra.lingue import lingue_disponibili, schemi
from shinra.services import registro
from shinra.services.agent import ShinraAgent
from shinra.services.user_manager import UserProfile
from shinra.skills import domini_casa

STATI = [
    {
        "entity_id": "lock.porta_ingresso",
        "state": "locked",
        "attributes": {"friendly_name": "Porta d'ingresso"},
    },
    {"entity_id": "media_player.salotto", "state": "playing", "attributes": {"friendly_name": "TV salotto"}},
    {"entity_id": "vacuum.robot", "state": "docked", "attributes": {"friendly_name": "Robottino"}},
    {"entity_id": "fan.camera", "state": "off", "attributes": {"friendly_name": "Ventilatore camera"}},
]


@pytest.fixture
def casa(monkeypatch):
    """Home Assistant che annota invece di eseguire: una serratura chiusa."""

    class FintoClient:
        async def call_service(self, dominio, servizio, dati=None):
            return {"success": True}

        async def stati_correnti(self):
            return list(STATI)

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "porta d'ingresso", "entity_id": "lock.porta_ingresso"}]
    )
    yield


@pytest.fixture
def da_web():
    """Il contesto di una richiesta che arriva dalla dashboard."""
    registro.apri_contesto(attore="alessio", canale="web")
    yield


@pytest.fixture(autouse=True)
def lingua_pulita():
    contesto.dichiara_lingua("")
    yield
    contesto.dichiara_lingua("")


@pytest.mark.asyncio
async def test_la_stessa_serratura_risponde_a_ciascuno_nella_sua_lingua(casa, da_web) -> None:
    contesto.dichiara_lingua("it")
    it = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")
    contesto.dichiara_lingua("en")
    en = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")

    assert it["message"] == "Porta d'ingresso chiusa."
    assert en["message"] == "Porta d'ingresso locked."
    assert it["success"] is en["success"] is True


@pytest.mark.asyncio
async def test_lo_stato_si_dice_nella_lingua_giusta(casa, da_web) -> None:
    contesto.dichiara_lingua("en")
    en = await domini_casa.comanda_serratura("lock.porta_ingresso", "stato")
    contesto.dichiara_lingua("it")
    it = await domini_casa.comanda_serratura("lock.porta_ingresso", "stato")

    assert en["message"] == "Porta d'ingresso is locked."
    assert it["message"] == "Porta d'ingresso e' chiusa."


@pytest.mark.asyncio
async def test_un_errore_di_azione_si_dice_nella_lingua_giusta(casa, da_web) -> None:
    contesto.dichiara_lingua("en")
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "esplodi")
    assert esito["error"] == "Action «esplodi» is not supported for a lock."


@pytest.mark.asyncio
async def test_senza_lingua_nel_contesto_si_segue_l_installazione(casa, da_web) -> None:
    contesto.dichiara_lingua("")
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")
    assert esito["message"] == "Porta d'ingresso chiusa."


@pytest.mark.asyncio
async def test_la_lingua_di_una_richiesta_non_resta_alla_successiva(casa, da_web) -> None:
    """Dichiarare vuoto azzera: la richiesta dopo non parla la lingua di quella prima."""
    contesto.dichiara_lingua("en")
    contesto.dichiara_lingua("")
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")
    assert esito["message"].endswith("chiusa.")


def test_ogni_lingua_ha_le_frasi_della_serratura() -> None:
    for lingua in lingue_disponibili():
        s = schemi(lingua)
        for chiave in (
            "serratura_chiusa",
            "serratura_aperta",
            "serratura_non_chiusa",
            "serratura_non_aperta",
        ):
            assert "{nome}" in s.messaggi[chiave], f"{lingua}: {chiave}"
        assert "{azione}" in s.messaggi["serratura_azione_ignota"]
        assert {s.messaggi[f"serratura_stato_{k}"] for k in ("locked", "unlocked", "jammed")}


# ----------------------------- la lingua arriva dal profilo, nel percorso dell'agente


@pytest.mark.asyncio
async def test_l_agente_dichiara_la_lingua_del_profilo(monkeypatch) -> None:
    """Chi parla in inglese mette la sua lingua nel contesto prima che gli strumenti lavorino."""
    from shinra.services.intenti import Risposta

    visti = []

    async def intento_finto(richiesta):
        visti.append(contesto.lingua_corrente())
        return Risposta("ok")

    monkeypatch.setattr("shinra.services.agent.instrada", intento_finto)
    agente = ShinraAgent()

    await agente.process_user_input("ciao", user_profile=UserProfile(id="john", name="John", lingua="en"))
    await agente.process_user_input("ciao", user_profile=UserProfile(id="sonia", name="Sonia", lingua=""))

    assert visti == [
        "en",
        "",
    ], "la lingua del profilo non e' arrivata nel contesto, o e' rimasta alla richiesta dopo"


# ------------------------------------------- lettore multimediale, aspirapolvere, ventilatore


async def _dice(lingua, funzione, *args, **kwargs):
    contesto.dichiara_lingua(lingua)
    return await funzione(*args, **kwargs)


@pytest.mark.asyncio
async def test_il_lettore_multimediale_risponde_nella_lingua_di_chi_ha_chiesto(casa, da_web) -> None:
    it = await _dice("it", domini_casa.comanda_media, "media_player.salotto", "volume", volume=40)
    en = await _dice("en", domini_casa.comanda_media, "media_player.salotto", "volume", volume=40)
    assert it["message"] == "Volume di TV salotto al 40 per cento."
    assert en["message"] == "TV salotto volume set to 40 percent."

    assert (await _dice("en", domini_casa.comanda_media, "media_player.salotto", "pausa"))["message"] == (
        "Done on TV salotto: pausa."
    )
    assert (await _dice("en", domini_casa.comanda_media, "media_player.salotto", "volume"))["error"] == (
        "I need a volume from 0 to 100."
    )
    assert (await _dice("en", domini_casa.comanda_media, "media_player.salotto", "salta"))["error"] == (
        "Action «salta» is not supported for a media player."
    )


@pytest.mark.asyncio
async def test_l_aspirapolvere_risponde_nella_lingua_di_chi_ha_chiesto(casa, da_web) -> None:
    it = await _dice("it", domini_casa.comanda_aspirapolvere, "vacuum.robot", "avvia", stanza="cucina")
    en = await _dice("en", domini_casa.comanda_aspirapolvere, "vacuum.robot", "avvia", stanza="cucina")
    assert it["message"] == "Robottino sta pulendo cucina."
    assert en["message"] == "Robottino is cleaning cucina."

    err = await _dice("en", domini_casa.comanda_aspirapolvere, "vacuum.robot", "vola")
    assert err["error"] == "Action «vola» is not supported for a vacuum."


@pytest.mark.asyncio
async def test_il_ventilatore_risponde_nella_lingua_di_chi_ha_chiesto(casa, da_web) -> None:
    pares = [
        (("accendi",), {}, "Ventilatore camera acceso.", "Ventilatore camera turned on."),
        (("spegni",), {}, "Ventilatore camera spento.", "Ventilatore camera turned off."),
        (
            ("velocita",),
            {"velocita": 60},
            "Ventilatore camera al 60 per cento.",
            "Ventilatore camera at 60 percent.",
        ),
        (
            ("oscilla",),
            {"oscillazione": True},
            "Oscillazione di Ventilatore camera attivata.",
            "Ventilatore camera oscillation turned on.",
        ),
        (
            ("oscilla",),
            {"oscillazione": False},
            "Oscillazione di Ventilatore camera disattivata.",
            "Ventilatore camera oscillation turned off.",
        ),
    ]
    for args, kwargs, atteso_it, atteso_en in pares:
        it = await _dice("it", domini_casa.comanda_ventilatore, "fan.camera", *args, **kwargs)
        en = await _dice("en", domini_casa.comanda_ventilatore, "fan.camera", *args, **kwargs)
        assert (it["message"], en["message"]) == (atteso_it, atteso_en)

    assert (await _dice("en", domini_casa.comanda_ventilatore, "fan.camera", "velocita"))["error"] == (
        "I need a speed from 0 to 100."
    )
    assert (await _dice("it", domini_casa.comanda_ventilatore, "fan.camera", "gira"))["error"] == (
        "Azione «gira» non prevista per un ventilatore."
    )


def test_ogni_lingua_ha_le_frasi_dei_tre_strumenti() -> None:
    chiavi = [k for k in schemi("it").messaggi if k.startswith(("media_", "ventilatore_", "aspirapolvere_"))]
    assert len(chiavi) >= 17
    for lingua in lingue_disponibili():
        mancano = [k for k in chiavi if k not in schemi(lingua).messaggi]
        assert mancano == [], f"{lingua}: {mancano}"
