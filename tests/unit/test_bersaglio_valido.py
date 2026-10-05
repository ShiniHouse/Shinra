"""Un comando senza un bersaglio valido non parte, e chiede quale.

Dall'analisi del giro con gli agenti (banco/risultati/2026-10-05-i5-8500t-agenti-ANALISI.md): «apri» chiamava
`comanda_tapparella` con `entity_id` vuoto, «accendi la luce della cantina» agiva su `light.cantina`, che non
esiste. Home Assistant risponde 200 a un servizio su una cosa che non c'e', e Shinra annunciava «fatto». Non si
puo' contare sul modello per accorgersene: il controllo sta nell'esecuzione.
"""

from __future__ import annotations

import pytest

from shinra.skills import ha_tools
from shinra.skills.entita import EntitaSconosciuta, verifica

STATI = [
    {"entity_id": "light.cucina", "state": "off", "attributes": {"friendly_name": "Luce cucina"}},
    {"entity_id": "switch.caffettiera", "state": "off", "attributes": {"friendly_name": "Caffettiera"}},
    {"entity_id": "cover.salotto", "state": "open", "attributes": {"friendly_name": "Tapparella salotto"}},
]


@pytest.fixture
def casa(monkeypatch):
    """Home Assistant che annota invece di eseguire, con tre dispositivi."""
    chiamate: list[tuple[str, str, dict]] = []

    class FintoClient:
        async def call_service(self, dominio, servizio, dati=None):
            chiamate.append((dominio, servizio, dati or {}))
            return {"success": True}

        async def stati_correnti(self):
            return list(STATI)

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: FintoClient())
    return chiamate


async def test_un_dispositivo_che_non_esiste_non_viene_comandato(casa):
    esito = await ha_tools.control_device("light.cantina", "turn_on")

    assert esito["success"] is False
    assert "light.cantina" in esito["message"] or "cantina" in esito["message"]
    assert casa == [], "ha chiamato Home Assistant per una cosa che non c'e'"


async def test_il_nome_sbagliato_propone_quello_giusto(casa):
    esito = await ha_tools.control_device("light.cucina_nuova", "turn_on")

    assert esito["success"] is False and "light.cucina" in esito["message"]
    assert casa == []


async def test_un_riferimento_vuoto_chiede_quale_dispositivo(casa):
    esito = await ha_tools.control_device("", "turn_on")

    assert esito["success"] is False and "Quale?" in esito["message"]
    assert casa == []


async def test_un_dispositivo_che_esiste_parte(casa):
    esito = await ha_tools.control_device("light.cucina", "turn_on")

    assert esito["success"] is True
    assert casa[0][2]["entity_id"] == "light.cucina"


async def test_un_riferimento_vuoto_non_passa_nemmeno_se_la_casa_non_risponde(monkeypatch):
    """Con Home Assistant spento il controllo dell'esistenza lascia passare (e' voluto), ma un comando
    senza destinatario non parte comunque."""

    class Muto:
        async def stati_correnti(self):
            return []

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: Muto())

    with pytest.raises(EntitaSconosciuta, match="Quale"):
        await verifica("   ", {"light"})


async def test_un_dispositivo_di_un_tipo_sbagliato_per_lo_strumento_viene_rifiutato(casa):
    with pytest.raises(EntitaSconosciuta, match="light"):
        await verifica("cover.salotto", {"light"})
