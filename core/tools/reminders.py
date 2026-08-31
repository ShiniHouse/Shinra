import datetime
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Memoria in-memory per note e promemoria
_REMINDERS_DB: List[Dict[str, Any]] = []

async def add_reminder(text: str, time_info: str = "oggi") -> Dict[str, Any]:
    """
    Aggiunge un promemoria o una nota per l'utente.
    
    Args:
        text: Testo o descrizione del promemoria (es. 'comprare il latte', 'chiamare il medico').
        time_info: Quando ricordare (es. 'stasera alle 20:00', 'domani mattina', 'tra 10 minuti').
    """
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    item = {
        "id": len(_REMINDERS_DB) + 1,
        "testo": text,
        "orario": time_info,
        "creato_il": created_at,
        "completato": False
    }
    _REMINDERS_DB.append(item)
    return {
        "success": True,
        "message": f"Promemoria salvato: '{text}' ({time_info})",
        "promemoria": item
    }

async def list_reminders() -> Dict[str, Any]:
    """
    Restituisce la lista di tutti i promemoria e le note attive.
    """
    active = [r for r in _REMINDERS_DB if not r["completato"]]
    return {
        "success": True,
        "totale_attivi": len(active),
        "promemoria": active
    }
