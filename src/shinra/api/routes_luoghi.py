"""Le rotte dei luoghi (#342): la casa principale, altre abitazioni, il lavoro.

Le coordinate sono un dato delicato. Chi **registra** un luogo le manda (dal browser) o le fa leggere a Home Assistant
(dal telefono); chi **legge** l'elenco le riceve arrotondate a circa un chilometro: basta a riconoscere il posto e uno
schermo condiviso non mostra l'ingresso di casa. Le coordinate esatte non escono mai dal server.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, richiedi_permesso
from shinra.domain import luoghi as dominio
from shinra.services import luoghi, permessi

router = APIRouter(
    prefix="/api/luoghi",
    tags=["Luoghi"],
    dependencies=[
        Depends(richiedi_autenticazione),
        Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI)),
    ],
)


class LuogoIn(BaseModel):
    nome: str
    tipo: str = "abitazione"
    latitudine: float
    longitudine: float
    precisione_m: Optional[int] = None
    raggio_m: Optional[int] = None
    citta: str = ""
    principale: bool = False
    origine: str = "browser"


class LuogoDaPersonaIn(BaseModel):
    entita: str
    nome: str
    tipo: str = "abitazione"
    raggio_m: Optional[int] = None
    citta: str = ""
    principale: bool = False


class LuogoModifica(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = None
    raggio_m: Optional[int] = None
    citta: Optional[str] = None
    principale: Optional[bool] = None


def come_si_mostra(luogo: Dict[str, Any]) -> Dict[str, Any]:
    """Un luogo per l'interfaccia: coordinate arrotondate a circa un chilometro, mai quelle esatte."""
    lat, lon = dominio.arrotonda_per_servizi_esterni(float(luogo["latitudine"]), float(luogo["longitudine"]))
    visibile = {k: v for k, v in luogo.items() if k not in ("latitudine", "longitudine", "creato_il")}
    visibile.update({"latitudine_approssimata": lat, "longitudine_approssimata": lon})
    return visibile


@router.get("")
async def elenco() -> Dict[str, Any]:
    """I luoghi registrati, con le coordinate arrotondate a circa un chilometro."""
    return {"luoghi": [come_si_mostra(x) for x in luoghi.elenco()]}


@router.post("")
async def registra(corpo: LuogoIn) -> Dict[str, Any]:
    """Registra il luogo in cui si e', dalle coordinate lette dal browser (la precisione di un PC e' bassa: va dichiarata)."""
    try:
        return {"success": True, "luogo": come_si_mostra(luoghi.registra(corpo.model_dump()))}
    except dominio.LuogoNonValido as errore:
        raise HTTPException(status_code=422, detail=str(errore)) from errore


@router.post("/da-persona")
async def registra_da_persona(corpo: LuogoDaPersonaIn) -> Dict[str, Any]:
    """Registra un luogo dalla posizione che Home Assistant conosce di una persona o di un telefono."""
    try:
        dati = corpo.model_dump(exclude={"entita"})
        return {
            "success": True,
            "luogo": come_si_mostra(await luoghi.registra_da_persona(corpo.entita, dati)),
        }
    except dominio.LuogoNonValido as errore:
        raise HTTPException(status_code=422, detail=str(errore)) from errore


@router.put("/{identificativo}")
async def modifica(identificativo: str, corpo: LuogoModifica) -> Dict[str, Any]:
    """Cambia nome, tipo, raggio, citta' o il luogo principale. Le coordinate non si ritoccano: si registra di nuovo."""
    try:
        return {
            "success": True,
            "luogo": come_si_mostra(luoghi.aggiorna(identificativo, corpo.model_dump(exclude_none=True))),
        }
    except luoghi.LuogoNonTrovato as errore:
        raise HTTPException(status_code=404, detail="Luogo non trovato.") from errore
    except dominio.LuogoNonValido as errore:
        raise HTTPException(status_code=422, detail=str(errore)) from errore


@router.delete("/{identificativo}")
async def cancella(identificativo: str) -> Dict[str, Any]:
    """Cancella un luogo e, con lui, le sue coordinate."""
    return {"success": luoghi.cancella(identificativo)}
