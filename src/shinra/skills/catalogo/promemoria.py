"""I promemoria: aggiungere, elencare, cancellare."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.reminders import add_reminder, delete_reminder, list_reminders

GESTORI: Dict[str, Callable] = {
    "add_reminder": add_reminder,
    "list_reminders": list_reminders,
    "delete_reminder": delete_reminder,
}

SCHEMI: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": (
                "Imposta un promemoria che suona all'ora indicata. Serve sempre un "
                "quando: se la persona non lo ha detto, il tool risponde chiedendolo "
                "e NON crea niente — in quel caso chiedi tu l'orario, non dire che "
                "hai salvato."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Contenuto del promemoria."},
                    "time_info": {
                        "type": "string",
                        "description": (
                            "Quando ricordare: 'domani mattina', 'alle 18:00', 'stasera', "
                            "'sabato', 'fra due ore', 'il 15'. Obbligatorio nei fatti: "
                            "senza, il promemoria non viene creato."
                        ),
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
            "name": "delete_reminder",
            "description": "Cancella un promemoria, e con lui la sveglia che lo avrebbe fatto suonare.",
            "parameters": {
                "type": "object",
                "properties": {"reminder_id": {"type": "string"}},
                "required": ["reminder_id"],
            },
        },
    },
]
