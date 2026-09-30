"""Serrature, media player, aspirapolvere e ventilatori (issue #20)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.domini_casa import (
    comanda_aspirapolvere,
    comanda_media,
    comanda_serratura,
    comanda_ventilatore,
)

GESTORI: Dict[str, Callable] = {
    "comanda_serratura": comanda_serratura,
    "comanda_media": comanda_media,
    "comanda_aspirapolvere": comanda_aspirapolvere,
    "comanda_ventilatore": comanda_ventilatore,
}

SCHEMI: List[Dict[str, Any]] = [
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
]
