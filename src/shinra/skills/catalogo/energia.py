"""Consumi, costi e fasce orarie italiane (issue #24)."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from shinra.skills.energia import consumo_energia, costo_dispositivo, fascia_corrente

GESTORI: Dict[str, Callable] = {
    "fascia_corrente": fascia_corrente,
    "consumo_energia": consumo_energia,
    "costo_dispositivo": costo_dispositivo,
}

SCHEMI: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fascia_corrente",
            "description": (
                "Dice in che fascia oraria dell'energia elettrica siamo adesso "
                "(F1 ore di punta, F2 intermedie, F3 fuori punta) e quando cambia. "
                "Domeniche e festivi sono F3 tutto il giorno."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consumo_energia",
            "description": (
                "Quanti kilowattora sono stati consumati e quanto sono costati, "
                "divisi per fascia. Se non ci sono letture lo dice, invece di "
                "rispondere zero."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "enum": ["oggi", "ieri", "settimana", "mese"],
                    },
                    "entity_id": {
                        "type": "string",
                        "description": "Un contatore specifico. Omesso, sono tutti insieme.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "costo_dispositivo",
            "description": (
                "Quanto costa tenere acceso un dispositivo, all'ora e al giorno, "
                "alla tariffa della fascia in cui siamo adesso. Serve un sensore "
                "che misuri la potenza."
            ),
            "parameters": {
                "type": "object",
                "properties": {"entity_id": {"type": "string"}},
                "required": ["entity_id"],
            },
        },
    },
]
