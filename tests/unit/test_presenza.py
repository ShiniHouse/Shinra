"""Chi c'e' in casa.

`person` e `device_tracker` comparivano fra i domini visibili e nessuna riga
li guardava: il sistema non sapeva se in casa ci fosse qualcuno, che e'
l'informazione piu' utile della domotica.

Il test che conta piu' di tutti e' `test_un_buco_del_gps_non_svuota_la_casa`.
Il GPS di un telefono perde il segnale in garage, in ascensore, dietro un
muro spesso: Home Assistant lo racconta come «uscito» e lo ridice
«rientrato» un minuto dopo. Senza attesa la casa spegne tutto addosso a chi
e' appena sceso in cantina — ed e' il genere di difetto che fa disattivare
l'automazione invece di sistemarla.

Riferimento: issue #22.
"""

from __future__ import annotations

import asyncio

import pytest

from shinra.domain import presenza as dominio
from shinra.domain.eventi import Evento, bus
from shinra.services.presenza import ServizioPresenza


def _stato(entita: str, valore: str) -> dict:
    return {"entity_id": entita, "state": valore}


def _cambiamento(entita: str, valore: str) -> Evento:
    from shinra.domain.eventi import HA_STATO_CAMBIATO

    return Evento(tipo=HA_STATO_CAMBIATO, dati={"entity_id": entita, "stato": valore})


@pytest.fixture
def raccolti(monkeypatch):
    visti: list[Evento] = []
    monkeypatch.setattr(bus, "pubblica_senza_attendere", visti.append)
    return visti


@pytest.fixture
def servizio(monkeypatch):
    """Un servizio con la casa gia' fotografata e l'attesa ridotta a un
    battito, cosi' i test non aspettano due minuti."""
    from shinra.config.settings import settings

    monkeypatch.setattr(settings.presenza, "ritardo_uscita_secondi", 0)
    s = ServizioPresenza()
    s._creduto = {"person.alessio": "home", "person.sonia": "home"}
    s._ultimo = s.stato
    yield s
    s.azzera()


# ------------------------------------------------------- la lettura pura


def test_chi_ha_uno_stato_ignoto_non_e_ne_dentro_ne_fuori():
    """Non sapere dov'e' una persona non e' saperla fuori: e' la differenza
    fra aspettare e spegnere le luci."""
    stato = dominio.leggi(
        {"person.a": "home", "person.b": "not_home", "person.c": "unknown", "person.d": "unavailable"}
    )

    assert stato.presenti == frozenset({"person.a"})
    assert stato.assenti == frozenset({"person.b"})


def test_una_zona_diversa_da_casa_e_fuori():
    stato = dominio.leggi({"person.a": "Ufficio"})

    assert stato.assenti == frozenset({"person.a"})


def test_senza_nessuna_persona_la_casa_non_e_conosciuta():
    """«Casa vuota» dedotto dal nulla sarebbe una notizia inventata."""
    vuoto = dominio.leggi({})

    assert vuoto.conosciuta is False
    assert dominio.transizioni(vuoto, vuoto) == []


def test_all_avvio_non_si_annuncia_niente():
    """Altrimenti ogni riavvio direbbe che sono rientrati tutti, e farebbe
    partire le routine di benvenuto."""
    dopo = dominio.leggi({"person.a": "home"})

    assert dominio.transizioni(None, dopo) == []


def test_l_ultima_uscita_produce_casa_vuota():
    prima = dominio.leggi({"person.a": "home", "person.b": "not_home"})
    dopo = dominio.leggi({"person.a": "not_home", "person.b": "not_home"})

    tipi = [t.tipo for t in dominio.transizioni(prima, dopo)]

    assert tipi == [dominio.PERSONA_USCITA, dominio.CASA_VUOTA]


def test_la_persona_viene_prima_della_casa():
    """Chi ascolta «casa vuota» vuole gia' sapere chi e' stato l'ultimo."""
    prima = dominio.leggi({"person.a": "home"})
    dopo = dominio.leggi({"person.a": "not_home"})

    cambiamenti = dominio.transizioni(prima, dopo)

    assert cambiamenti[0].persona == "person.a"
    assert cambiamenti[-1].tipo == dominio.CASA_VUOTA


def test_il_primo_rientro_riabita_la_casa():
    prima = dominio.leggi({"person.a": "not_home"})
    dopo = dominio.leggi({"person.a": "home"})

    tipi = [t.tipo for t in dominio.transizioni(prima, dopo)]

    assert tipi == [dominio.PERSONA_RIENTRATA, dominio.CASA_ABITATA]


def test_il_secondo_rientro_non_riannuncia_la_casa():
    prima = dominio.leggi({"person.a": "home", "person.b": "not_home"})
    dopo = dominio.leggi({"person.a": "home", "person.b": "home"})

    tipi = [t.tipo for t in dominio.transizioni(prima, dopo)]

    assert tipi == [dominio.PERSONA_RIENTRATA]


# --------------------------------------------------- il tempo, e il GPS


async def test_un_rientro_si_crede_subito(servizio, raccolti):
    """Chi torna a casa vuole la luce accesa adesso. E un falso rientro non
    spegne niente a nessuno: l'attesa serve solo dall'altra parte."""
    servizio._creduto["person.sonia"] = "not_home"
    servizio._ultimo = servizio.stato
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("person.sonia", "home"))

    assert [e.tipo for e in raccolti] == [dominio.PERSONA_RIENTRATA]


async def test_un_uscita_aspetta_prima_di_essere_creduta(monkeypatch, raccolti):
    from shinra.config.settings import settings

    monkeypatch.setattr(settings.presenza, "ritardo_uscita_secondi", 30)
    servizio = ServizioPresenza()
    servizio._creduto = {"person.alessio": "home"}
    servizio._ultimo = servizio.stato

    servizio._su_cambiamento(_cambiamento("person.alessio", "not_home"))

    assert raccolti == [], "non si annuncia niente prima dell'attesa"
    assert servizio.dettaglio()["in_attesa"] == ["person.alessio"]
    assert servizio.dettaglio()["abitata"] is True
    servizio.azzera()


async def test_un_buco_del_gps_non_svuota_la_casa(servizio, raccolti):
    """Il test per cui esiste tutto il resto.

    Il telefono perde il segnale in garage: Home Assistant dice «uscito», poi
    ci ripensa. Senza attesa la casa spegnerebbe tutto addosso a chi e'
    appena sceso in cantina, e lo riaccenderebbe quando risale.
    """
    servizio._creduto = {"person.alessio": "home"}
    servizio._ultimo = servizio.stato
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("person.alessio", "not_home"))
    servizio._su_cambiamento(_cambiamento("person.alessio", "home"))  # il segnale torna
    await asyncio.sleep(0.05)

    assert raccolti == [], "nessuno e' mai uscito, quindi non c'e' niente da dire"
    assert servizio.dettaglio()["abitata"] is True
    assert servizio.dettaglio()["in_attesa"] == []


async def test_passata_l_attesa_l_uscita_diventa_vera(servizio, raccolti):
    servizio._creduto = {"person.alessio": "home"}
    servizio._ultimo = servizio.stato
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("person.alessio", "not_home"))
    await asyncio.sleep(0.05)  # il ritardo qui e' zero

    assert [e.tipo for e in raccolti] == [dominio.PERSONA_USCITA, dominio.CASA_VUOTA]
    assert servizio.dettaglio()["abitata"] is False


async def test_uno_stato_ignoto_non_conclude_niente(servizio, raccolti):
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("person.alessio", "unknown"))
    await asyncio.sleep(0.05)

    assert raccolti == []
    assert "person.alessio" in servizio.stato.presenti


async def test_gli_altri_domini_non_riguardano_la_presenza(servizio, raccolti):
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("light.cucina", "off"))

    assert raccolti == []


async def test_l_evento_dice_chi_c_e_rimasto(servizio, raccolti):
    raccolti.clear()

    servizio._su_cambiamento(_cambiamento("person.sonia", "not_home"))
    await asyncio.sleep(0.05)

    uscita = next(e for e in raccolti if e.tipo == dominio.PERSONA_USCITA)
    assert uscita.dati["persona"] == "sonia"
    assert uscita.dati["persone_in_casa"] == ["person.alessio"]


# ------------------------------------------------------------- la rotta


async def test_person_arriva_sul_bus_degli_eventi():
    """Non basta che la casa mandi i cambiamenti: `person` non e' un dominio
    comandabile, e finche' sul bus finiva solo cio' che si comanda, la
    presenza non sarebbe mai arrivata fin qui."""
    from shinra.infra.homeassistant.stati import DOMINI_CONTROLLABILI, DOMINI_OSSERVATI

    assert "person" in DOMINI_OSSERVATI
    assert "person" not in DOMINI_CONTROLLABILI


async def test_la_rotta_racconta_chi_c_e(cliente_autenticato):
    risposta = cliente_autenticato.get("/api/presenza")

    assert risposta.status_code == 200
    for campo in ("abitata", "conosciuta", "presenti", "assenti", "in_attesa"):
        assert campo in risposta.json()
