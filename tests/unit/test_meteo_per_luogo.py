"""Il meteo per il luogo giusto (#344): «al mare» risponde per il mare, senza luogo nominato per la casa principale.

La privacy conta quanto la risposta: a Open-Meteo vanno le coordinate arrotondate a circa un chilometro, e nelle azioni che
l'interfaccia mostra c'e' il nome del luogo, mai le coordinate.
"""

from __future__ import annotations

import json

import pytest

from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import luoghi
from shinra.services.intenti import informazioni as modulo
from shinra.services.intenti import instrada
from shinra.services.intenti.base import Richiesta
from shinra.services.memory import ConversationMemory
from shinra.skills import weather

CASA = (41.902784, 12.496366)
MARE = (44.123456, 12.234567)


@pytest.fixture(autouse=True)
def due_luoghi():
    deposito.sostituisci_tutto([])
    luoghi.registra({"nome": "Casa", "latitudine": CASA[0], "longitudine": CASA[1], "origine": "telefono"})
    luoghi.registra(
        {"nome": "Casa al mare", "latitudine": MARE[0], "longitudine": MARE[1], "origine": "telefono"}
    )
    yield
    deposito.sostituisci_tutto([])


@pytest.fixture
def meteo(monkeypatch):
    """Il meteo finto: annota per quale luogo e con quali coordinate e' stato chiesto."""
    chiamate: list[dict] = []
    citta: list[dict] = []

    async def di_un_luogo(nome, latitudine, longitudine, days=2):
        chiamate.append({"nome": nome, "lat": latitudine, "lon": longitudine})
        return {
            "success": True,
            "localita": nome,
            "adesso": {"temperatura": "18°C", "condizione": "Sereno"},
            "previsioni": [{"temp_max": 20, "temp_min": 12}],
        }

    async def execute_tool(nome, argomenti):
        citta.append({"tool": nome, **argomenti})
        return {
            "success": True,
            "localita": f"{argomenti.get('location')} (IT)",
            "adesso": {"temperatura": "9°C", "condizione": "Nuvoloso"},
            "previsioni": [{"temp_max": 12, "temp_min": 4}],
        }

    monkeypatch.setattr(modulo, "meteo_di_un_luogo", di_un_luogo)
    monkeypatch.setattr(modulo, "execute_tool", execute_tool)
    return {"luoghi": chiamate, "citta": citta}


def _richiesta(testo: str) -> Richiesta:
    return Richiesta(testo=testo, memoria=ConversationMemory())


async def test_il_luogo_nominato_nella_frase_vince(meteo):
    risposta = await instrada(_richiesta("che tempo fa nella casa al mare"))
    assert [c["nome"] for c in meteo["luoghi"]] == ["Casa al mare"], "ha risposto per un altro luogo"
    assert meteo["citta"] == [], "ha interrogato anche la citta' predefinita"
    assert "Casa al mare" in risposta.testo


async def test_il_nome_piu_lungo_vince_su_quello_contenuto():
    assert luoghi.nominato_nella_frase("com'e' il tempo a casa al mare?")["nome"] == "Casa al mare"
    assert luoghi.nominato_nella_frase("com'e' il tempo a casa?")["nome"] == "Casa"
    assert luoghi.nominato_nella_frase("com'e' il tempo a casalinga?") is None, "e' scattato su mezza parola"


async def test_senza_un_luogo_nominato_si_usa_la_casa_principale(meteo):
    risposta = await instrada(_richiesta("che tempo fa oggi"))
    assert [c["nome"] for c in meteo["luoghi"]] == ["Casa"]
    assert "Casa" in risposta.testo


async def test_chi_chiede_di_un_altra_citta_non_riceve_la_sua_casa(meteo):
    await instrada(_richiesta("che tempo fa a Milano"))
    assert meteo["luoghi"] == []
    assert [c["location"] for c in meteo["citta"]] == ["Milano"]


async def test_senza_luoghi_registrati_resta_il_comportamento_di_prima(meteo):
    deposito.sostituisci_tutto([])
    await instrada(_richiesta("che tempo fa oggi"))
    assert meteo["luoghi"] == []
    assert len(meteo["citta"]) == 1


async def test_le_azioni_riportano_il_nome_del_luogo_non_le_coordinate(meteo):
    richiesta = _richiesta("che tempo fa nella casa al mare")
    await instrada(richiesta)
    azioni = json.dumps(richiesta.azioni, default=str)
    assert "Casa al mare" in azioni
    for cifra in ("44.12", "12.23", "41.9", "12.49"):
        assert cifra not in azioni, f"le azioni riportano le coordinate ({cifra})"


async def test_a_open_meteo_vanno_le_coordinate_arrotondate(monkeypatch):
    viste: list[tuple[float, float]] = []

    async def finto_meteo(client, lat, lon, localita, days):
        viste.append((lat, lon))
        return {"success": True, "localita": localita}

    monkeypatch.setattr(weather, "_meteo", finto_meteo)

    esito = await weather.meteo_di_un_luogo("Casa al mare", *MARE)

    assert viste == [(44.12, 12.23)], "a un servizio di terzi sono arrivate coordinate precise"
    assert esito["localita"] == "Casa al mare"
    assert "44.12" not in json.dumps(esito)


async def test_un_errore_del_servizio_non_riporta_le_coordinate(monkeypatch):
    async def rotto(client, lat, lon, localita, days):
        raise RuntimeError("servizio non raggiungibile")

    monkeypatch.setattr(weather, "_meteo", rotto)
    esito = await weather.meteo_di_un_luogo("Casa al mare", *MARE)
    assert esito["success"] is False and "44.1" not in json.dumps(esito)
