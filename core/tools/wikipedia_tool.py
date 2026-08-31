import httpx
import logging
import urllib.parse
from typing import Dict, Any

logger = logging.getLogger(__name__)

# User-Agent conforme alle policy Wikimedia API
WIKI_HEADERS = {
    "User-Agent": "ShinraAssistant/1.0 (https://shinra.local; contact@shinra.local)",
    "Accept": "application/json"
}

async def search_wikipedia(query: str, language: str = "it") -> Dict[str, Any]:
    """
    Cerca spiegazioni, definizioni, biografie o cenni storici ed enciclopedici su Wikipedia (in lingua italiana).
    
    Args:
        query: Il termine, concetto o persona da cercare (es. 'Olocausto', 'Intelligenza Artificiale', 'Teoria della relatività').
        language: Lingua di Wikipedia (default 'it').
    """
    clean_query = query.strip()
    
    try:
        encoded_query = urllib.parse.quote(clean_query.capitalize().replace(" ", "_"))
        api_url = f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded_query}"
        
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(api_url, headers=WIKI_HEADERS)
            
            if res.status_code == 200:
                data = res.json()
                return {
                    "success": True,
                    "termine": data.get("title", clean_query),
                    "descrizione_breve": data.get("description", ""),
                    "estratto": data.get("extract", "Nessun estratto disponibile.")
                }

            # Fallback con action=query
            search_api = f"https://{language}.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": clean_query,
                "format": "json",
                "srlimit": 1
            }
            search_res = await client.get(search_api, params=params, headers=WIKI_HEADERS)
            if search_res.status_code == 200:
                search_data = search_res.json()
                results = search_data.get("query", {}).get("search", [])
                if results:
                    title = results[0]["title"]
                    encoded_title = urllib.parse.quote(title.replace(" ", "_"))
                    summary_res = await client.get(f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded_title}", headers=WIKI_HEADERS)
                    if summary_res.status_code == 200:
                        s_data = summary_res.json()
                        return {
                            "success": True,
                            "termine": s_data.get("title", title),
                            "descrizione_breve": s_data.get("description", ""),
                            "estratto": s_data.get("extract", "")
                        }
                    snippet = results[0].get("snippet", "").replace('<span class="searchmatch">', "").replace("</span>", "")
                    return {
                        "success": True,
                        "termine": title,
                        "estratto": snippet
                    }

            return {"success": False, "message": f"Nessuna informazione enciclopedica trovata per '{clean_query}'."}

    except Exception as e:
        logger.error(f"Errore ricerca Wikipedia per {clean_query}: {e}")
        return {"success": False, "error": str(e), "message": f"Impossibile consultare Wikipedia per '{clean_query}'."}
