import inspect
import logging
from typing import Any, Callable, Dict, List

from shinra.services import registro
from shinra.services.permessi import PermessoNegato
from shinra.skills.clima import comanda_clima, stato_clima
from shinra.skills.domini_casa import (
    comanda_aspirapolvere,
    comanda_media,
    comanda_serratura,
    comanda_ventilatore,
)
from shinra.skills.ha_tools import (
    activate_mode,
    activate_scene_or_routine,
    control_device,
    get_home_status,
    get_indoor_temperature,
)
from shinra.skills.news_search import get_latest_news, search_web
from shinra.skills.reminders import add_reminder, list_reminders
from shinra.skills.sicurezza_casa import comanda_allarme, stato_aperture
from shinra.skills.simulazione import comanda_simulazione
from shinra.skills.tapparelle import comanda_tapparella, stato_tapparella
from shinra.skills.weather import get_weather
from shinra.skills.wikipedia_tool import search_wikipedia

logger = logging.getLogger(__name__)

# Mappa funzioni registrate
TOOL_HANDLERS: Dict[str, Callable] = {
    "control_device": control_device,
    "get_home_status": get_home_status,
    "get_indoor_temperature": get_indoor_temperature,
    "activate_scene_or_routine": activate_scene_or_routine,
    "activate_mode": activate_mode,
    "get_weather": get_weather,
    "get_latest_news": get_latest_news,
    "search_web": search_web,
    "search_wikipedia": search_wikipedia,
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
    # I quattro domini che l'interfaccia mostrava e nessuno sapeva
    # comandare (issue #20).
    "comanda_serratura": comanda_serratura,
    "comanda_media": comanda_media,
    "comanda_aspirapolvere": comanda_aspirapolvere,
    "comanda_ventilatore": comanda_ventilatore,
    # L'allarme e le aperture (issue #23).
    "comanda_allarme": comanda_allarme,
    "stato_aperture": stato_aperture,
    "comanda_simulazione": comanda_simulazione,
    # Clima e tapparelle per intero: modalita', ventola, umidita',
    # posizione percentuale e lamelle (issue #21).
    "comanda_clima": comanda_clima,
    "stato_clima": stato_clima,
    "comanda_tapparella": comanda_tapparella,
    "stato_tapparella": stato_tapparella,
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
                        "description": "L'ID o alias del dispositivo (es. 'light.salotto', 'lampadario salotto', 'clima camera', 'switch.tv').",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["turn_on", "turn_off", "toggle", "set_temperature", "open", "close"],
                        "description": "Azione da eseguire sul dispositivo.",
                    },
                    "brightness": {
                        "type": "integer",
                        "description": "Percentuale di luminosità per le luci da 1 a 100.",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperatura target per climatizzatore o termostato.",
                    },
                    "color_name": {
                        "type": "string",
                        "description": "Colore per luci RGB (es. 'rosso', 'blu', 'verde', 'bianco caldo').",
                    },
                },
                "required": ["entity_id", "action"],
            },
        },
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
                        "description": "Opzionale: filtra per tipologia di dispositivo.",
                    }
                },
            },
        },
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
                        "description": "Il nome della modalità da attivare (es. 'Cinema', 'Buonanotte', 'Buongiorno', 'Lavoro').",
                    }
                },
                "required": ["mode_name"],
            },
        },
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
                        "description": "ID dell'entità scena o script (es. 'scene.buonanotte').",
                    }
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": "Salva un promemoria o una nota per l'utente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Contenuto del promemoria."},
                    "time_info": {
                        "type": "string",
                        "description": "Quando ricordare (es. 'domani mattina', 'alle 18:00', 'stasera').",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_reminders",
            "description": "Elenca tutti i promemoria salvati e attivi.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_serratura",
            "description": (
                "Chiude, apre o riferisce lo stato di una serratura. "
                "APRIRE una serratura richiede sempre la conferma esplicita della "
                "persona: alla prima richiesta rispondi riportando la domanda di "
                "conferma e attendi che confermi, poi richiama questo tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Entita' o nome della serratura, es. 'lock.porta_ingresso' o 'porta di casa'.",
                    },
                    "azione": {
                        "type": "string",
                        "enum": ["blocca", "sblocca", "stato"],
                        "description": "Cosa fare: chiudere, aprire, o dire com'e' messa.",
                    },
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_media",
            "description": "Controlla un media player: riproduzione, pausa, traccia successiva o precedente, volume, sorgente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entita' o nome del media player."},
                    "azione": {
                        "type": "string",
                        "enum": [
                            "riproduci",
                            "pausa",
                            "ferma",
                            "successiva",
                            "precedente",
                            "accendi",
                            "spegni",
                            "volume",
                            "sorgente",
                        ],
                    },
                    "volume": {
                        "type": "integer",
                        "description": "Volume da 0 a 100, solo con azione 'volume'.",
                    },
                    "sorgente": {
                        "type": "string",
                        "description": "Nome della sorgente, solo con azione 'sorgente'.",
                    },
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_aspirapolvere",
            "description": "Comanda un robot aspirapolvere: avvia, ferma, rimanda alla base, o mandalo a pulire una stanza.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entita' o nome dell'aspirapolvere."},
                    "azione": {
                        "type": "string",
                        "enum": ["avvia", "ferma", "rientra", "spegni"],
                    },
                    "stanza": {
                        "type": "string",
                        "description": "Stanza o segmento da pulire, se la persona ne ha indicata una.",
                    },
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_ventilatore",
            "description": "Accende, spegne, cambia velocita' o oscillazione di un ventilatore.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entita' o nome del ventilatore."},
                    "azione": {
                        "type": "string",
                        "enum": ["accendi", "spegni", "velocita", "oscilla"],
                    },
                    "velocita": {"type": "integer", "description": "Velocita' da 0 a 100."},
                    "oscillazione": {"type": "boolean", "description": "Se far oscillare o no."},
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stato_aperture",
            "description": (
                "Dice quali porte, finestre e tapparelle risultano aperte. "
                "Usalo per domande come «sono chiuse tutte le finestre?» o «e' "
                "rimasto aperto qualcosa?»."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_allarme",
            "description": (
                "Inserisce o disinserisce l'allarme di casa, o ne riferisce lo "
                "stato. Se l'inserimento viene rifiutato perche' qualcosa e' "
                "aperto, riporta alla persona che cosa e' aperto e chiedi se "
                "vuole inserirlo lo stesso: solo allora richiama con forza=true."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "azione": {
                        "type": "string",
                        "enum": ["arma_casa", "arma_fuori", "disarma", "stato"],
                        "description": "arma_casa lascia liberi i sensori interni; arma_fuori li attiva tutti.",
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "La centrale, se in casa ce n'e' piu' di una.",
                    },
                    "codice": {
                        "type": "string",
                        "description": "Il codice della centrale, se ne richiede uno.",
                    },
                    "forza": {
                        "type": "boolean",
                        "description": "Inserisci anche con qualcosa di aperto, solo dopo che la persona lo ha confermato.",
                    },
                },
                "required": ["azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_simulazione",
            "description": (
                "Accende o spegne la simulazione di presenza, quella che fa "
                "sembrare la casa abitata quando si e' via. Si spegne da sola "
                "appena qualcuno rientra."
            ),
            "parameters": {
                "type": "object",
                "properties": {"azione": {"type": "string", "enum": ["accendi", "spegni", "stato"]}},
                "required": ["azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_clima",
            "description": (
                "Comanda un termostato o un climatizzatore per intero: modalita' "
                "(riscaldamento, raffrescamento, automatico, deumidificazione, "
                "ventilazione), temperatura, velocita' della ventola, umidita' "
                "obiettivo, profili predefiniti. Se il dispositivo non sa fare "
                "quel che gli si chiede lo dice, ed elenca cosa sa fare."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "L'entita' climate, o il nome con cui la persona la chiama.",
                    },
                    "azione": {
                        "type": "string",
                        "enum": [
                            "modalita",
                            "temperatura",
                            "ventola",
                            "umidita",
                            "preset",
                            "accendi",
                            "spegni",
                            "stato",
                        ],
                    },
                    "modalita": {
                        "type": "string",
                        "description": (
                            "Per azione 'modalita': riscaldamento, raffrescamento, "
                            "automatico, deumidificazione, ventilazione, spento."
                        ),
                    },
                    "temperatura": {"type": "number", "description": "Gradi obiettivo."},
                    "ventola": {
                        "type": "string",
                        "description": "La velocita' della ventola cosi' come la chiama il dispositivo.",
                    },
                    "umidita": {
                        "type": "integer",
                        "description": "Umidita' obiettivo in percentuale.",
                    },
                    "preset": {"type": "string", "description": "Un profilo predefinito."},
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stato_clima",
            "description": (
                "Dice come e' impostato un termostato: modalita', temperatura "
                "obiettivo, temperatura misurata in stanza, umidita', ventola. "
                "La temperatura impostata e quella misurata sono due cose diverse."
            ),
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "comanda_tapparella",
            "description": (
                "Apre, chiude, ferma a meta' corsa, porta a una percentuale precisa "
                "o orienta le lamelle di tapparelle, tende e persiane. La "
                "percentuale dice quanto e' APERTA: 0 e' chiusa, 100 e' aperta. "
                "«Abbassala al 40 per cento» vuol dire posizione 40."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "azione": {
                        "type": "string",
                        "enum": ["apri", "chiudi", "posizione", "lamelle", "ferma", "stato"],
                    },
                    "posizione": {
                        "type": "integer",
                        "description": "Quanto aperta, da 0 (chiusa) a 100 (aperta).",
                    },
                    "lamelle": {
                        "type": "integer",
                        "description": "Orientamento delle lamelle da 0 a 100.",
                    },
                },
                "required": ["entity_id", "azione"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stato_tapparella",
            "description": (
                "Dice quanto e' aperta una tapparella, in percentuale quando il "
                "motore lo sa dire. Una tapparella al 5 per cento e una spalancata "
                "sono tutte e due «aperte» per Home Assistant."
            ),
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
            },
        },
    },
]


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Esegue un tool registrato passando gli argomenti forniti dal modello LLM.

    E' il passaggio obbligato di ogni azione: comandi ai dispositivi,
    attivazione di modalita', meteo, notizie, promemoria. Per questo il
    registro delle azioni (issue #15) si attacca qui e non in dieci posti
    diversi — un tool nuovo risulta tracciato senza che nessuno se ne debba
    ricordare.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        registro.registra(
            f"tool.{tool_name}", esito=registro.ESITO_ERRORE, dettagli={"errore": "tool sconosciuto"}
        )
        return {"success": False, "error": f"Tool '{tool_name}' non trovato nel registro."}

    with registro.traccia(f"tool.{tool_name}", {"parametri": arguments}) as voce:
        try:
            if inspect.iscoroutinefunction(handler):
                esito = await handler(**arguments)
            else:
                esito = handler(**arguments)
        except PermessoNegato as negato:
            # Un rifiuto non e' un guasto, e non va raccontato come tale: chi
            # ha chiesto deve sapere cosa gli manca, non che «qualcosa e'
            # andato storto». Il registro lo ha gia' scritto in `esigi`.
            logger.info("Permesso negato su %s: %s", tool_name, negato.permesso)
            voce["esito"] = registro.ESITO_NEGATO
            voce["dettagli"]["permesso"] = negato.permesso
            return {
                "success": False,
                "error": negato.spiegazione,
                "permesso_negato": True,
                "spiegazione": negato.spiegazione,
            }
        except Exception as e:
            logger.error(f"Errore durante l'esecuzione del tool {tool_name} con args {arguments}: {e}")
            voce["esito"] = registro.ESITO_ERRORE
            voce["dettagli"]["errore"] = str(e)
            return {"success": False, "error": str(e)}

        # I tool segnalano i guasti restituendoli, non sollevandoli: senza
        # questo controllo un comando fallito comparirebbe nel registro come
        # riuscito, che e' il modo peggiore di avere un registro.
        if isinstance(esito, dict) and (esito.get("error") or esito.get("success") is False):
            voce["esito"] = registro.ESITO_ERRORE
            voce["dettagli"]["errore"] = str(esito.get("error") or "operazione non riuscita")
        return esito
