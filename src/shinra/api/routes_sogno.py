"""Le rotte del sogno: cosa Shinra ha notato di notte (#263).

Ognuno vede **solo le proprie** proposte; l'identificativo di una proposta altrui riceve «non trovata» (404), come se non
esistesse. Accettare un'abitudine crea una regola **spenta**: non cambia niente in casa finche' una persona non la accende.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.services import proposte_del_sogno as sogno

router = APIRouter(
    prefix="/api/sogno",
    tags=["Sogno"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class Accettazione(BaseModel):
    # Per due ricordi simili: l'identificativo di quello che si tiene (l'altro si archivia).
    tieni: Optional[str] = None


def _non_trovata(e: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail="Proposta non trovata.")


def _come_si_vede(p: Dict[str, Any]) -> Dict[str, Any]:
    return {k: p[k] for k in ("id", "tipo", "dati", "stato", "creato_il")}


@router.get("/proposte")
async def proposte_in_attesa(request: Request) -> Dict[str, Any]:
    """Le proposte di stanotte (e dei giorni scorsi) che aspettano una risposta, solo di chi chiede."""
    return {"proposte": [_come_si_vede(p) for p in sogno.elenco(utente_corrente(request))]}


@router.post("/proposte/{identificativo}/scarta")
async def scarta(identificativo: str, request: Request) -> Dict[str, Any]:
    """Scarta una proposta: non viene riproposta."""
    try:
        return {"success": sogno.scarta(utente_corrente(request), identificativo)}
    except sogno.PropostaNonTrovata as e:
        raise _non_trovata(e) from e


@router.post("/proposte/{identificativo}/accetta")
async def accetta(
    identificativo: str, request: Request, corpo: Optional[Accettazione] = None
) -> Dict[str, Any]:
    """Accetta. Se l'abitudine si sa scrivere come regola, nasce una regola spenta e ne torna l'identificativo."""
    try:
        return {
            "success": True,
            **sogno.accetta(utente_corrente(request), identificativo, tieni=corpo.tieni if corpo else None),
        }
    except sogno.PropostaNonTrovata as e:
        raise _non_trovata(e) from e
    except sogno.ScegliQualeTenere as e:
        raise HTTPException(status_code=422, detail="Scegli quale dei due ricordi tenere.") from e
