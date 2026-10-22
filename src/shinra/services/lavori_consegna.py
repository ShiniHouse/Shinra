"""Consegnare l'esito di un lavoro a chi lo aspettava (#431, ADR 0013).

Due strade, e nessuna porta il contenuto dove non deve:

- **l'evento `lavoro.finito`** arriva al browser **di chi ha chiesto** (il canale lo filtra per profilo) con il testo da mostrare: e'
  l'unica strada che porta l'esito vero, in chat;
- **l'avviso** (dashboard aperta altrove, telefono, ntfy, secondo le preferenze della persona) dice solo che il lavoro e' pronto, **senza
  il contenuto**: un avviso viaggia verso piu' canali e uno di questi puo' essere un telefono sul tavolo.

Non solleva: una consegna che non riesce resta nel log, e l'esito si legge comunque con `GET /api/lavori/{id}`.
"""

from __future__ import annotations

import logging
from typing import Any

from shinra.domain import lavori as dominio
from shinra.domain import notifiche as notifiche_dominio
from shinra.domain.eventi import bus
from shinra.services.notifiche import servizio_notifiche
from shinra.services.user_manager import user_manager

logger = logging.getLogger("Shinra.Lavori")


def _lingua_di(profilo: str) -> str:
    try:
        utente = user_manager.get_user_by_id(profilo)
    except Exception:
        return ""
    return str(getattr(utente, "lingua", "") or "")


async def consegna(lavoro: dict[str, Any]) -> None:
    """Chiamata alla fine di ogni lavoro (`ServizioLavori.alla_fine`)."""
    if not dominio.da_consegnare(lavoro["stato"]):
        return
    proprietario = lavoro.get("proprietario", "")
    lingua = _lingua_di(proprietario)
    # `lavoro` qui e' quello che si vede (senza proprietario): lo si rimette per il filtro del canale.
    completo = {**lavoro, "proprietario": proprietario}
    await bus.pubblica(dominio.evento_finito(completo, lingua))
    riuscito = lavoro["stato"] == dominio.FATTO
    avviso = notifiche_dominio.Avviso(
        categoria=notifiche_dominio.LAVORO,
        titolo=dominio.testo("avviso_fatto" if riuscito else "avviso_fallito", lingua),
        testo=dominio.testo("avviso_fatto_testo" if riuscito else "avviso_fallito_testo", lingua),
        priorita=notifiche_dominio.INFORMATIVA,
    )
    try:
        await servizio_notifiche.avvisa(avviso, utente=proprietario or None)
    except Exception:
        logger.exception("Avviso del lavoro %s non riuscito", lavoro.get("id"))
