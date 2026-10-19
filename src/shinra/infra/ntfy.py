"""Mandare un avviso a un server `ntfy` che sta in casa (#389).

Solo in uscita. Non parla mai con un indirizzo che non sia locale (`domain.notifiche.indirizzo_locale`), nemmeno se glielo
si chiede: il motivo di ntfy e' non passare da terzi. Non solleva mai: chi avvisa sta gia' raccontando qualcosa, e un guasto
del canale non deve diventare un guasto dell'evento.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from shinra.domain import notifiche as dominio

logger = logging.getLogger("Shinra.Ntfy")

TEMPO_MASSIMO_SECONDI = 5.0
# ntfy va da 1 (minima) a 5 (massima).
_PRIORITA = {dominio.INFORMATIVA: 2, dominio.IMPORTANTE: 3, dominio.URGENTE: 5}


@dataclass(frozen=True)
class Esito:
    riuscito: bool
    errore: str = ""


async def pubblica(url: str, argomento: str, avviso: Mapping[str, Any]) -> Esito:
    """Pubblica un avviso sull'argomento. Mai il testo o l'argomento nei log: solo se e' andata."""
    if not dominio.indirizzo_locale(url):
        return Esito(False, "l'indirizzo di ntfy non e' locale")
    corpo = {
        "topic": argomento,
        "title": str(avviso.get("titolo") or "Shinra"),
        "message": str(avviso.get("testo") or avviso.get("titolo") or "Shinra"),
        "priority": _PRIORITA.get(str(avviso.get("priorita") or ""), 3),
        "tags": [str(avviso.get("categoria"))] if avviso.get("categoria") else [],
    }
    try:
        async with httpx.AsyncClient(timeout=TEMPO_MASSIMO_SECONDI) as cliente:
            risposta = await cliente.post(url.strip().rstrip("/") + "/", json=corpo)
        if risposta.status_code >= 400:
            return Esito(False, f"ntfy ha risposto {risposta.status_code}")
        return Esito(True)
    except httpx.HTTPError as errore:
        logger.warning("Invio a ntfy non riuscito: %s", type(errore).__name__)
        return Esito(False, type(errore).__name__)
