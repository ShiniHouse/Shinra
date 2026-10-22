"""La chat: una frase in ingresso, la risposta di Shinra in uscita (e, se la richiesta e' lenta, «ci sto lavorando»).

Stava in `app.py`, che superava il tetto delle cinquecento righe. La rotta non cambia (`POST /api/chat`) e resta protetta come tutto il
resto. L'agente e' quello di sempre (`services/agent.py`): i test lo sostituiscono da li'.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api import sicurezza
from shinra.config.settings import settings
from shinra.domain import contesto
from shinra.domain import lavori as dominio_lavori
from shinra.services.agent import agent
from shinra.services.lavori import servizio_lavori
from shinra.services.satelliti import registro_satelliti
from shinra.services.user_manager import user_manager

router = APIRouter(tags=["Chat"], dependencies=[Depends(sicurezza.richiedi_autenticazione)])


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    # Da quale punto di ascolto arriva (issue #33). La dashboard lo manda se
    # si e' dichiarata satellite di una stanza; chi non lo manda continua a
    # funzionare come prima.
    satellite: Optional[str] = None
    # La dashboard dichiara che puo' ricevere la risposta **piu' tardi** (evento `lavoro.finito`): una richiesta lenta diventa un lavoro
    # in background («ci sto lavorando»). Chi non lo dichiara (Alexa, un satellite a voce) aspetta come sempre.
    puo_attendere: bool = False


@router.post("/api/chat")
async def chat_endpoint(payload: ChatRequest, request: Request):
    """Endpoint per richieste di chat / voce dall'interfaccia web o client locali."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto.")

    if payload.satellite:
        # Chi ha sentito la frase per primo risponde; agli altri si dice che
        # e' gia' stata presa in carico, e non si esegue niente. Due
        # dispositivi sullo stesso tavolo sentono la stessa cosa, e due
        # esecuzioni della stessa richiesta su una serranda si notano.
        if not registro_satelliti.prende_in_carico(payload.satellite, payload.message):
            return {"response": "", "gia_in_carico": True}
        contesto.dichiara_stanza(registro_satelliti.stanza_di(payload.satellite))

    if payload.puo_attendere and settings.lavori.soglia_secondi > 0:
        profilo = sicurezza.utente_corrente(request) or user_manager.get_user_by_id(payload.user_id or "")
        proprietario = str(getattr(profilo, "id", "") or "")
        if proprietario:
            risposta, lavoro = await servizio_lavori.con_attesa_massima(
                proprietario,
                payload.message,
                lambda: agent.process_user_input(user_text=payload.message, user_id=payload.user_id),
                settings.lavori.soglia_secondi,
            )
            if lavoro is not None:
                lingua = str(getattr(profilo, "lingua", "") or "")
                return {
                    "response": dominio_lavori.testo("ci_penso", lingua),
                    "actions": [],
                    "lavoro": {"id": lavoro["id"], "stato": lavoro["stato"]},
                }
            return risposta

    result = await agent.process_user_input(user_text=payload.message, user_id=payload.user_id)
    return result
