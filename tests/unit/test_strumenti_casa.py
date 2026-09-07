"""Gli strumenti che toccano davvero la casa.

`core/tools/ha_tools.py` era il modulo meno coperto del progetto — tredici
per cento — ed e' quello che accende le luci, cambia la temperatura, apre le
tapparelle ed esegue le routine. La copertura non e' un numero da far
salire: e' che qui dentro un errore si vede in salotto.

Nessuno di questi test tocca la rete: il client di Home Assistant e'
sostituito, e cio' che si verifica e' **quale servizio chiediamo e con quali
parametri**. E' esattamente la parte che si sbaglia.

Riferimento: issue #18.
"""

from __future__ import annotations

import pytest

from core.archivio import depositi
from core.tools import ha_tools


@pytest.fixture
def casa(monkeypatch):
    """Un client di Home Assistant che annota invece di chiamare."""
    chiamate: list[tuple[str, str, dict]] = []
    esito = {"success": True}

    class FintoClient:
        async def call_service(self, dominio, servizio, dati=None):
            chiamate.append((dominio, servizio, dati or {}))
            return dict(esito)

        async def get_states(self):
            return STATI

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: FintoClient())
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "lampadario salotto", "entity_id": "light.salotto_main"}]
    )
    return {"chiamate": chiamate, "esito": esito}


STATI = [
    {
        "entity_id": "sensor.salotto_temperatura",
        "state": "21.4",
        "attributes": {
            "friendly_name": "Salotto Temperatura",
            "device_class": "temperature",
            "unit_of_measurement": "°C",
        },
    },
    {
        "entity_id": "sensor.camera_temperatura",
        "state": "19.0",
        "attributes": {"friendly_name": "Camera Temperatura", "unit_of_measurement": "°C"},
    },
    {
        "entity_id": "sensor.umidita",
        "state": "55",
        "attributes": {"friendly_name": "Umidita", "unit_of_measurement": "%"},
    },
    {
        "entity_id": "sensor.guasto",
        "state": "unavailable",
        "attributes": {"friendly_name": "Sensore rotto", "device_class": "temperature"},
    },
    {"entity_id": "light.cucina", "state": "on", "attributes": {"friendly_name": "Luce cucina"}},
]


# ------------------------------------------------------------- accendi/spegni


async def test_accendere_una_luce_chiama_il_servizio_giusto(casa):
    esito = await ha_tools.control_device("light.cucina", "turn_on")

    assert esito["success"] is True
    assert casa["chiamate"] == [("light", "turn_on", {"entity_id": "light.cucina"})]


async def test_l_alias_viene_risolto_prima_di_chiamare(casa):
    """«lampadario salotto» non e' un entity_id: se la risoluzione saltasse,
    Home Assistant riceverebbe un nome che non esiste e non direbbe niente."""
    await ha_tools.control_device("lampadario salotto", "turn_on")

    assert casa["chiamate"][0][2]["entity_id"] == "light.salotto_main"


async def test_la_luminosita_viene_passata_in_percentuale(casa):
    await ha_tools.control_device("light.cucina", "turn_on", brightness=40)

    assert casa["chiamate"][0][2]["brightness_pct"] == 40


@pytest.mark.parametrize("richiesta,attesa", [(0, 1), (-10, 1), (500, 100)])
async def test_la_luminosita_resta_fra_uno_e_cento(casa, richiesta, attesa):
    """Un modello che inventa `brightness: 500` non deve arrivare a Home
    Assistant: il limite si applica qui, dove si sa cosa vuol dire."""
    await ha_tools.control_device("light.cucina", "turn_on", brightness=richiesta)

    assert casa["chiamate"][0][2]["brightness_pct"] == attesa


async def test_impostare_la_temperatura_va_sul_dominio_clima(casa):
    """L'entita' puo' essere scritta come `climate.x`, ma anche no: il
    dominio giusto lo decide l'azione."""
    await ha_tools.control_device("climate.camera", "set_temperature", temperature=21)

    dominio, servizio, dati = casa["chiamate"][0]
    assert (dominio, servizio) == ("climate", "set_temperature")
    assert dati["temperature"] == 21.0


@pytest.mark.parametrize("azione,servizio", [("open", "open_cover"), ("close", "close_cover")])
async def test_le_tapparelle_usano_i_servizi_delle_cover(casa, azione, servizio):
    await ha_tools.control_device("cover.salotto", azione)

    assert casa["chiamate"][0][0] == "cover"
    assert casa["chiamate"][0][1] == servizio


async def test_un_comando_fallito_lo_dice(casa):
    casa["esito"].clear()
    casa["esito"].update({"success": False, "error": "Home Assistant non risponde"})

    esito = await ha_tools.control_device("light.cucina", "turn_on")

    assert esito["success"] is False
    assert "non risponde" in esito["error"]


# ------------------------------------------------------- temperatura interna


async def test_la_temperatura_interna_legge_solo_i_sensori_di_temperatura(casa):
    esito = await ha_tools.get_indoor_temperature()

    nomi = [letture["nome"] for letture in esito["letture"]]
    assert esito["success"] is True
    assert "Salotto Temperatura" in nomi
    assert "Camera Temperatura" in nomi  # riconosciuto dall'unita', senza device_class
    assert "Umidita" not in nomi


async def test_un_sensore_non_disponibile_non_viene_riportato(casa):
    """Meglio dire «non trovo un sensore» che riferire «unavailable gradi»."""
    esito = await ha_tools.get_indoor_temperature()

    assert all(letture["valore"] != "unavailable" for letture in esito["letture"])


async def test_si_puo_chiedere_una_stanza_sola(casa):
    esito = await ha_tools.get_indoor_temperature("salotto")

    assert [letture["nome"] for letture in esito["letture"]] == ["Salotto Temperatura"]


async def test_senza_home_assistant_lo_dice_invece_di_inventare(monkeypatch):
    class ClientMuto:
        async def get_states(self):
            return []

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: ClientMuto())

    esito = await ha_tools.get_indoor_temperature()

    assert esito["success"] is False
    assert "Home Assistant" in esito["message"]


# ------------------------------------------------------------------ routine


async def test_una_modalita_esegue_le_sue_azioni(casa):
    depositi.modalita.sostituisci_tutto(
        [
            {
                "id": "cinema",
                "name": "Cinema",
                "enabled": True,
                "trigger_phrases": ["modalità cinema"],
                "actions": [
                    {
                        "type": "ha_service",
                        "domain": "light",
                        "service": "turn_off",
                        "entity_id": "light.salotto_main",
                    },
                    {
                        "type": "ha_service",
                        "domain": "cover",
                        "service": "close_cover",
                        "entity_id": "cover.salotto",
                    },
                ],
            }
        ]
    )

    esito = await ha_tools.activate_mode("Cinema")

    assert esito.get("success") is not False
    servizi = [(d, s) for d, s, _ in casa["chiamate"]]
    assert ("light", "turn_off") in servizi
    assert ("cover", "close_cover") in servizi


async def test_una_modalita_inesistente_non_esplode(casa):
    depositi.modalita.sostituisci_tutto([])

    esito = await ha_tools.activate_mode("Non esiste")

    assert esito["success"] is False
    assert casa["chiamate"] == []


async def test_lo_stato_della_casa_riporta_i_dispositivi(casa):
    esito = await ha_tools.get_home_status()

    assert esito.get("success") is not False
    testo = str(esito)
    assert "light.cucina" in testo or "Luce cucina" in testo
