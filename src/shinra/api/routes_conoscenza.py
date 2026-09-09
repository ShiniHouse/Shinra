"""Le rotte del recupero: com'e' messo l'indice, e cosa ha risposto a cosa.

`GET /fatti-usati` e' la rotta che soddisfa il criterio «mostrare quali fatti
hanno contribuito a una risposta». Non e' una curiosita': quando l'assistente
dice una cosa strana, la prima domanda e' «da dove l'ha presa», e senza questa
la risposta e' «leggi il prompt», che nessuno puo' fare.

Riferimento: issue #32.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from shinra.api.sicurezza import richiedi_autenticazione, richiedi_permesso
from shinra.services import permessi
from shinra.services.conoscenza import servizio_conoscenza

logger = logging.getLogger("Shinra.Conoscenza")

router = APIRouter(
    prefix="/api/conoscenza",
    tags=["Conoscenza"],
    dependencies=[Depends(richiedi_autenticazione)],
)


@router.get("/stato")
async def stato() -> Dict[str, Any]:
    """Quanti fatti, quanti indicizzati, e se il recupero e' semantico.

    `semantico: false` con dei fatti presenti vuol dire che il modello di
    embedding non e' installato: il recupero funziona lo stesso, per testo,
    e dirlo evita di credere che la ricerca semantica funzioni male.
    """
    return await servizio_conoscenza.stato()


@router.get("/fatti-usati")
async def fatti_usati() -> Dict[str, Any]:
    """I fatti che hanno contribuito all'ultima risposta, con i punteggi."""
    return {"fatti": servizio_conoscenza.fatti_usati()}


@router.post("/reindicizza", dependencies=[Depends(richiedi_permesso(permessi.SCRIVI_CONOSCENZA))])
async def reindicizza(forza: bool = False) -> Dict[str, Any]:
    """Ricalcola gli embedding mancanti, o tutti con `forza=true`.

    Serve dopo aver installato il modello, o dopo averlo cambiato. Non
    servirebbe per le modifiche ai fatti — quelle il servizio le riconosce da
    solo dall'impronta del testo — ed e' un pulsante, non un dovere.
    """
    esito = await servizio_conoscenza.aggiorna_indice(forza=forza)
    return {"success": True, **esito}
