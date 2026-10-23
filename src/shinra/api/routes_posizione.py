"""«Dove sono?»: la posizione di chi chiede, rispetto ai luoghi registrati (#343).

Ognuno decide per **se'**: collega (o scollega) la propria persona di Home Assistant. Senza collegamento non si e' localizzati.
Si risponde col **nome del luogo** e mai con le coordinate; non si conserva nessuno spostamento.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.domain import luoghi as dominio
from shinra.services import posizione, posizione_eventi

router = APIRouter(
    prefix="/api/posizione",
    tags=["Posizione"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class PosizioneIn(BaseModel):
    entita: str = ""


class SegnalazioneIn(BaseModel):
    latitudine: float
    longitudine: float
    precisione_m: Optional[int] = None


@router.get("/candidati")
async def candidati() -> Dict[str, Any]:
    """Le persone e i telefoni di Home Assistant fra cui scegliere, col nome leggibile e se mandano una posizione."""
    return {"candidati": posizione.candidati()}


@router.get("/io")
async def dove_sono(request: Request) -> Dict[str, Any]:
    """In quale luogo si trova chi chiede: il nome del luogo, «in giro», «ignota» o «spenta». Mai le coordinate."""
    utente = utente_corrente(request)
    if utente is None:
        return posizione.dove_sei("").come_dizionario()
    risposta = posizione.dove_sei(utente.entita_posizione, profilo_id=utente.id).come_dizionario()
    # Da dove arriva la posizione: serve all'app per sapere se deve segnalare la propria.
    risposta["fonte"] = (
        posizione.DISPOSITIVO
        if utente.entita_posizione == posizione.DISPOSITIVO
        else ("home_assistant" if utente.entita_posizione else None)
    )
    return risposta


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


@router.post("/segnala")
async def segnala(corpo: SegnalazioneIn, request: Request) -> Dict[str, Any]:
    """L'app Shinra del telefono dice dove si trova. Vale solo per chi ha scelto «questo telefono» come fonte."""
    utente = utente_corrente(request)
    if utente is None:
        raise HTTPException(status_code=401, detail="Serve un profilo.")
    if utente.entita_posizione != posizione.DISPOSITIVO:
        raise HTTPException(
            status_code=409, detail="Non hai scelto questa app come fonte della tua posizione."
        )
    try:
        posizione.segnala(utente.id, corpo.latitudine, corpo.longitudine, corpo.precisione_m)
    except dominio.LuogoNonValido as errore:
        raise HTTPException(status_code=422, detail=str(errore)) from errore
    dove = posizione.dove_sei(utente.entita_posizione, profilo_id=utente.id)
    posizione_eventi.annuncia(utente.id, dove, utente.name)
    return dove.come_dizionario()
