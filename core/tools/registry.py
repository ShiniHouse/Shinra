import inspect
import json
import logging
from typing import Callable, Dict, Any, List

from core.tools.ha_tools import control_device, get_home_status, activate_scene_or_routine, activate_mode
from core.tools.weather import get_weather
from core.tools.news_search import get_latest_news, search_web
from core.tools.wikipedia_tool import search_wikipedia
from core.tools.reminders import add_reminder, list_reminders

logger = logging.getLogger(__name__)

# Mappa funzioni registrate
TOOL_HANDLERS: Dict[str, Callable] = {
    "control_device": control_device,
    "get_home_status": get_home_status,
    "activate_scene_or_routine": activate_scene_or_routine,
    "activate_mode": activate_mode,
    "get_weather": get_weather,
    "get_latest_news": get_latest_news,
    "search_web": search_web,
    "search_wikipedia": search_wikipedia,
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
}

# Schemi compatibili con Ollama / OpenAI Tools
TOOLS_SCHEMA: List[Dict[str, Any]] = [
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
                        "description": "Nome della città o comune (es. 'Roma', 'Milano', 'Bologna')."
                    },
                    "days": {
                        "type": "integer",
                        "description": "Numero di giorni da prevedere (default 2 per oggi e domani)."
                    }
                },
                "required": ["location"]
            }
        }
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
                        "description": "Il termine o concetto da cercare (es. 'Olocausto', 'Legge di bilancio', 'Albert Einstein')."
                    }
                },
                "required": ["query"]
            }
        }
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
                        "description": "La query di ricerca su internet (es. 'approvazione legge di bilancio novità', 'cosa è successo oggi nel mondo')."
                    }
                },
                "required": ["query"]
            }
        }
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
                        "description": "Categoria delle notizie desiderata."
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Accende, spegne o regola dispositivi della casa connessi a Home Assistant tramite ID entità o nome/alias naturale (luci, prese, termostato, clima, tapparelle).",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "L'ID o alias del dispositivo (es. 'light.salotto', 'lampadario salotto', 'clima camera', 'switch.tv')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["turn_on", "turn_off", "toggle", "set_temperature", "open", "close"],
                        "description": "Azione da eseguire sul dispositivo."
                    },
                    "brightness": {
                        "type": "integer",
                        "description": "Percentuale di luminosità per le luci da 1 a 100."
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperatura target per climatizzatore o termostato."
                    },
                    "color_name": {
                        "type": "string",
                        "description": "Colore per luci RGB (es. 'rosso', 'blu', 'verde', 'bianco caldo')."
                    }
                },
                "required": ["entity_id", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_home_status",
            "description": "Interroga Home Assistant per conoscere lo stato corrente dei dispositivi di casa (es. quali luci sono accese, temperature rilevate dai sensori).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_domain": {
                        "type": "string",
                        "enum": ["light", "climate", "sensor", "switch", "cover"],
                        "description": "Opzionale: filtra per tipologia di dispositivo."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_mode",
            "description": "Attiva una modalità o scenario personalizzato configurato in Shinra (es. 'Cinema', 'Buonanotte', 'Buongiorno', 'Lavoro').",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode_name": {
                        "type": "string",
                        "description": "Il nome della modalità da attivare (es. 'Cinema', 'Buonanotte', 'Buongiorno', 'Lavoro')."
                    }
                },
                "required": ["mode_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "activate_scene_or_routine",
            "description": "Attiva una scena o routine domotica programmata in Home Assistant (es. 'scene.buonanotte', 'scene.cinema').",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "ID dell'entità scena o script (es. 'scene.buonanotte')."
                    }
                },
                "required": ["entity_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": "Salva un promemoria o una nota per l'utente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Contenuto del promemoria."
                    },
                    "time_info": {
                        "type": "string",
                        "description": "Quando ricordare (es. 'domani mattina', 'alle 18:00', 'stasera')."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Elenca tutti i promemoria salvati e attivi.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Esegue un tool registrato passando gli argomenti forniti dal modello LLM."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"success": False, "error": f"Tool '{tool_name}' non trovato nel registro."}
    
    try:
        if inspect.iscoroutinefunction(handler):
            return await handler(**arguments)
        else:
            return handler(**arguments)
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione del tool {tool_name} con args {arguments}: {e}")
        return {"success": False, "error": str(e)}
