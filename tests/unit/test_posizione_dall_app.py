"""La posizione che manda l'app Shinra del telefono (#343): il GPS dell'iPhone, senza passare da Home Assistant.

Su iPhone una web app legge la posizione solo mentre e' aperta: per questo una segnalazione vale venti minuti. E, come ogni
posizione, si tiene **solo in memoria** (una per profilo): nessuna tabella, nessuna traccia, persa al riavvio.
"""

from __future__ import annotations

import json
import time

import pytest
from sqlalchemy import text

from shinra.api import routes_posizione
from shinra.domain import luoghi as dominio
from shinra.infra.db import depositi
from shinra.infra.db.luoghi import luoghi as deposito_luoghi
from shinra.infra.db.motore import sessione
from shinra.services import luoghi, posizione
from shinra.services.intenti import instrada
from shinra.services.intenti.base import Richiesta
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile

LAVORO = (45.4642, 9.19)


@pytest.fixture(autouse=True)
def pulito():
    deposito_luoghi.sostituisci_tutto([])
    posizione._dall_app.clear()
    luoghi.registra(
        {
            "nome": "Lavoro",
            "tipo": "lavoro",
            "latitudine": LAVORO[0],
            "longitudine": LAVORO[1],
            "origine": "telefono",
        }
    )
    depositi.utenti.salva(
        {"id": "u_app", "name": "App", "role": "adult", "entita_posizione": posizione.DISPOSITIVO}
    )
    yield
    deposito_luoghi.sostituisci_tutto([])
    posizione._dall_app.clear()
    depositi.utenti.cancella("u_app")


def test_senza_segnalazioni_dice_che_l_app_non_ha_ancora_mandato_niente():
    esito = posizione.dove_sei(posizione.DISPOSITIVO, profilo_id="u_app")
    assert esito.stato == posizione.IGNOTA and esito.motivo == posizione.APP_SENZA_SEGNALAZIONE


def test_una_segnalazione_dice_in_quale_luogo_si_e():
    posizione.segnala("u_app", LAVORO[0] + 0.0003, LAVORO[1], 12)
    esito = posizione.dove_sei(posizione.DISPOSITIVO, profilo_id="u_app")
    assert (esito.stato, esito.luogo, esito.tipo) == (posizione.IN_UN_LUOGO, "Lavoro", "lavoro")


def test_una_segnalazione_di_venti_minuti_fa_non_vale_piu():
    posizione.segnala("u_app", *LAVORO, adesso=time.time() - 21 * 60)
    esito = posizione.dove_sei(posizione.DISPOSITIVO, profilo_id="u_app")
    assert (
        esito.stato == posizione.IGNOTA
        and esito.motivo == posizione.TROPPO_VECCHIA
        and esito.eta_minuti >= 20
    )


def test_ogni_profilo_ha_la_sua_segnalazione():
    posizione.segnala("u_app", *LAVORO)
    assert (
        posizione.dove_sei(posizione.DISPOSITIVO, profilo_id="u_altro").motivo
        == posizione.APP_SENZA_SEGNALAZIONE
    )


@pytest.mark.parametrize("lat, lon", [(0, 0), (91, 10), (10, 181), ("boh", 3), (None, 3)])
def test_una_segnalazione_impossibile_e_rifiutata_e_non_si_tiene(lat, lon):
    with pytest.raises(dominio.LuogoNonValido):
        posizione.segnala("u_app", lat, lon)
    assert "u_app" not in posizione._dall_app


def test_la_segnalazione_sta_solo_in_memoria():
    """Nessuna tabella la conserva: nemmeno dopo tante segnalazioni."""
    for passo in range(5):
        posizione.segnala("u_app", 47.123456 + passo * 0.00001, 8.654321)
    assert len(posizione._dall_app) == 1, "una sola posizione per profilo"
    with sessione() as s:
        tabelle = [r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
        for tabella in tabelle:
            if tabella.startswith("alembic"):
                continue
            righe = s.execute(text(f'SELECT * FROM "{tabella}"')).all()  # noqa: S608
            assert "47.1234" not in json.dumps(
                [list(map(str, r)) for r in righe]
            ), f"la posizione e' in {tabella}"


def test_spegnere_o_cambiare_fonte_dimentica_la_segnalazione():
    posizione.segnala("u_app", *LAVORO)
    posizione.collega("u_app", "")
    assert "u_app" not in posizione._dall_app
    posizione.collega("u_app", posizione.DISPOSITIVO)
    posizione.segnala("u_app", *LAVORO)
    posizione.collega("u_app", "person.alessio")
    assert "u_app" not in posizione._dall_app


def test_questo_telefono_e_una_scelta_valida_e_una_luce_no():
    posizione.collega("u_app", posizione.DISPOSITIVO)
    with pytest.raises(posizione.EntitaNonValida):
        posizione.collega("u_app", "light.cucina")


# ------------------------------------------------------------------- le rotte


@pytest.fixture
def io(monkeypatch):
    corrente = {"utente": UserProfile(id="u_app", name="App", entita_posizione=posizione.DISPOSITIVO)}
    monkeypatch.setattr(routes_posizione, "utente_corrente", lambda request: corrente["utente"])
    return corrente


async def test_la_rotta_riceve_la_posizione_e_risponde_col_luogo(io):
    esito = await routes_posizione.segnala(
        routes_posizione.SegnalazioneIn(latitudine=LAVORO[0], longitudine=LAVORO[1], precisione_m=10), None
    )
    assert esito["stato"] == posizione.IN_UN_LUOGO and esito["luogo"] == "Lavoro"
    assert "45.46" not in json.dumps(esito), "la risposta riporta le coordinate"
    assert (await routes_posizione.dove_sono(None))["fonte"] == "dispositivo"


async def test_chi_non_ha_scelto_l_app_non_puo_segnalare(io):
    from fastapi import HTTPException

    io["utente"] = UserProfile(id="u_app", name="App", entita_posizione="person.alessio")
    with pytest.raises(HTTPException) as errore:
        await routes_posizione.segnala(routes_posizione.SegnalazioneIn(latitudine=1, longitudine=2), None)
    assert errore.value.status_code == 409 and "u_app" not in posizione._dall_app


async def test_la_rotta_rifiuta_un_punto_impossibile(io):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_posizione.segnala(routes_posizione.SegnalazioneIn(latitudine=0, longitudine=0), None)
    assert errore.value.status_code == 422


# -------------------------------------------- «dove sono?» e il meteo usano la segnalazione


def chiedi(testo: str) -> Richiesta:
    profilo = UserProfile(id="u_app", name="App", entita_posizione=posizione.DISPOSITIVO)
    return Richiesta(testo=testo, profilo=profilo, memoria=ConversationMemory())


async def test_dove_sono_risponde_con_la_posizione_dell_app():
    posizione.segnala("u_app", *LAVORO)
    assert (await instrada(chiedi("dove sono?"))).testo == "Sei a Lavoro."


async def test_dove_sono_senza_segnalazione_dice_di_aprire_l_app():
    testo = (await instrada(chiedi("dove sono?"))).testo
    assert "app Shinra" in testo and "consenti la posizione" in testo


async def test_il_meteo_usa_il_luogo_segnalato_dall_app(monkeypatch):
    from shinra.services.intenti import informazioni as modulo

    visti: list[str] = []

    async def di_un_luogo(nome, latitudine, longitudine, days=2):
        visti.append(nome)
        return {
            "success": True,
            "localita": nome,
            "adesso": {"temperatura": "9°C", "condizione": "Sereno"},
            "previsioni": [],
        }

    monkeypatch.setattr(modulo, "meteo_di_un_luogo", di_un_luogo)
    luoghi.registra(
        {"nome": "Casa", "latitudine": 41.9, "longitudine": 12.49, "origine": "telefono", "principale": True}
    )
    posizione.segnala("u_app", *LAVORO)
    await instrada(chiedi("che tempo fa oggi"))
    assert visti == ["Lavoro"]
