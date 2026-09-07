"""Gli strumenti che escono su Internet, provati contro i servizi veri.

Sostituisce `test_tools.py`, che stava nella radice del progetto ed era uno
script di `print`: chiamava le API vere e stampava cio' che tornava. Non
verificava niente — nessuna asserzione — e non poteva girare in CI, perche'
avrebbe reso ogni build dipendente da quattro servizi esterni.

Questi test sono marcati `network` ed **esclusi dalla CI**
(`pytest -m "not network and not integration"`). Si eseguono a mano, quando
si sospetta che un servizio abbia cambiato risposta:

    pytest -m network -v

Non verificano il contenuto — «che tempo fa a Roma» cambia ogni ora — ma la
forma: che la chiamata riesca e che i campi che il resto del codice legge ci
siano davvero. E' l'unica cosa che ha senso chiedere a un servizio altrui, ed
e' anche quella che si rompe quando cambia un'API.

Riferimento: issue #10.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.network, pytest.mark.integration]


async def test_il_meteo_risponde_con_i_campi_che_leggiamo():
    from core.tools.weather import get_weather

    esito = await get_weather("Roma", days=2)

    assert esito.get("success") is True
    assert esito.get("localita")
    assert "temperatura" in esito.get("adesso", {})
    previsioni = esito.get("previsioni") or []
    assert previsioni and {"temp_max", "temp_min"} <= set(previsioni[0])


async def test_il_meteo_di_una_citta_composta():
    """Il difetto della issue #17 arrivava fin qui: se la geocodifica non
    riconosce «Reggio Emilia», l'intento ripiega e nessuno se ne accorge."""
    from core.tools.weather import get_weather

    esito = await get_weather("Reggio Emilia", days=1)

    assert esito.get("success") is True
    assert "reggio" in (esito.get("localita") or "").lower()


async def test_wikipedia_restituisce_un_estratto():
    from core.tools.wikipedia_tool import search_wikipedia

    esito = await search_wikipedia("Bologna")

    assert esito.get("success") is True
    assert len(esito.get("estratto") or "") > 50


async def test_le_notizie_arrivano_con_un_titolo():
    from core.tools.news_search import get_latest_news

    esito = await get_latest_news("mondo", max_items=2)

    assert esito.get("success") is True
    notizie = esito.get("notizie") or []
    assert notizie and notizie[0].get("titolo")


async def test_la_ricerca_web_risponde():
    from core.tools.news_search import search_web

    esito = await search_web("previsioni economiche italia", max_results=2)

    assert esito.get("success") is True
