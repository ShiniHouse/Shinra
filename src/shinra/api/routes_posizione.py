"""«Dove sono?»: la posizione di chi chiede, rispetto ai luoghi registrati (#343).

Ognuno decide per **se'**: collega (o scollega) la propria persona di Home Assistant. Senza collegamento non si e' localizzati.
Si risponde col **nome del luogo** e mai con le coordinate; non si conserva nessuno spostamento.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.services import posizione

router = APIRouter(
    prefix="/api/posizione",
    tags=["Posizione"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class PosizioneIn(BaseModel):
    entita: str = ""


@router.get("/candidati")
async def candidati() -> Dict[str, Any]:
    """Le persone e i telefoni di Home Assistant fra cui scegliere, col nome leggibile e se mandano una posizione."""
    return {"candidati": posizione.candidati()}


@router.get("/io")
async def dove_sono(request: Request) -> Dict[str, Any]:
    """In quale luogo si trova chi chiede: il nome del luogo, «in giro», «ignota» o «spenta». Mai le coordinate."""
    utente = utente_corrente(request)
    return posizione.dove_sei(utente.entita_posizione if utente else "").come_dizionario()


@router.put("/io")
async def collega_la_mia_posizione(corpo: PosizioneIn, request: Request) -> Dict[str, Any]:
    """Collega la propria persona o il proprio telefono di Home Assistant (vuoto: spegne la posizione). Vale solo per se'."""
    utente = utente_corrente(request)
    if utente is None:
        raise HTTPException(status_code=401, detail="Serve un profilo per collegare la posizione.")
    try:
        return posizione.collega(utente.id, corpo.entita).come_dizionario()
    except posizione.EntitaNonValida as errore:
        raise HTTPException(status_code=422, detail=str(errore)) from errore
