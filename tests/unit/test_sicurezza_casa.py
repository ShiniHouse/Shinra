"""L'allarme, e le finestre che si dimentica di chiudere.

E' il dominio per cui una famiglia installa la domotica, ed era l'unico
completamente scoperto.

Il test che porta il peso di tutta la issue e'
`test_non_arma_con_una_finestra_aperta`. Un allarme inserito su una casa
aperta suona da solo dopo dieci minuti, e chi lo ha inserito impara la cosa
sbagliata — che l'allarme e' inaffidabile — e smette di usarlo. Il rifiuto
non e' pignoleria: e' cio' che tiene in vita l'abitudine di inserirlo.

Riferimento: issue #23, ADR 0004.
"""

from __future__ import annotations

import pytest

from shinra.domain import aperture as dominio
from shinra.skills import sicurezza_casa

APERTO = {
    "entity_id": "binary_sensor.finestra_cucina",
    "state": "on",
    "attributes": {"device_class": "window", "friendly_name": "Finestra cucina"},
}
CHIUSO = {
    "entity_id": "binary_sensor.porta_ingresso",
    "state": "off",
    "attributes": {"device_class": "door", "friendly_name": "Porta d'ingresso"},
}
PANNELLO = {
    "entity_id": "alarm_control_panel.casa",
    "state": "disarmed",
    "attributes": {"friendly_name": "Allarme casa"},
}


@pytest.fixture
def casa(monkeypatch):
    chiamate: list[tuple[str, str, dict]] = []
    esito = {"success": True}
    stati = [dict(PANNELLO), dict(CHIUSO)]

    class FintoClient:
        async def call_service(self, dom, servizio, dati=None):
            chiamate.append((dom, servizio, dati or {}))
            return dict(esito)

        async def stati_correnti(self):
            return [dict(s) for s in stati]

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    sicurezza_casa.azzera_conferme()
    yield chiamate, stati, esito
    sicurezza_casa.azzera_conferme()


@pytest.fixture
def da_web():
    from shinra.services import registro

    registro.apri_contesto(attore="alessio", canale="web")


# --------------------------------------------------- cosa conta per aperto


def test_un_sensore_di_movimento_non_e_un_apertura():
    """`on` per un sensore di movimento significa «qualcuno si muove», non
    «e' aperto». Confonderli farebbe rifiutare ogni inserimento."""
    stati = [
        APERTO,
        {"entity_id": "binary_sensor.movimento", "state": "on", "attributes": {"device_class": "motion"}},
    ]

    assert [a.entity_id for a in dominio.aperte(stati)] == ["binary_sensor.finestra_cucina"]


def test_una_tapparella_aperta_conta():
    stati = [{"entity_id": "cover.salotto", "state": "open", "attributes": {"friendly_name": "Tapparella"}}]

    assert len(dominio.aperte(stati)) == 1


def test_un_sensore_che_non_risponde_non_e_ne_aperto_ne_chiuso():
    """Metterlo fra gli aperti significherebbe non poter piu' inserire
    l'allarme per un guasto."""
    stati = [
        {"entity_id": "binary_sensor.rotto", "state": "unavailable", "attributes": {"device_class": "window"}}
    ]

    assert dominio.aperture(stati) == []


def test_il_riassunto_si_legge_ad_alta_voce():
    elenco = [
        dominio.Apertura("a", "Finestra cucina", True, "window"),
        dominio.Apertura("b", "Porta garage", True, "door"),
        dominio.Apertura("c", "Finestra bagno", True, "window"),
    ]

    assert dominio.riassunto(elenco) == "Finestra cucina, Porta garage e Finestra bagno"


# ----------------------------------------------------------- le aperture


async def test_con_tutto_chiuso_lo_dice(casa):
    esito = await sicurezza_casa.stato_aperture()

    assert esito["success"] is True
    assert esito["aperte"] == []
    assert "Tutto chiuso" in esito["message"]


async def test_elenca_cosa_e_rimasto_aperto(casa):
    _, stati, _ = casa
    stati.append(dict(APERTO))

    esito = await sicurezza_casa.stato_aperture()

    assert [a["nome"] for a in esito["aperte"]] == ["Finestra cucina"]
    assert "Finestra cucina" in esito["message"]


async def test_senza_sensori_lo_dice_invece_di_rassicurare(casa):
    """«Tutto chiuso» senza aver controllato niente e' la risposta peggiore."""
    _, stati, _ = casa
    stati[:] = [dict(PANNELLO)]

    esito = await sicurezza_casa.stato_aperture()

    assert esito["success"] is False
    assert "non posso dirti" in esito["message"]


# ------------------------------------------------------------- l'allarme


async def test_non_arma_con_una_finestra_aperta(casa, da_web):
    """Il test che porta il peso della issue.

    Un allarme inserito su una casa aperta suona da solo dopo dieci minuti,
    e chi lo ha inserito conclude che l'allarme e' inaffidabile.
    """
    chiamate, stati, _ = casa
    stati.append(dict(APERTO))

    esito = await sicurezza_casa.comanda_allarme("arma_fuori")

    assert esito["success"] is False
    assert chiamate == [], "non deve aver armato niente"
    assert "Finestra cucina" in esito["error"]
    assert esito["serve_conferma"] is True


async def test_con_la_conferma_arma_lo_stesso_e_lo_ricorda(casa, da_web):
    chiamate, stati, _ = casa
    stati.append(dict(APERTO))

    esito = await sicurezza_casa.comanda_allarme("arma_fuori", forza=True)

    assert esito["success"] is True
    assert chiamate[0][1] == "alarm_arm_away"
    assert "resta aperto" in esito["message"]


async def test_con_tutto_chiuso_arma_senza_domande(casa, da_web):
    chiamate, _, _ = casa

    esito = await sicurezza_casa.comanda_allarme("arma_casa")

    assert esito["success"] is True
    assert chiamate == [("alarm_control_panel", "alarm_arm_home", {"entity_id": "alarm_control_panel.casa"})]


async def test_il_codice_arriva_alla_centrale(casa, da_web):
    chiamate, _, _ = casa

    await sicurezza_casa.comanda_allarme("arma_fuori", codice="1234")

    assert chiamate[0][2]["code"] == "1234"


async def test_con_piu_centrali_chiede_quale(casa, da_web):
    chiamate, stati, _ = casa
    stati.append({"entity_id": "alarm_control_panel.garage", "state": "disarmed", "attributes": {}})

    esito = await sicurezza_casa.comanda_allarme("arma_fuori")

    assert esito["success"] is False
    assert chiamate == []
    assert "piu' centrali" in esito["error"]


async def test_lo_stato_si_dice_in_italiano(casa, da_web):
    _, stati, _ = casa
    stati[0]["state"] = "armed_away"

    esito = await sicurezza_casa.comanda_allarme("stato")

    assert "inserito fuori casa" in esito["message"]


# ------------------------------------------------------------ il disarmo


async def test_dal_web_il_disarmo_e_immediato(casa, da_web):
    chiamate, _, _ = casa

    esito = await sicurezza_casa.comanda_allarme("disarma")

    assert esito["success"] is True
    assert chiamate[0][1] == "alarm_disarm"


async def test_da_alexa_il_disarmo_chiede_conferma(casa):
    from shinra.services import registro

    chiamate, _, _ = casa
    registro.apri_contesto(attore="alessio", canale="alexa")

    esito = await sicurezza_casa.comanda_allarme("disarma")

    assert esito["success"] is False
    assert esito["conferma_richiesta"] is True
    assert chiamate == []


async def test_da_alexa_la_seconda_richiesta_disarma(casa):
    from shinra.services import registro

    chiamate, _, _ = casa
    registro.apri_contesto(attore="alessio", canale="alexa")
    await sicurezza_casa.comanda_allarme("disarma")

    esito = await sicurezza_casa.comanda_allarme("disarma")

    assert esito["success"] is True
    assert chiamate[0][1] == "alarm_disarm"


# ------------------------------------------------------- l'intrusione


async def test_quando_scatta_finisce_sul_bus(monkeypatch):
    from shinra.domain.eventi import CASA_INTRUSIONE, HA_STATO_CAMBIATO, Evento, bus
    from shinra.services.allarme import ServizioAllarme

    visti: list[Evento] = []
    monkeypatch.setattr(bus, "pubblica_senza_attendere", visti.append)
    servizio = ServizioAllarme()

    servizio._su_cambiamento(
        Evento(
            tipo=HA_STATO_CAMBIATO,
            dati={"entity_id": "alarm_control_panel.casa", "stato": "triggered", "nome": "Allarme casa"},
        )
    )

    assert [e.tipo for e in visti] == [CASA_INTRUSIONE]
    assert "persone_in_casa" in visti[0].dati


async def test_inserire_l_allarme_non_e_un_intrusione(monkeypatch):
    from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento, bus
    from shinra.services.allarme import ServizioAllarme

    visti: list[Evento] = []
    monkeypatch.setattr(bus, "pubblica_senza_attendere", visti.append)

    ServizioAllarme()._su_cambiamento(
        Evento(tipo=HA_STATO_CAMBIATO, dati={"entity_id": "alarm_control_panel.casa", "stato": "armed_away"})
    )

    assert visti == []


def test_la_centrale_e_osservata_sul_bus():
    """Senza, l'allarme potrebbe scattare e nessuno lo saprebbe."""
    from shinra.infra.homeassistant.stati import DOMINI_OSSERVATI

    assert "alarm_control_panel" in DOMINI_OSSERVATI
