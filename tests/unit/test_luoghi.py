"""I luoghi (#342): validare, registrare, e non far uscire le coordinate.

La posizione e' un dato delicato. Le prove che contano di piu' sono quelle di privacy: le coordinate non finiscono nel
registro delle azioni, nei log, in un salvataggio, ne' nell'elenco che vede l'interfaccia (che le riceve arrotondate).
"""

from __future__ import annotations

import json
import logging

import pytest

from shinra.api import routes_luoghi
from shinra.domain import luoghi as dominio
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import luoghi, registro, salvataggio

# Via del Corso, Roma (un posto qualunque): le cifre sono riconoscibili se compaiono dove non devono.
LAT, LON = 41.902784, 12.496366


@pytest.fixture(autouse=True)
def senza_luoghi():
    deposito.sostituisci_tutto([])
    yield
    deposito.sostituisci_tutto([])


def casa(**extra):
    return {"nome": "Casa", "latitudine": LAT, "longitudine": LON, "origine": "telefono", **extra}


# ------------------------------------------------------------------ il dominio


def test_la_distanza_fra_due_punti_e_quella_giusta():
    assert dominio.distanza_m(LAT, LON, LAT, LON) == 0
    # un grado di latitudine sono circa 111 km
    assert dominio.distanza_m(41.0, 12.0, 42.0, 12.0) == pytest.approx(111_195, rel=0.001)
    # Roma - Milano circa 477 km in linea d'aria
    assert dominio.distanza_m(41.9028, 12.4964, 45.4642, 9.19) == pytest.approx(477_000, rel=0.02)


@pytest.mark.parametrize(
    "dati, parola",
    [
        ({"nome": "  "}, "nome"),
        ({"tipo": "castello"}, "tipo"),
        ({"latitudine": 91}, "latitudine"),
        ({"longitudine": -181}, "longitudine"),
        ({"latitudine": "non so"}, "latitudine"),
        ({"latitudine": None}, "latitudine"),
        ({"latitudine": float("nan")}, "latitudine"),
        ({"latitudine": True}, "latitudine"),
        ({"latitudine": 0, "longitudine": 0}, "coordinate"),
        ({"origine": "indovinata"}, "origine"),
        ({"precisione_m": -5}, "precisione"),
    ],
)
def test_un_luogo_impossibile_e_rifiutato(dati, parola):
    with pytest.raises(dominio.LuogoNonValido, match=parola):
        dominio.valida(casa(**dati))


def test_il_raggio_non_scende_sotto_la_precisione_della_registrazione():
    """Un PC che sa dov'e' a 800 metri non puo' promettere un luogo largo 100."""
    assert dominio.valida(casa(raggio_m=100, precisione_m=800)).raggio_m == 1200
    assert dominio.valida(casa(raggio_m=100, precisione_m=10)).raggio_m == 100
    assert dominio.valida(casa()).raggio_m == dominio.RAGGIO_PREDEFINITO_M
    assert dominio.valida(casa(raggio_m=1)).raggio_m == dominio.RAGGIO_MINIMO_M
    assert dominio.valida(casa(raggio_m=10**6)).raggio_m == dominio.RAGGIO_MASSIMO_M


def test_il_piu_vicino_entro_il_raggio_e_in_giro_altrimenti():
    luoghi_ = [
        {"id": "a", "latitudine": LAT, "longitudine": LON, "raggio_m": 150},
        {"id": "b", "latitudine": 45.4642, "longitudine": 9.19, "raggio_m": 150},
    ]
    assert dominio.piu_vicino(LAT + 0.0005, LON, luoghi_)["id"] == "a"  # ~55 m
    assert dominio.piu_vicino(45.4643, 9.1901, luoghi_)["id"] == "b"
    assert dominio.piu_vicino(LAT + 0.01, LON, luoghi_) is None  # ~1,1 km: in giro


def test_le_coordinate_per_un_servizio_esterno_sono_arrotondate_a_circa_un_chilometro():
    lat, lon = dominio.arrotonda_per_servizi_esterni(LAT, LON)
    assert (lat, lon) == (41.9, 12.5)
    assert dominio.distanza_m(LAT, LON, lat, lon) < 1500


# ------------------------------------------------------------------ il servizio


def test_il_primo_luogo_e_il_principale():
    primo = luoghi.registra(casa())
    secondo = luoghi.registra(casa(nome="Mare", latitudine=44.0, longitudine=12.0))
    assert primo["principale"] is True and secondo["principale"] is False
    assert luoghi.principale()["id"] == primo["id"]


def test_chiedere_un_nuovo_principale_toglie_il_titolo_al_vecchio():
    luoghi.registra(casa())
    mare = luoghi.registra(casa(nome="Mare", latitudine=44.0, longitudine=12.0, principale=True))
    assert [x["id"] for x in luoghi.elenco() if x["principale"]] == [mare["id"]], "due luoghi principali"


def test_cancellando_il_principale_lo_diventa_un_altro():
    primo = luoghi.registra(casa())
    secondo = luoghi.registra(casa(nome="Mare", latitudine=44.0, longitudine=12.0))
    assert luoghi.cancella(primo["id"]) is True
    assert luoghi.principale()["id"] == secondo["id"]
    assert luoghi.cancella("l_inesistente") is False


def test_cancellare_un_luogo_cancella_le_coordinate():
    primo = luoghi.registra(casa())
    luoghi.cancella(primo["id"])
    assert deposito.elenco() == []


def test_modificare_non_ritocca_le_coordinate():
    primo = luoghi.registra(casa())
    nuovo = luoghi.aggiorna(primo["id"], {"nome": "Casa mia", "latitudine": 10.0, "longitudine": 10.0})
    assert nuovo["nome"] == "Casa mia"
    assert (nuovo["latitudine"], nuovo["longitudine"]) == (
        LAT,
        LON,
    ), "le coordinate si registrano di nuovo, non si ritoccano"


def test_modificare_un_luogo_che_non_c_e_e_un_errore():
    with pytest.raises(luoghi.LuogoNonTrovato):
        luoghi.aggiorna("l_inesistente", {"nome": "x"})


STATI = [
    {
        "entity_id": "person.alessio",
        "state": "home",
        "attributes": {"latitude": LAT, "longitude": LON, "gps_accuracy": 12},
    },
    {"entity_id": "person.ospite", "state": "unknown", "attributes": {}},
    {"entity_id": "light.cucina", "state": "on", "attributes": {}},
]


def test_si_registra_dalla_posizione_che_home_assistant_conosce_di_una_persona():
    luogo = luoghi.dalla_posizione_di_una_persona(STATI, "person.alessio", {"nome": "Casa"})
    assert (luogo["latitudine"], luogo["longitudine"]) == (LAT, LON)
    assert luogo["origine"] == "telefono" and luogo["precisione_m"] == 12


@pytest.mark.parametrize("entita", ["person.ospite", "person.nessuno", "light.cucina"])
def test_senza_una_posizione_vera_non_si_registra_niente(entita):
    with pytest.raises(dominio.LuogoNonValido):
        luoghi.dalla_posizione_di_una_persona(STATI, entita, {"nome": "Casa"})
    assert deposito.elenco() == []


# ------------------------------------------------------------------ la privacy


def test_il_registro_dice_che_e_avvenuto_non_dove_ne_come_si_chiama():
    luogo = luoghi.registra(casa(nome="Casa di mia madre"))
    luoghi.cancella(luogo["id"])

    tutte = registro.voci()
    assert {"luogo.registrato", "luogo.cancellato"} <= {v["azione"] for v in tutte}
    # Si guardano i dettagli delle voci dei luoghi, non l'intera riga: un orario come «07:23:41.9…» contiene «41.9» per caso
    # (il test falliva una volta ogni tanto, a seconda del secondo in cui girava).
    voci = json.dumps([v["dettagli"] for v in tutte if v["azione"].startswith("luogo.")], default=str)
    for segreto in ("41.9027", "12.4963", "41.9", "madre"):
        assert segreto not in voci, f"il registro riporta «{segreto}»"


def test_i_log_non_riportano_le_coordinate(caplog):
    with caplog.at_level(logging.DEBUG):
        luogo = luoghi.registra(casa(nome="Casa di mia madre"))
        luoghi.aggiorna(luogo["id"], {"nome": "Altro"})
        luoghi.cancella(luogo["id"])
    testo = " ".join(r.getMessage() for r in caplog.records)
    assert "41.9027" not in testo and "12.4963" not in testo and "madre" not in testo


def test_i_luoghi_non_escono_in_un_salvataggio():
    luoghi.registra(casa())
    assert "luoghi" not in salvataggio.TABELLE, "le coordinate non devono finire in un archivio che si copia"
    assert "luoghi" in salvataggio.FUORI, "la tabella nuova non e' stata decisa"
    archivio = json.dumps(salvataggio.esporta(), default=str)
    assert "41.9027" not in archivio and "12.4963" not in archivio


async def test_l_interfaccia_riceve_le_coordinate_arrotondate():
    esito = await routes_luoghi.registra(routes_luoghi.LuogoIn(nome="Casa", latitudine=LAT, longitudine=LON))
    visibile = esito["luogo"]
    assert "latitudine" not in visibile and "longitudine" not in visibile
    assert (visibile["latitudine_approssimata"], visibile["longitudine_approssimata"]) == (41.9, 12.5)

    elenco = await routes_luoghi.elenco()
    assert "41.9027" not in json.dumps(elenco) and "12.4963" not in json.dumps(elenco)


async def test_un_luogo_impossibile_diventa_un_errore_422():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_luoghi.registra(routes_luoghi.LuogoIn(nome="Casa", latitudine=0, longitudine=0))
    assert errore.value.status_code == 422


def test_le_rotte_dei_luoghi_chiedono_il_permesso_delle_impostazioni():
    permessi_richiesti = {d.dependency.__name__ for d in routes_luoghi.router.dependencies}
    assert len(routes_luoghi.router.dependencies) == 2, permessi_richiesti


async def test_la_rotta_da_persona_legge_la_posizione_da_home_assistant(monkeypatch):
    class FintoClient:
        async def stati_correnti(self):
            return STATI

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())

    esito = await routes_luoghi.registra_da_persona(
        routes_luoghi.LuogoDaPersonaIn(entita="person.alessio", nome="Casa")
    )

    assert esito["luogo"]["origine"] == "telefono" and esito["luogo"]["precisione_m"] == 12
    assert "latitudine" not in esito["luogo"]


async def test_la_rotta_da_persona_senza_posizione_e_un_422(monkeypatch):
    from fastapi import HTTPException

    class FintoClient:
        async def stati_correnti(self):
            return STATI

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())

    with pytest.raises(HTTPException) as errore:
        await routes_luoghi.registra_da_persona(
            routes_luoghi.LuogoDaPersonaIn(entita="person.ospite", nome="Casa")
        )
    assert errore.value.status_code == 422
