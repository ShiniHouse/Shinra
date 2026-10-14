"""«Dove sei» (#343): in quale luogo registrato si trova una persona, senza conservare dove e' stata.

Le prove che contano sono di privacy: chi non ha collegato la posizione non e' localizzato, una posizione vecchia non vale,
si risponde col nome del luogo e mai con le coordinate, e **nessuna tabella** conserva uno spostamento.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from shinra.api import routes_posizione
from shinra.infra.db import depositi
from shinra.infra.db.luoghi import luoghi as deposito_luoghi
from shinra.infra.db.motore import sessione
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services import luoghi, posizione, registro
from shinra.services.user_manager import UserProfile

CASA = (41.902784, 12.496366)
MARE = (44.0, 12.0)


@pytest.fixture(autouse=True)
def pulito():
    deposito_luoghi.sostituisci_tutto([])
    cache_stati.svuota()
    luoghi.registra({"nome": "Casa", "latitudine": CASA[0], "longitudine": CASA[1], "origine": "telefono"})
    luoghi.registra({"nome": "Mare", "latitudine": MARE[0], "longitudine": MARE[1], "origine": "telefono"})
    yield
    deposito_luoghi.sostituisci_tutto([])
    cache_stati.svuota()


def persona(lat, lon, quando=None, entita="person.alessio"):
    cache_stati.aggiorna(
        {
            "entity_id": entita,
            "state": "home",
            "last_updated": (quando or datetime.now(timezone.utc)).isoformat(),
            "attributes": {"latitude": lat, "longitude": lon},
        }
    )


def test_senza_collegamento_non_si_e_localizzati():
    persona(*CASA)
    assert posizione.dove_sei("").stato == posizione.SPENTA


def test_si_dice_il_nome_del_luogo_in_cui_si_e():
    persona(CASA[0] + 0.0004, CASA[1])
    esito = posizione.dove_sei("person.alessio")
    assert (esito.stato, esito.luogo, esito.principale) == (posizione.IN_UN_LUOGO, "Casa", True)

    persona(MARE[0], MARE[1])
    esito = posizione.dove_sei("person.alessio")
    assert (esito.luogo, esito.principale) == ("Mare", False)


def test_fuori_da_ogni_luogo_si_e_in_giro():
    persona(45.0, 10.0)
    assert posizione.dove_sei("person.alessio").stato == posizione.IN_GIRO


@pytest.mark.parametrize(
    "stato", [None, {"entity_id": "person.alessio", "state": "unknown", "attributes": {}}]
)
def test_senza_una_posizione_letta_non_si_inventa(stato):
    if stato:
        cache_stati.aggiorna(stato)
    assert posizione.dove_sei("person.alessio").stato == posizione.IGNOTA


def test_una_posizione_ferma_da_ore_non_vale():
    ieri = datetime.fromtimestamp(time.time() - 3 * 3600, tz=timezone.utc)
    persona(*CASA, quando=ieri)
    assert posizione.dove_sei("person.alessio").stato == posizione.IGNOTA, "ha indicato un posto di ore fa"


def test_una_posizione_recente_vale():
    recente = datetime.fromtimestamp(time.time() - 60, tz=timezone.utc)
    persona(*CASA, quando=recente)
    assert posizione.dove_sei("person.alessio").stato == posizione.IN_UN_LUOGO


def test_la_risposta_non_contiene_coordinate():
    persona(*CASA)
    risposta = json.dumps(posizione.dove_sei("person.alessio").come_dizionario())
    assert "41.9" not in risposta and "12.49" not in risposta


def test_nessuna_tabella_conserva_dove_si_e_stati():
    """«Dove sei» si legge al momento: dopo tante letture il database non sa dove si e' stati."""
    for passo in range(5):
        persona(CASA[0] + passo * 0.00001, CASA[1])
        posizione.dove_sei("person.alessio")
    with sessione() as s:
        tabelle = [r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
        assert not [t for t in tabelle if "posizion" in t or "spostament" in t or "traccia" in t], tabelle


# ------------------------------------------------------------------- le rotte


@pytest.fixture
def io(monkeypatch):
    profilo = UserProfile(id="u_alessio", name="Alessio")
    depositi.utenti.salva({"id": profilo.id, "name": profilo.name, "role": "adult"})
    corrente = {"utente": profilo}
    monkeypatch.setattr(routes_posizione, "utente_corrente", lambda request: corrente["utente"])
    yield corrente
    depositi.utenti.cancella(profilo.id)


async def test_collegare_la_propria_posizione_e_poi_leggerla(io):
    persona(*CASA)
    prima = await routes_posizione.dove_sono(None)
    assert prima["stato"] == posizione.SPENTA

    esito = await routes_posizione.collega_la_mia_posizione(
        routes_posizione.PosizioneIn(entita="person.alessio"), None
    )
    assert (esito["stato"], esito["luogo"]) == (posizione.IN_UN_LUOGO, "Casa")
    assert depositi.utenti.per_id("u_alessio")["entita_posizione"] == "person.alessio"

    io["utente"] = UserProfile(id="u_alessio", name="Alessio", entita_posizione="person.alessio")
    assert (await routes_posizione.dove_sono(None))["luogo"] == "Casa"


async def test_spegnere_la_posizione_scollega_e_basta(io):
    await routes_posizione.collega_la_mia_posizione(
        routes_posizione.PosizioneIn(entita="person.alessio"), None
    )
    esito = await routes_posizione.collega_la_mia_posizione(routes_posizione.PosizioneIn(entita=""), None)
    assert esito["stato"] == posizione.SPENTA
    assert depositi.utenti.per_id("u_alessio")["entita_posizione"] == ""


async def test_si_collega_solo_una_persona_o_un_telefono(io):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_posizione.collega_la_mia_posizione(
            routes_posizione.PosizioneIn(entita="light.cucina"), None
        )
    assert errore.value.status_code == 422


async def test_senza_un_profilo_non_si_collega_niente(io):
    from fastapi import HTTPException

    io["utente"] = None
    with pytest.raises(HTTPException) as errore:
        await routes_posizione.collega_la_mia_posizione(
            routes_posizione.PosizioneIn(entita="person.alessio"), None
        )
    assert errore.value.status_code == 401


async def test_il_registro_dice_chi_ha_acceso_o_spento_non_dove_e(io):
    persona(*CASA)
    await routes_posizione.collega_la_mia_posizione(
        routes_posizione.PosizioneIn(entita="person.alessio"), None
    )
    await routes_posizione.collega_la_mia_posizione(routes_posizione.PosizioneIn(entita=""), None)
    voci = json.dumps(registro.voci(), default=str)
    assert "posizione.collegata" in voci and "posizione.spenta" in voci
    assert "Casa" not in json.dumps([v["dettagli"] for v in registro.voci(azione="posizione.collegata")])
    assert "41.9" not in voci


# ------------------------------------------------------ scegliere il telefono (#343)


def test_i_candidati_hanno_il_nome_che_si_legge_e_non_le_coordinate():
    cache_stati.aggiorna(
        {
            "entity_id": "device_tracker.iphone_di_shinigami",
            "state": "home",
            "attributes": {"friendly_name": "iPhone di Shinigami", "latitude": 41.9, "longitude": 12.5},
        }
    )
    cache_stati.aggiorna(
        {
            "entity_id": "person.alessio",
            "state": "home",
            "attributes": {"friendly_name": "Alessio", "latitude": 1.0, "longitude": 2.0},
        }
    )
    cache_stati.aggiorna(
        {"entity_id": "person.senza_gps", "state": "unknown", "attributes": {"friendly_name": "Ospite"}}
    )
    cache_stati.aggiorna(
        {"entity_id": "light.cucina", "state": "on", "attributes": {"friendly_name": "Cucina"}}
    )

    elenco = posizione.candidati()

    assert [c["entita"] for c in elenco] == [
        "person.alessio",
        "device_tracker.iphone_di_shinigami",
        "person.senza_gps",
    ]
    assert elenco[1]["nome"] == "iPhone di Shinigami" and elenco[1]["ha_posizione"] is True
    assert elenco[2]["ha_posizione"] is False
    assert "light.cucina" not in json.dumps(elenco)
    assert "41.9" not in json.dumps(elenco) and "12.5" not in json.dumps(
        elenco
    ), "i candidati riportano le coordinate"


async def test_la_rotta_dei_candidati_risponde_con_l_elenco():
    cache_stati.aggiorna(
        {"entity_id": "person.alessio", "state": "home", "attributes": {"friendly_name": "Alessio"}}
    )
    esito = await routes_posizione.candidati()
    assert [c["entita"] for c in esito["candidati"]] == ["person.alessio"]
