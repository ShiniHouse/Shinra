"""Le rotte delle regole: crearle, provarle, spegnerle.

Una regola cambia cosa fa la casa da sola, quindi cambiarle richiede il
permesso di modificare le modalita': sono la stessa cosa vista da due lati —
una modalita' e' una sequenza che parte a comando, una regola e' una sequenza
che parte da sola, e la seconda e' piu' potente della prima.

`POST /prova` esegue una regola **saltando il trigger ma non le condizioni**.
E' voluto: serve a rispondere a «perche' non scatta?», e una prova che ignora
anche le condizioni risponderebbe sempre di si' e non direbbe niente.

Riferimento: issue #27.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shinra.api.sicurezza import richiedi_autenticazione, richiedi_permesso
from shinra.domain import regole as dominio
from shinra.services import permessi
from shinra.services.regole import motore_regole
from shinra.services.user_manager import UserProfile

logger = logging.getLogger("Shinra.Regole")

router = APIRouter(
    prefix="/api/regole",
    tags=["Regole"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class RegolaIn(BaseModel):
    nome: str
    trigger: Dict[str, Any]
    condizioni: List[Dict[str, Any]] = Field(default_factory=list)
    azioni: List[Dict[str, Any]] = Field(default_factory=list)
    attiva: bool = True


class Modifica(BaseModel):
    nome: Optional[str] = None
    trigger: Optional[Dict[str, Any]] = None
    condizioni: Optional[List[Dict[str, Any]]] = None
    azioni: Optional[List[Dict[str, Any]]] = None
    attiva: Optional[bool] = None


def _valida(regola: RegolaIn) -> None:
    """Rifiuta cio' che non potrebbe mai scattare.

    Una regola con un trigger sconosciuto viene salvata, non scatta mai, e
    sembra rotta senza dire perche'. Meglio rifiutarla adesso, quando c'e'
    ancora qualcuno che guarda.
    """
    tipo = str(regola.trigger.get("tipo") or "")
    if tipo not in dominio.TRIGGER:
        raise HTTPException(
            status_code=400,
            detail=f"Trigger «{tipo or 'assente'}» sconosciuto. Sono: {', '.join(dominio.TRIGGER)}.",
        )

    if tipo == dominio.STATO:
        confronto = str(regola.trigger.get("confronto") or "")
        if confronto and confronto not in dominio.CONFRONTI:
            raise HTTPException(
                status_code=400,
                detail=f"Confronto «{confronto}» sconosciuto. Sono: {', '.join(dominio.CONFRONTI)}.",
            )
        if not regola.trigger.get("entity_id"):
            raise HTTPException(status_code=400, detail="Un trigger su stato ha bisogno di un'entita'.")

    for condizione in regola.condizioni:
        if str(condizione.get("tipo") or "") not in dominio.CONDIZIONI:
            raise HTTPException(
                status_code=400,
                detail=f"Condizione «{condizione.get('tipo')}» sconosciuta.",
            )

    if not regola.azioni:
        raise HTTPException(
            status_code=400, detail="Una regola senza azioni non fa niente: aggiungine almeno una."
        )

    for azione in regola.azioni:
        if str(azione.get("tipo") or "") not in dominio.AZIONI:
            raise HTTPException(status_code=400, detail=f"Azione «{azione.get('tipo')}» sconosciuta.")


@router.get("")
async def elenco() -> Dict[str, Any]:
    voci = motore_regole.elenco()
    return {
        "regole": [
            {
                **v,
                "descrizione": dominio.descrivi(
                    dominio.Regola(
                        str(v["id"]),
                        str(v.get("nome") or ""),
                        dict(v.get("trigger") or {}),
                        list(v.get("condizioni") or []),
                        list(v.get("azioni") or []),
                    )
                ),
            }
            for v in voci
        ]
    }


@router.post("", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def crea(
    dati: RegolaIn, profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    _valida(dati)
    voce = motore_regole.crea(dati.model_dump(), autore=profilo.id if profilo else None)
    return {"success": True, "regola": voce}


@router.patch("/{identificativo}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def modifica(identificativo: str, dati: Modifica) -> Dict[str, Any]:
    cambiamenti = {k: v for k, v in dati.model_dump().items() if v is not None}
    if not cambiamenti:
        raise HTTPException(status_code=400, detail="Non c'e' niente da cambiare.")

    voce = motore_regole.modifica(identificativo, cambiamenti)
    if voce is None:
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": True, "regola": voce}


@router.delete("/{identificativo}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def cancella(identificativo: str) -> Dict[str, Any]:
    if not motore_regole.cancella(identificativo):
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": True}


@router.post("/{identificativo}/prova", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def prova(identificativo: str) -> Dict[str, Any]:
    """Esegue la regola saltando il trigger, **ma non le condizioni**.

    Serve a rispondere a «perche' non scatta?»: se le condizioni non sono
    soddisfatte la risposta lo dice, ed e' quasi sempre la risposta giusta.
    """
    esito = await motore_regole.esegui_per_id(identificativo, motivo="prova manuale")
    if esito is None:
        raise HTTPException(status_code=404, detail="Regola non trovata.")
    return {"success": esito.get("eseguita", False), **esito}
