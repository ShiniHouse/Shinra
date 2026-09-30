"""I dispositivi di casa, le modalita' e le temperature dei sensori."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.ha_tools import (
    activate_mode,
    activate_scene_or_routine,
    control_device,
    get_home_status,
    get_indoor_temperature,
)

GESTORI: Dict[str, Callable] = {
    "control_device": control_device,
    "get_home_status": get_home_status,
    "get_indoor_temperature": get_indoor_temperature,
    "activate_mode": activate_mode,
    "activate_scene_or_routine": activate_scene_or_routine,
}

SCHEMI: List[Dict[str, Any]] = [
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
]
