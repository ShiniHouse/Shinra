import asyncio
import logging
import urllib.parse
from typing import Any, Dict, Optional, Sequence

import feedparser
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Le fonti di partenza, usate soltanto quando l'elenco configurato e' vuoto:
# un'installazione appena fatta, o un archivio che non risponde. Non sono piu'
# «le fonti»: quelle stanno in `data/sources.json` e si gestiscono dalla
# scheda «Fonti & Notizie». Fino alla v0.3.0 questo dizionario *era* l'unica
# verita', e il gestore nell'interfaccia — venti testate, interruttori,
# categorie — non aveva alcun effetto: si disattivava ANSA Politica e le
# notizie di politica arrivavano lo stesso.
FONTI_DI_RIPIEGO = {
    "mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
    "italia": "https://www.ansa.it/sito/notizie/cronaca/cronaca_rss.xml",
    "economia": "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "politica": "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
    "tecnologia": "https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml",
    "generale": "https://www.ansa.it/sito/ansait_rss.xml",
}


def fonti_attive(categorie: Sequence[str]) -> list[dict[str, Any]]:
    """Le fonti accese, fra quelle delle categorie richieste.

    `enabled` assente vale acceso: una fonte aggiunta a mano senza quel campo
    deve funzionare, non sparire in silenzio.
    """
    from shinra.infra.data_store import data_store

    volute = {(c or "").strip().lower() for c in categorie if (c or "").strip()}
    if not volute:
        volute = {"generale"}

    try:
        tutte = data_store.get_sources()
    except Exception as e:  # l'archivio puo' non esserci ancora
        logger.warning("Fonti non leggibili (%s): uso quelle di ripiego.", e)
        return []

    return [
        f for f in tutte if f.get("enabled", True) and (f.get("category") or "").strip().lower() in volute
    ]


def _indirizzi(categorie: Sequence[str]) -> tuple[list[str], bool]:
    """Gli indirizzi da leggere, e se sono quelli configurati o il ripiego."""
    from shinra.infra.data_store import data_store

    attive = fonti_attive(categorie)
    if attive:
        return [f["url"] for f in attive if f.get("url")], True

    # Nessuna fonte accesa. Due casi molto diversi: non ce n'e' nessuna
    # configurata — installazione nuova, si ripiega — oppure ci sono e le ha
    # spente l'utente, e allora spegnerle deve avere effetto. Fingere di
    # non capire la differenza e' esattamente il difetto che questa issue
    # chiude.
    try:
        configurate = bool(data_store.get_sources())
    except Exception:
        configurate = False
    if configurate:
        return [], True

    volute = [(c or "").strip().lower() for c in categorie] or ["generale"]
    ripiego = [FONTI_DI_RIPIEGO.get(c) for c in volute]
    return [u for u in ripiego if u] or [FONTI_DI_RIPIEGO["generale"]], False


def _clean_html(raw_html: str) -> str:
    """Rimuove tag HTML dai sommari RSS."""
    if not raw_html:
        return ""
    return BeautifulSoup(raw_html, "html.parser").get_text(separator=" ", strip=True)


async def get_latest_news(
    category: str = "generale",
    max_items: int = 4,
    categorie: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Le ultime notizie dalle fonti accese.

    `categorie` ha la precedenza su `category`: e' la strada che porta qui le
    preferenze del profilo che ha fatto la domanda. Chi chiede le notizie
    senza dire quali le riceve secondo cio' che ha scelto, e due persone di
    casa con interessi diversi ricevono rassegne diverse — che e' il motivo
    per cui quel campo esisteva nell'anagrafica fin dalla prima versione,
    senza che nessuno lo leggesse.
    """
    volute = list(categorie) if categorie else [category]
    indirizzi, configurate = _indirizzi(volute)

    if not indirizzi and configurate:
        etichetta = ", ".join(volute)
        return {
            "success": False,
            "categoria": etichetta,
            "message": (
                f"Nessuna fonte attiva per {etichetta}. Puoi riaccenderne una "
                "dalla scheda «Fonti & Notizie»."
            ),
        }

    try:
        letture = await asyncio.gather(*(_leggi_feed(u) for u in indirizzi), return_exceptions=True)
        articoli = _mescola([voci for voci in letture if isinstance(voci, list)], max_items)

        if not articoli:
            return await search_web(f"ultime notizie {volute[0]}", max_results=max_items)

        return {"success": True, "categoria": ", ".join(volute), "notizie": articoli}
    except Exception as e:
        logger.error("Errore recupero news RSS (%s): %s", volute, e)
        return await search_web(f"ultime notizie {volute[0]}", max_results=max_items)


async def _leggi_feed(indirizzo: str) -> list[dict[str, Any]]:
    def _analizza():
        return feedparser.parse(indirizzo)

    parsed = await asyncio.get_event_loop().run_in_executor(None, _analizza)
    return [
        {
            "titolo": voce.get("title", ""),
            "sommario": _clean_html(voce.get("summary", "")),
            "data": voce.get("published", ""),
        }
        for voce in parsed.entries
    ]


def _mescola(gruppi: list[list[dict[str, Any]]], quanti: int) -> list[dict[str, Any]]:
    """Una notizia per fonte a giro, finche' non bastano.

    Prendere le prime quattro dalla prima fonte significa che con due fonti
    accese se ne sente una sola — e chi ha acceso la seconda ha ragione di
    aspettarsi il contrario.
    """
    fuori: list[dict[str, Any]] = []
    for posizione in range(max((len(g) for g in gruppi), default=0)):
        for gruppo in gruppi:
            if posizione < len(gruppo) and gruppo[posizione].get("titolo"):
                fuori.append(gruppo[posizione])
                if len(fuori) >= quanti:
                    return fuori
    return fuori


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
