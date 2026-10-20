"""Regole che scattano all'arrivo in un luogo o alla partenza (#346).

«Quando arrivo al mare accendi il riscaldamento»: si riusano le **zone di Home Assistant**. Home Assistant dice dove e' una
persona con il nome della zona (`home`, «Casa al mare», `not_home`), e Shinra confronta quel nome con i luoghi registrati:
nessuna coordinata, nessuna traccia degli spostamenti. Il registro dice quale luogo ha fatto scattare la regola, mai dove si e'.
Una regola che non puo' scattare (persona sconosciuta a Home Assistant, zona mancante) lo dice nell'elenco.
"""

from __future__ import annotations

import json

import pytest

from shinra.domain import regole as dominio
from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento
from shinra.infra.db import depositi
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services import luoghi, posizione, registro
from shinra.services.regole import MotoreRegole

PERSONA = "person.alessio"


@pytest.fixture(autouse=True)
def archivio():
    deposito.sostituisci_tutto([])
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()
    casa = luoghi.registra({"nome": "Casa", "latitudine": 41.9, "longitudine": 12.49, "origine": "telefono"})
    mare = luoghi.registra(
        {"nome": "Casa al mare", "latitudine": 44.12, "longitudine": 12.23, "origine": "telefono"}
    )
    yield {"casa": casa["id"], "mare": mare["id"]}
    deposito.sostituisci_tutto([])
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()


def trigger(luogo, evento=dominio.ARRIVO, entita=PERSONA):
    return {"tipo": dominio.LUOGO, "luogo_id": luogo, "evento": evento, "entity_id": entita}


def regola(t):
    return dominio.Regola("r1", "Prova", t, (), ({"tipo": "modalita", "modalita": "x"},), True)


# ------------------------------------------------------------------ il dominio


def test_arrivo_scatta_solo_entrando_nel_luogo():
    r = regola(trigger("L1"))
    giusto = {"entity_id": PERSONA, "luogo_precedente": "", "luogo_nuovo": "L1"}
    assert dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, giusto)
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {**giusto, "luogo_nuovo": "L2"})
    assert not dominio.scatta_su_evento(
        r, HA_STATO_CAMBIATO, {**giusto, "luogo_precedente": "L1"}
    ), "era gia' li'"
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {**giusto, "entity_id": "person.sonia"})


def test_partenza_scatta_solo_uscendo_dal_luogo():
    r = regola(trigger("L1", dominio.PARTENZA))
    giusto = {"entity_id": PERSONA, "luogo_precedente": "L1", "luogo_nuovo": ""}
    assert dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, giusto)
    assert dominio.scatta_su_evento(
        r, HA_STATO_CAMBIATO, {**giusto, "luogo_nuovo": "L2"}
    ), "da un luogo all'altro e' una partenza"
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {**giusto, "luogo_precedente": ""})
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {**giusto, "luogo_nuovo": "L1"})


def test_senza_luogo_nel_trigger_non_scatta_mai():
    r = regola({"tipo": dominio.LUOGO, "evento": "arrivo", "entity_id": PERSONA})
    assert not dominio.scatta_su_evento(r, HA_STATO_CAMBIATO, {"entity_id": PERSONA, "luogo_nuovo": ""})


def test_la_descrizione_dice_il_luogo_non_le_coordinate():
    d = dominio.descrivi_trigger({**trigger("L1"), "luogo_nome": "Casa al mare"})
    assert "arriva a Casa al mare" in d
    assert "lascia Casa al mare" in dominio.descrivi_trigger(
        {**trigger("L1", dominio.PARTENZA), "luogo_nome": "Casa al mare"}
    )


def test_una_regola_su_luogo_non_ha_un_prossimo_scatto():
    from datetime import datetime

    assert dominio.prossimo_scatto(regola(trigger("L1")), datetime(2026, 10, 20, 12, 0)) is None


# ------------------------------------------------------------------ le zone di Home Assistant


def test_home_e_il_luogo_principale_e_gli_altri_si_riconoscono_dal_nome(archivio):
    assert posizione.luogo_dallo_stato("home") == archivio["casa"]
    assert posizione.luogo_dallo_stato("Casa al mare") == archivio["mare"]
    assert posizione.luogo_dallo_stato("  casa   AL mare ") == archivio["mare"]


@pytest.mark.parametrize("stato", ["not_home", "unknown", "unavailable", "", "Ufficio", None])
def test_fuori_o_ignoto_o_senza_luogo_registrato_e_nessun_luogo(stato):
    assert posizione.luogo_dallo_stato(stato) == ""


# ------------------------------------------------------------------ il motore


@pytest.fixture
def azioni(monkeypatch):
    """Il motore con un'azione finta che annota e basta."""
    fatte: list[str] = []

    async def esegui(self, regola, motivo="", catena=None):
        fatte.append(motivo)
        return {"eseguita": True}

    monkeypatch.setattr(MotoreRegole, "esegui", esegui)
    return fatte


def evento(prima, dopo, entita=PERSONA):
    return Evento(
        tipo=HA_STATO_CAMBIATO,
        dati={"entity_id": entita, "stato": dopo, "stato_precedente": prima, "dominio": "person"},
    )


async def test_arrivando_al_mare_la_regola_scatta_e_il_motivo_dice_il_luogo(archivio, azioni):
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Riscalda",
            "trigger": trigger(archivio["mare"]),
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    await motore._su_evento(evento("not_home", "Casa al mare"))
    assert azioni == ["arrivo Casa al mare"], "il motivo deve dire il luogo e non altro"


async def test_arrivando_altrove_non_scatta(archivio, azioni):
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Riscalda",
            "trigger": trigger(archivio["mare"]),
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    await motore._su_evento(evento("not_home", "home"))
    await motore._su_evento(evento("home", "not_home"))
    assert azioni == []


async def test_lasciando_il_mare_scatta_la_partenza(archivio, azioni):
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Spegni",
            "trigger": trigger(archivio["mare"], dominio.PARTENZA),
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    await motore._su_evento(evento("Casa al mare", "not_home"))
    assert azioni == ["partenza Casa al mare"]


async def test_un_altra_persona_non_fa_scattare_la_regola_di_alessio(archivio, azioni):
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Riscalda",
            "trigger": trigger(archivio["mare"]),
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    await motore._su_evento(evento("not_home", "Casa al mare", "person.sonia"))
    assert azioni == []


async def test_il_registro_della_regola_eseguita_dice_il_luogo_senza_coordinate(archivio, monkeypatch):
    """Dall'inizio alla fine: l'evento arriva, la regola esegue davvero e il registro dice quale luogo, non dove."""

    class FintoClient:
        async def call_service(self, dom, servizio, dati=None):
            return {"success": True}

        async def stati_correnti(self):
            return []

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    motore = MotoreRegole()
    motore.crea(
        {
            "nome": "Riscalda",
            "trigger": trigger(archivio["mare"]),
            "azioni": [{"tipo": "dispositivo", "entity_id": "climate.mare", "servizio": "turn_on"}],
        }
    )
    await motore._su_evento(evento("not_home", "Casa al mare"))
    voce = next(v for v in registro.voci(limite=10) if v["azione"] == "regola.eseguita")
    assert voce["dettagli"]["motivo"] == "arrivo Casa al mare"
    testo = json.dumps(voce, default=str)
    for cifra in ("44.12", "12.23", "41.9", "12.49"):
        assert cifra not in testo, f"il registro riporta le coordinate ({cifra})"


# ------------------------------------------------------------------ l'API


def _crea(cliente, **sovrascrivi):
    corpo = {
        "nome": "Riscalda al mare",
        "trigger": sovrascrivi.pop("trigger"),
        "azioni": [{"tipo": "modalita", "modalita": "x"}],
    }
    return cliente.post("/api/regole", json=corpo)


def test_si_crea_una_regola_su_un_luogo_registrato(cliente_autenticato, archivio):
    r = _crea(cliente_autenticato, trigger=trigger(archivio["mare"]))
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "cambia,parte",
    [
        ({"luogo_id": "l_inventato"}, "registrati"),
        ({"evento": "boh"}, "arrivo"),
        ({"entity_id": "light.cucina"}, "person"),
        ({"entity_id": ""}, "person"),
    ],
)
def test_un_trigger_su_luogo_sbagliato_e_rifiutato(cliente_autenticato, archivio, cambia, parte):
    r = _crea(cliente_autenticato, trigger={**trigger(archivio["mare"]), **cambia})
    assert r.status_code == 400 and parte in r.json()["detail"]


def test_l_elenco_dice_perche_una_regola_non_scattera(cliente_autenticato, archivio):
    # Home Assistant non conosce la persona: la regola non puo' scattare, e lo dice.
    id_ = _crea(cliente_autenticato, trigger=trigger(archivio["mare"])).json()["regola"]["id"]
    voce = {r["id"]: r for r in cliente_autenticato.get("/api/regole").json()["regole"]}[id_]
    assert "non conosce questa persona" in voce["avviso"] and voce["aspetta_un_evento"] is True
    assert "arriva a Casa al mare" in voce["descrizione"]

    # La persona c'e', ma in Home Assistant manca la zona con quel nome.
    cache_stati.aggiorna({"entity_id": PERSONA, "state": "home", "attributes": {}})
    voce = {r["id"]: r for r in cliente_autenticato.get("/api/regole").json()["regole"]}[id_]
    assert "manca una zona" in voce["avviso"] and "Casa al mare" in voce["avviso"]

    # Con la zona al suo posto non c'e' niente da dire.
    cache_stati.aggiorna(
        {"entity_id": "zone.casa_al_mare", "state": "0", "attributes": {"friendly_name": "Casa al mare"}}
    )
    voce = {r["id"]: r for r in cliente_autenticato.get("/api/regole").json()["regole"]}[id_]
    assert voce["avviso"] == ""


def test_una_regola_spenta_non_ha_avvisi(cliente_autenticato, archivio):
    corpo = {
        "nome": "Spenta",
        "attiva": False,
        "trigger": trigger(archivio["mare"]),
        "azioni": [{"tipo": "modalita", "modalita": "x"}],
    }
    id_ = cliente_autenticato.post("/api/regole", json=corpo).json()["regola"]["id"]
    voce = {r["id"]: r for r in cliente_autenticato.get("/api/regole").json()["regole"]}[id_]
    assert voce["avviso"] == ""


@pytest.mark.parametrize(
    "azione",
    [
        {"tipo": "dispositivo", "entity_id": "lock.ingresso", "servizio": "unlock"},
        {"tipo": "dispositivo", "entity_id": "alarm_control_panel.casa", "servizio": "alarm_disarm"},
        {"tipo": "dispositivo", "entity_id": "cover.porta_garage", "servizio": "open_cover"},
        {"tipo": "dispositivo", "entity_id": "script.cancello", "servizio": "turn_on"},
    ],
)
def test_un_azione_sensibile_non_si_lega_a_un_luogo(cliente_autenticato, archivio, azione):
    """#192: arrivando o partendo non si apre una serratura, non si disarma l'allarme, non si alza il garage."""
    corpo = {"nome": "Apri arrivando", "trigger": trigger(archivio["casa"]), "azioni": [azione]}
    r = cliente_autenticato.post("/api/regole", json=corpo)
    assert r.status_code == 400 and "non si comandano in automatico" in r.json()["detail"]
    assert depositi.regole.elenco() == []


def test_un_azione_normale_si_lega_a_un_luogo_e_chiudere_una_serratura_pure(cliente_autenticato, archivio):
    corpo = {
        "nome": "Accendi arrivando",
        "trigger": trigger(archivio["casa"]),
        "azioni": [
            {"tipo": "dispositivo", "entity_id": "climate.mare", "servizio": "turn_on"},
            {"tipo": "dispositivo", "entity_id": "lock.ingresso", "servizio": "lock"},
        ],
    }
    assert cliente_autenticato.post("/api/regole", json=corpo).status_code == 200


def test_la_modifica_non_aggira_il_controllo(cliente_autenticato, archivio):
    """Si puo' arrivare a una regola con luogo e azione sensibile anche cambiando una regola esistente: non deve riuscire."""
    luogo = cliente_autenticato.post(
        "/api/regole",
        json={
            "nome": "A",
            "trigger": trigger(archivio["casa"]),
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        },
    ).json()["regola"]["id"]
    sensibile = {"tipo": "dispositivo", "entity_id": "lock.ingresso", "servizio": "unlock"}
    r = cliente_autenticato.patch(f"/api/regole/{luogo}", json={"azioni": [sensibile]})
    assert r.status_code == 400

    orario = cliente_autenticato.post(
        "/api/regole",
        json={"nome": "B", "trigger": {"tipo": "orario", "ora": "07:00"}, "azioni": [sensibile]},
    ).json()["regola"]["id"]
    r = cliente_autenticato.patch(f"/api/regole/{orario}", json={"trigger": trigger(archivio["casa"])})
    assert (
        r.status_code == 400
    ), "si e' trasformata una regola a orario con una serratura in una regola su un luogo"
