import asyncio
import logging
import urllib.parse
from typing import Any, Dict

import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Feed RSS ANSA per notizie istantanee per categoria
RSS_FEEDS = {
    "mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
    "italia": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
    "economia": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    "tecnologia": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
    "generale": "https://www.ansa.it/sito/ansait_rss.xml",
}


def _clean_html(raw_html: str) -> str:
    """Rimuove tag HTML dai sommari RSS."""
    if not raw_html:
        return ""
    return BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)


async def get_latest_news(category: str = "generale", max_items: int = 4) -> Dict[str, Any]:
    """
    Recupera le ultimissime notizie in tempo reale per categoria (mondo, italia, economia, politica, tecnologia, generale).
    """
    try:
        feed_url = RSS_FEEDS.get(category.lower(), RSS_FEEDS["generale"])

        def _parse_feed():
            return feedparser.parse(feed_url)

        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, _parse_feed)

        articles = []
        for entry in parsed.entries[:max_items]:
            title = entry.get("title", "")
            summary = _clean_html(entry.get("summary", ""))
            pub_date = entry.get("published", "")
            articles.append({"titolo": title, "sommario": summary, "data": pub_date})

        if not articles:
            return await search_web(f"ultime notizie {category}", max_results=max_items)

        return {"success": True, "categoria": category, "notizie": articles}
    except Exception as e:
        logger.error(f"Errore recupero news RSS ({category}): {e}")
        return await search_web(f"ultime notizie {category}", max_results=max_items)


async def search_web(query: str, max_results: int = 4) -> Dict[str, Any]:
    """
    Effettua una ricerca notizie e attualità su internet in tempo reale (Google News & agenzie stampa).

    Args:
        query: Termine o domanda da cercare (es. 'approvazione legge di bilancio cosa prevede', 'ultime notizie mondo').
        max_results: Numero massimo di notizie/risultati da restituire (default 4).
    """
    try:
        encoded_query = urllib.parse.quote(query.strip())
        google_news_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=it&gl=IT&ceid=IT:it"

        def _fetch_google_news():
            return feedparser.parse(google_news_url)

        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(None, _fetch_google_news)

        results = []
        for entry in parsed.entries[:max_results]:
            title = entry.get("title", "")
            summary = _clean_html(entry.get("summary", ""))
            pub_date = entry.get("published", "")
            source = entry.get("source", {}).get("title", "News")

            results.append({"titolo": title, "estratto": summary, "data": pub_date, "fonte": source})

        if not results:
            return {"success": False, "message": f"Nessun risultato o notizia recente trovata per '{query}'."}

        return {"success": True, "query": query, "risultati": results}
    except Exception as e:
        logger.error(f"Errore ricerca web per {query}: {e}")
        return {"success": False, "error": str(e), "message": f"Errore durante la ricerca per '{query}'."}
