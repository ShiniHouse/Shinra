"""#207: gli strumenti dicono il loro esito nella lingua di chi ha chiesto.

Due profili, uno italiano e uno inglese, comandano **la stessa serratura**: ciascuno riceve il messaggio di esito nella
propria lingua. La lingua viaggia nel contesto della richiesta, come l'attore e il canale, e gli strumenti la leggono
senza che nessuno gliela passi.
"""

from __future__ import annotations

import pytest

from shinra.domain import contesto
from shinra.infra.lingue import lingue_disponibili, schemi
from shinra.services.agent import ShinraAgent
from shinra.services.user_manager import UserProfile
from shinra.skills import domini_casa

# Le fixture `casa` (Home Assistant che annota) e `da_web` stanno in test_domini_casa.
from tests.unit.test_domini_casa import casa, da_web  # noqa: F401


@pytest.fixture(autouse=True)
def lingua_pulita():
    contesto.dichiara_lingua("")
    yield
    contesto.dichiara_lingua("")


@pytest.mark.asyncio
async def test_la_stessa_serratura_risponde_a_ciascuno_nella_sua_lingua(casa, da_web) -> None:  # noqa: F811
    contesto.dichiara_lingua("it")
    it = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")
    contesto.dichiara_lingua("en")
    en = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")

    assert it["message"] == "Porta d'ingresso chiusa."
    assert en["message"] == "Porta d'ingresso locked."
    assert it["success"] is en["success"] is True


@pytest.mark.asyncio
async def test_lo_stato_si_dice_nella_lingua_giusta(casa, da_web) -> None:  # noqa: F811
    contesto.dichiara_lingua("en")
    en = await domini_casa.comanda_serratura("lock.porta_ingresso", "stato")
    contesto.dichiara_lingua("it")
    it = await domini_casa.comanda_serratura("lock.porta_ingresso", "stato")

    assert en["message"] == "Porta d'ingresso is locked."
    assert it["message"] == "Porta d'ingresso e' chiusa."


@pytest.mark.asyncio
async def test_un_errore_di_azione_si_dice_nella_lingua_giusta(casa, da_web) -> None:  # noqa: F811
    contesto.dichiara_lingua("en")
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "esplodi")
    assert esito["error"] == "Action «esplodi» is not supported for a lock."


@pytest.mark.asyncio
async def test_senza_lingua_nel_contesto_si_segue_l_installazione(casa, da_web) -> None:  # noqa: F811
    contesto.dichiara_lingua("")
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")
    assert esito["message"] == "Porta d'ingresso chiusa."


@pytest.mark.asyncio
async def test_la_lingua_di_una_richiesta_non_resta_alla_successiva(casa, da_web) -> None:  # noqa: F811
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
