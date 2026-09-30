"""Meteo, notizie, ricerca sul web e enciclopedia."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.news_search import get_latest_news, search_web
from shinra.skills.weather import get_weather
from shinra.skills.wikipedia_tool import search_wikipedia

GESTORI: Dict[str, Callable] = {
    "get_weather": get_weather,
    "search_wikipedia": search_wikipedia,
    "search_web": search_web,
    "get_latest_news": get_latest_news,
}

SCHEMI: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Ottiene le previsioni meteo dettagliate (attuali, oggi, domani e prossimi giorni) per qualsiasi città o località.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Nome della città o comune (es. 'Roma', 'Milano', 'Bologna').",
                    },
                    "days": {
                        "type": "integer",
                        "description": "Numero di giorni da prevedere (default 2 per oggi e domani).",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_wikipedia",
            "description": "Cerca definizioni, significato di termini, spiegazioni storiche, scientifiche, culturali o biografie enciclopediche in lingua italiana.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Il termine o concetto da cercare (es. 'Olocausto', 'Legge di bilancio', 'Albert Einstein').",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Effettua una ricerca su internet in tempo reale per novità, eventi recenti, leggi approvate, informazioni dell'ultima ora non presenti nella memoria statica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La query di ricerca su internet (es. 'approvazione legge di bilancio novità', 'cosa è successo oggi nel mondo').",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_latest_news",
            "description": "Recupera le notizie del giorno in tempo reale da agenzie stampa per categoria (mondo, italia, economia, politica, tecnologia, generale).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["mondo", "italia", "economia", "politica", "tecnologia", "generale"],
                        "description": "Categoria delle notizie desiderata.",
                    }
                },
                "required": ["category"],
            },
        },
    },
]
