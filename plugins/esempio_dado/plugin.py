"""Un plugin di esempio: tira un dado.

Non dichiara permessi: non tocca la casa, la rete ne' la conoscenza. E' il piu'
piccolo plugin che si possa scrivere, e serve a mostrare la forma: `SCHEMI` e
`GESTORI`, con il `Contesto` come primo argomento di ogni gestore.
"""

import random
from typing import Any, Dict

SCHEMI = [
    {
        "type": "function",
        "function": {
            "name": "esempio_dado_tira",
            "description": "Tira un dado e dice che numero e' uscito.",
            "parameters": {
                "type": "object",
                "properties": {
                    "facce": {"type": "integer", "description": "Quante facce ha il dado (da 2 a 100)."},
                },
            },
        },
    }
]


def tira(contesto, facce: int = 6) -> Dict[str, Any]:
    if not 2 <= int(facce) <= 100:
        return {"success": False, "error": "Un dado ha da 2 a 100 facce."}
    uscito = random.randint(1, int(facce))  # noqa: S311 - un dado non e' crittografia
    return {"success": True, "messaggio": f"E' uscito {uscito} (dado a {int(facce)} facce)."}


GESTORI = {"esempio_dado_tira": tira}
