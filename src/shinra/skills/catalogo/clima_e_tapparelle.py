"""Clima e tapparelle per intero: modalita', ventola, umidita', posizione percentuale e lamelle (issue #21)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.clima import comanda_clima, stato_clima
from shinra.skills.tapparelle import comanda_tapparella, stato_tapparella

GESTORI: Dict[str, Callable] = {
    "comanda_clima": comanda_clima,
    "stato_clima": stato_clima,
    "comanda_tapparella": comanda_tapparella,
    "stato_tapparella": stato_tapparella,
}

SCHEMI: List[Dict[str, Any]] = [
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
