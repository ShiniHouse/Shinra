"""La posizione dell'app arriva a presenza e regole come se l'avesse detta Home Assistant (#343, #346)."""

from __future__ import annotations

import pytest

from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento, bus
from shinra.domain.presenza import CASA_ABITATA, PERSONA_RIENTRATA
from shinra.services import posizione, posizione_eventi
from shinra.services.presenza import presenza

CASA = posizione.DoveSei(posizione.IN_UN_LUOGO, "Casa", "casa", True)
MARE = posizione.DoveSei(posizione.IN_UN_LUOGO, "Casa al mare", "casa", False)
IN_GIRO = posizione.DoveSei(posizione.IN_GIRO)
IGNOTA = posizione.DoveSei(posizione.IGNOTA, motivo=posizione.TROPPO_VECCHIA)


@pytest.fixture(autouse=True)
def pulito():
    posizione_eventi._ultimo.clear()
    presenza.azzera()
    bus.azzera()
    yield
    posizione_eventi._ultimo.clear()
    presenza.azzera()
    bus.azzera()


@pytest.fixture
def visti(monkeypatch):
    eventi: list[Evento] = []
    monkeypatch.setattr(bus, "pubblica_senza_attendere", eventi.append)
    return eventi


def test_la_prima_segnalazione_non_e_un_arrivo(visti):
    posizione_eventi.annuncia("a", CASA)
    assert visti == []
    assert presenza.stato.presenti == frozenset({"person.app_a"})


def test_il_cambio_di_luogo_diventa_un_evento_di_home_assistant_senza_coordinate(visti):
    posizione_eventi.annuncia("a", CASA, "Alessio")
    posizione_eventi.annuncia("a", IN_GIRO, "Alessio")
    posizione_eventi.annuncia("a", MARE, "Alessio")
    assert [(e.tipo, e.dati["stato_precedente"], e.dati["stato"]) for e in visti] == [
        (HA_STATO_CAMBIATO, "home", "not_home"),
        (HA_STATO_CAMBIATO, "not_home", "Casa al mare"),
    ]
    assert all(e.dati["entity_id"] == "person.app_a" for e in visti)
    assert all(not ({"latitudine", "longitudine"} & set(e.dati)) for e in visti)


def test_la_stessa_posizione_due_volte_non_annuncia_niente(visti):
    posizione_eventi.annuncia("a", CASA)
    posizione_eventi.annuncia("a", CASA)
    assert visti == []


def test_una_posizione_ignota_non_e_un_uscita(visti):
    posizione_eventi.annuncia("a", CASA)
    posizione_eventi.annuncia("a", IGNOTA)
    posizione_eventi.annuncia("a", CASA)
    assert visti == []


async def test_la_presenza_vede_il_rientro_di_chi_usa_l_app():
    presenza._ultimo = presenza.stato  # il servizio e' acceso
    ricevuti: list[str] = []
    bus.sottoscrivi(PERSONA_RIENTRATA, lambda e: ricevuti.append(e.tipo))
    bus.sottoscrivi(CASA_ABITATA, lambda e: ricevuti.append(e.tipo))
    bus.sottoscrivi(HA_STATO_CAMBIATO, presenza._su_cambiamento)

    posizione_eventi.annuncia("a", IN_GIRO)
    await _svuota()
    posizione_eventi.annuncia("a", CASA)
    await _svuota()
    assert ricevuti == [PERSONA_RIENTRATA, CASA_ABITATA] or ricevuti == [CASA_ABITATA, PERSONA_RIENTRATA]


async def _svuota():
    import asyncio

    for _ in range(5):
        await asyncio.sleep(0)


def test_spegnere_la_fonte_toglie_la_persona_dell_app(visti):
    posizione_eventi.annuncia("a", CASA)
    posizione_eventi.dimentica("a")
    assert presenza.stato.presenti == frozenset()
    posizione_eventi.annuncia("a", IN_GIRO)
    assert visti == []  # di nuovo «la prima»: nessun annuncio


async def test_la_rotta_di_segnalazione_annuncia_il_luogo(monkeypatch):
    from shinra.api import routes_posizione
    from shinra.services.user_manager import UserProfile

    chiamate: list[tuple[str, str, str]] = []
    utente = UserProfile(id="u_app", name="App", entita_posizione=posizione.DISPOSITIVO)
    monkeypatch.setattr(routes_posizione, "utente_corrente", lambda request: utente)
    monkeypatch.setattr(posizione, "segnala", lambda *a, **k: None)
    monkeypatch.setattr(posizione, "dove_sei", lambda *a, **k: CASA)
    monkeypatch.setattr(
        posizione_eventi, "annuncia", lambda pid, dove, nome="": chiamate.append((pid, dove.luogo, nome))
    )
    await routes_posizione.segnala(routes_posizione.SegnalazioneIn(latitudine=45.0, longitudine=9.0), None)
    assert chiamate == [("u_app", "Casa", "App")]
