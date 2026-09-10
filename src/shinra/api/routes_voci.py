"""Le voci sentite dagli Echo, e a chi corrispondono.

Associare una voce a un profilo significa dare a chi parla i permessi di
quella persona. E' un'azione di gestione degli utenti, non una preferenza, e
porta lo stesso permesso: `utenti.gestisci`. Chi puo' creare un profilo
amministratore puo' anche dire quale voce lo comanda; chi non puo' l'una non
deve poter l'altra.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shinra.api.sicurezza import richiedi_autenticazione, richiedi_permesso
from shinra.services import permessi, registro
from shinra.services.voci import servizio_voci

logger = logging.getLogger("Shinra.Voci")

router = APIRouter(
    prefix="/api/voci",
    tags=["Voci"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class Associazione(BaseModel):
    person_id: str = Field(description="L'identificativo del profilo vocale, come lo manda Amazon.")
    # Vuoto riporta la voce a sconosciuta: e' il modo di revocare
    # un'associazione senza cancellare la riga, che serve ancora a sapere
    # che quella voce esiste.
    user_id: Optional[str] = None
    nota: str = ""


@router.get("")
async def elenco() -> List[Dict[str, Any]]:
    """Le voci sentite, la piu' recente per prima.

    Leggibile da chiunque sia entrato in casa: dice quali voci l'impianto ha
    sentito e quali sono attribuite, che e' esattamente cio' che serve per
    accorgersi di una voce di troppo. Cambiarle richiede il permesso.
    """
    return servizio_voci.elenco()


@router.post("/associa", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def associa(dati: Associazione) -> Dict[str, Any]:
    """Dice di chi e' una voce, o la riporta a sconosciuta."""
    try:
        riga = servizio_voci.associa(dati.person_id, dati.user_id, dati.nota)
    except ValueError as errore:
        raise HTTPException(status_code=400, detail=str(errore)) from errore

    if riga is None:
        raise HTTPException(status_code=404, detail="Questa voce non risulta mai sentita.")

    registro.registra(
        "voce.associata",
        dettagli={"person_id": dati.person_id, "profilo": dati.user_id or "nessuno"},
    )
    logger.info("Voce %s associata a %s.", dati.person_id, dati.user_id or "nessuno")
    return {"success": True, "voce": riga}


@router.delete("/{person_id}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def dimentica(person_id: str) -> Dict[str, Any]:
    """Toglie la riga.

    Dimenticare non e' revocare: se quella voce parla ancora, la riga
    ricompare — sconosciuta, senza permessi. Serve a ripulire l'elenco dalle
    voci di passaggio, non a impedire a qualcuno di parlare.
    """
    if not servizio_voci.dimentica(person_id):
        raise HTTPException(status_code=404, detail="Questa voce non risulta mai sentita.")

    registro.registra("voce.dimenticata", dettagli={"person_id": person_id})
    return {"success": True}
