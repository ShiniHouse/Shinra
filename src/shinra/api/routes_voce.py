"""La rotta che riceve l'audio del microfono e restituisce il testo.

Esiste perche' fino alla issue #31 quell'audio andava a Google. Adesso arriva
qui, viene trascritto sul server di casa, e non esce.

Trascrivere non comanda niente: quello che il testo poi fa passa dall'agente
e dai suoi controlli, gli stessi di una frase digitata. E' il motivo per cui
questa rotta non porta un permesso proprio — sarebbe un permesso su
«parlare», e chi non lo avesse scriverebbe la stessa frase con la tastiera.

Riferimento: issue #31.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from shinra.api.sicurezza import richiedi_autenticazione
from shinra.domain import trascrizione as dominio
from shinra.services.trascrizione import AudioRifiutato, NonSiPuo, servizio_trascrizione

logger = logging.getLogger("Shinra.Voce")

router = APIRouter(
    prefix="/api/voce",
    tags=["Voce"],
    dependencies=[Depends(richiedi_autenticazione)],
)


@router.get("/stato")
async def stato() -> Dict[str, Any]:
    """Se il microfono si puo' accendere, e cosa dire se no.

    La dashboard lo chiede prima di mostrare il pulsante: un microfono che
    registra e poi fallisce e' peggio di un microfono spento, perche' chi lo
    preme ha gia' parlato e scopre dopo che non e' servito.
    """
    return servizio_trascrizione.per_l_interfaccia()


@router.post("/trascrivi")
async def trascrivi(
    audio: UploadFile = File(...),
    tipo: str = Form(default=""),
) -> Dict[str, Any]:
    """Riceve una registrazione e restituisce cio' che e' stato detto.

    Il tetto sulla dimensione si applica **prima** di leggere tutto: leggere
    per intero un caricamento senza limite e poi misurarlo vuol dire averlo
    gia' in memoria, che e' il problema che il limite dovrebbe evitare.

    La trascrizione gira su un altro filo. Far girare il modello qui dentro,
    dove tutto e' `async`, significa fermare il filo che serve **tutte** le
    richieste: per i secondi della trascrizione l'hub non risponde piu' a
    niente — non la dashboard, non le rotte di Alexa, non gli eventi della
    casa. Una frase detta al microfono non deve poter spegnere la casa per il
    tempo in cui viene capita.
    """
    dati = await audio.read(dominio.DIMENSIONE_MASSIMA + 1)

    try:
        testo = await run_in_threadpool(servizio_trascrizione.trascrivi, dati, tipo or audio.content_type)
    except AudioRifiutato as errore:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(errore)) from errore
    except NonSiPuo as errore:
        # 409 e non 500: non e' un guasto, e' una condizione che si risolve
        # installando qualcosa o cambiando una riga di configurazione.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(errore)) from errore

    # Il testo non finisce nel log: e' cio' che una persona ha detto in casa
    # sua. Nel log resta che una trascrizione c'e' stata e quanto era lunga.
    logger.info("Trascrizione completata (%d caratteri).", len(testo))
    return {"testo": testo, "vuota": not testo}
