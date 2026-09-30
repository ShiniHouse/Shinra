"""L'allarme, le aperture e la simulazione di presenza (issue #23)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.sicurezza_casa import comanda_allarme, stato_aperture
from shinra.skills.simulazione import comanda_simulazione

GESTORI: Dict[str, Callable] = {
    "stato_aperture": stato_aperture,
    "comanda_allarme": comanda_allarme,
    "comanda_simulazione": comanda_simulazione,
}

SCHEMI: List[Dict[str, Any]] = [
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
]
