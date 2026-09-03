import asyncio

from core.tools.news_search import get_latest_news, search_web
from core.tools.reminders import add_reminder, list_reminders
from core.tools.weather import get_weather
from core.tools.wikipedia_tool import search_wikipedia


async def main():
    print("=== 1. Test Tool Meteo (Open-Meteo) ===")
    w = await get_weather("Roma", days=2)
    print("Meteo Roma:", w.get("localita"), "| Adesso:", w.get("adesso"))
    print("Previsione:", w.get("previsioni"))

    print("\n=== 2. Test Tool Wikipedia (Definizioni/Storia) ===")
    wiki = await search_wikipedia("Olocausto")
    print("Wikipedia Termine:", wiki.get("termine"))
    print("Wikipedia Estratto:", str(wiki.get("estratto"))[:200] + "...")

    print("\n=== 3. Test Tool Notizie ANSA RSS & Web ===")
    news = await get_latest_news("mondo", max_items=2)
    print("Notizie Mondo:", news.get("categoria"), "| Conteggio:", len(news.get("notizie", [])))
    if news.get("notizie"):
        print("Prima notizia:", news["notizie"][0]["titolo"])

    print("\n=== 4. Test Tool Ricerca Web (Legge di Bilancio / Fatti) ===")
    web = await search_web("legge di bilancio novita", max_results=2)
    print("Web search success:", web.get("success"), "| Trovati:", len(web.get("risultati", [])))
    if web.get("risultati"):
        print("Primo risultato web:", web["risultati"][0]["titolo"])

    print("\n=== 5. Test Tool Promemoria ===")
    await add_reminder("Comprare il latte", "domani mattina")
    rems = await list_reminders()
    print("Promemoria:", rems)


if __name__ == "__main__":
    asyncio.run(main())
