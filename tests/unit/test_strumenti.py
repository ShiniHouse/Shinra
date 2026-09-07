"""Come leggiamo cio' che ci rispondono i servizi esterni.

I test che chiamano davvero Open-Meteo, Wikipedia e i feed ANSA stanno in
`tests/integration/` e sono marcati `network`: girano a mano, non in CI,
perche' una build non deve dipendere da quattro servizi altrui.

Questi invece verificano **il nostro codice**, con le risposte simulate: che
sappiamo leggere la forma che quei servizi restituiscono, e soprattutto che
un servizio giu' o cambiato non faccia cadere l'assistente. E' la parte che
si rompe davvero, ed e' l'unica che possiamo verificare a ogni commit.

Riferimento: issue #10.
"""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import respx

from core.tools.weather import get_weather
from core.tools.wikipedia_tool import search_wikipedia

GEOCODIFICA = {
    "results": [{"name": "Reggio Emilia", "latitude": 44.7, "longitude": 10.63, "country": "Italia"}]
}
PREVISIONI = {
    "current": {
        "temperature_2m": 9.4,
        "relative_humidity_2m": 71,
        "apparent_temperature": 7.1,
        "weather_code": 3,
        "wind_speed_10m": 6.2,
    },
    "daily": {
        "time": ["2026-09-07", "2026-09-08"],
        "weather_code": [3, 61],
        "temperature_2m_max": [17.2, 15.0],
        "temperature_2m_min": [8.1, 9.3],
        "precipitation_probability_max": [10, 80],
        "sunrise": ["2026-09-07T06:52", "2026-09-08T06:53"],
        "sunset": ["2026-09-07T19:48", "2026-09-08T19:46"],
    },
}


# ------------------------------------------------------------------- meteo


async def test_leggiamo_la_risposta_di_open_meteo():
    with respx.mock:
        respx.get(url__startswith="https://geocoding-api.open-meteo.com").mock(
            return_value=httpx.Response(200, json=GEOCODIFICA)
        )
        respx.get(url__startswith="https://api.open-meteo.com").mock(
            return_value=httpx.Response(200, json=PREVISIONI)
        )

        esito = await get_weather("Reggio Emilia", days=2)

    assert esito["success"] is True
    assert "Reggio Emilia" in esito["localita"]
    assert esito["adesso"]["temperatura"]
    assert len(esito["previsioni"]) == 2
    assert esito["previsioni"][0]["temp_max"] == 17.2


async def test_una_citta_che_la_geocodifica_non_conosce_non_esplode():
    """E' il ripiego su cui conta l'intento del meteo (issue #17): se qui
    tornasse un'eccezione invece di `success: False`, «che tempo fa a casa
    mia» farebbe cadere la richiesta."""
    with respx.mock:
        respx.get(url__startswith="https://geocoding-api.open-meteo.com").mock(
            return_value=httpx.Response(200, json={"results": []})
        )

        esito = await get_weather("Città Inventata", days=1)

    assert esito["success"] is False
    assert esito.get("error") or esito.get("message")


@pytest.mark.parametrize("codice", [403, 500, 503])
async def test_un_servizio_meteo_giu_non_ferma_l_assistente(codice):
    """Open-Meteo ha limiti d'uso e ogni tanto risponde 403. Non deve
    diventare un errore in faccia a chi ha solo chiesto che tempo fa."""
    with respx.mock:
        respx.get(url__startswith="https://geocoding-api.open-meteo.com").mock(
            return_value=httpx.Response(codice, text="no")
        )

        esito = await get_weather("Roma", days=1)

    assert esito["success"] is False


async def test_una_risposta_senza_i_campi_attesi_non_esplode():
    """Un'API che cambia forma e' il modo piu' comune in cui un'integrazione
    si rompe, e succede senza preavviso."""
    with respx.mock:
        respx.get(url__startswith="https://geocoding-api.open-meteo.com").mock(
            return_value=httpx.Response(200, json=GEOCODIFICA)
        )
        respx.get(url__startswith="https://api.open-meteo.com").mock(
            return_value=httpx.Response(200, json={"qualcosa": "di diverso"})
        )

        esito = await get_weather("Reggio Emilia", days=1)

    assert isinstance(esito, dict)  # qualunque cosa risponda, non solleva


# --------------------------------------------------------------- wikipedia


async def test_leggiamo_l_estratto_di_wikipedia():
    with respx.mock:
        respx.get(url__regex=r".*wikipedia\.org/api/rest_v1/page/summary/.*").mock(
            return_value=httpx.Response(
                200,
                json={
                    "title": "Bologna",
                    "extract": "Bologna e' un comune italiano di circa 390 000 abitanti, "
                    "capoluogo dell'omonima citta' metropolitana in Emilia-Romagna.",
                },
            )
        )

        esito = await search_wikipedia("Bologna")

    assert esito["success"] is True
    assert "Bologna" in esito["estratto"]


async def test_un_termine_inesistente_non_esplode():
    with respx.mock:
        respx.get(url__regex=r".*wikipedia\.org.*").mock(return_value=httpx.Response(404, json={}))

        esito = await search_wikipedia("qwertyuiop-non-esiste")

    assert esito.get("success") is not True
    assert isinstance(esito, dict)


# ------------------------------------------------------------------ notizie


async def test_le_notizie_leggono_un_feed_rss(monkeypatch):
    """feedparser non passa da httpx, quindi si sostituisce lui: cio' che
    conta e' che sappiamo estrarre i titoli dalla struttura che restituisce."""
    import core.tools.news_search as modulo

    finto = SimpleNamespace(
        entries=[
            {"title": "Prima notizia", "link": "https://esempio.it/1", "published": "oggi"},
            {"title": "Seconda notizia", "link": "https://esempio.it/2", "published": "oggi"},
        ],
        bozo=False,
    )
    monkeypatch.setattr(modulo.feedparser, "parse", lambda url: finto)

    esito = await modulo.get_latest_news("mondo", max_items=2)

    assert esito["success"] is True
    assert [n["titolo"] for n in esito["notizie"]] == ["Prima notizia", "Seconda notizia"]


async def test_un_feed_vuoto_non_esplode(monkeypatch):
    """Un feed irraggiungibile o malformato capita: non deve diventare un
    errore in faccia a chi ha chiesto le notizie."""
    import core.tools.news_search as modulo

    monkeypatch.setattr(modulo.feedparser, "parse", lambda url: SimpleNamespace(entries=[], bozo=True))

    esito = await modulo.get_latest_news("mondo", max_items=2)

    assert isinstance(esito, dict)
    assert esito.get("notizie", []) == [] or esito.get("success") is False
