"""Timer, promemoria e intervista di apprendimento.

Riferimento: issue #196 (prima stava tutto in `routes_admin.py`).
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from shinra.api.sicurezza import (
    richiedi_autenticazione,
)
from shinra.services.interview_engine import interview_engine
from shinra.services.intervista_alias import dispositivi_senza_nome
from shinra.services.timer_engine import timer_engine
from shinra.services.user_manager import user_manager

logger = logging.getLogger("Shinra.Admin")
# Ogni rotta di questo router richiede una sessione valida: e' il
# comportamento predefinito (SEC-01). Per aprire un varco bisogna
# dichiararlo in sicurezza.ROTTE_PUBBLICHE.
router = APIRouter(
    prefix="/api",
    tags=["Timer, promemoria e apprendimento"],
    dependencies=[Depends(richiedi_autenticazione)],
)


# --- TIMERS & REMINDERS ENDPOINTS ---


class CreateTimerReq(BaseModel):
    label: str = "Timer"
    duration_seconds: int = 60
    user_id: str = "alessio"


class CreateReminderReq(BaseModel):
    text: str
    remind_at: str
    user_id: str = "alessio"


@router.get("/timers")
async def list_timers():
    """Elenca i timer attivi."""
    return timer_engine.get_timers()


@router.post("/timers")
async def create_timer(payload: CreateTimerReq):
    """Crea un timer."""
    item = timer_engine.add_timer(payload.label, payload.duration_seconds, payload.user_id)
    return {"success": True, "timer": item}


@router.delete("/timers/{timer_id}")
async def remove_timer(timer_id: str):
    """Cancella un timer."""
    success = timer_engine.delete_timer(timer_id)
    return {"success": success}


@router.get("/reminders")
async def list_reminders():
    """Elenca i promemoria in attesa."""
    return timer_engine.get_reminders()


@router.post("/reminders")
async def create_reminder(payload: CreateReminderReq):
    """Crea un promemoria."""
    item = timer_engine.add_reminder(payload.text, payload.remind_at, payload.user_id)
    return {"success": True, "reminder": item}


@router.delete("/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    """Cancella un promemoria."""
    success = timer_engine.delete_reminder(reminder_id)
    return {"success": success}


# --- LEARNING & INTERVIEW ENGINE ENDPOINTS ---


class StartLearningReq(BaseModel):
    user_id: str = "alessio"


class AnswerLearningReq(BaseModel):
    user_id: str = "alessio"
    answer: str


class ConfirmRoutineReq(BaseModel):
    routine: Dict[str, Any]


@router.post("/learning/start")
async def start_learning_session(payload: StartLearningReq):
    """Avvia l'intervista di apprendimento per un profilo."""
    # I dispositivi veri senza un nome: Home Assistant spento li rende zero, e
    # l'intervista fa le sue domande senza questa parte.
    dispositivi = await dispositivi_senza_nome()
    profilo = user_manager.get_user_by_id(payload.user_id)
    # L'intervista si svolge nella lingua della persona (vuota: quella dell'installazione).
    return interview_engine.start_session(payload.user_id, dispositivi, getattr(profilo, "lingua", "") or "")


@router.post("/learning/answer")
async def answer_learning_question(payload: AnswerLearningReq):
    """Manda la risposta a una domanda dell'intervista."""
    res = await interview_engine.process_answer(payload.user_id, payload.answer)
    return res


@router.post("/learning/confirm-routine")
async def confirm_learning_routine(payload: ConfirmRoutineReq):
    """Conferma la routine proposta alla fine dell'intervista."""
    res = await interview_engine.conferma_routine_proposta(payload.routine)
    return res


@router.post("/learning/stop")
async def stop_learning_session(payload: StartLearningReq):
    """Interrompe l'intervista di apprendimento."""
    interview_engine.stop_session(payload.user_id)
    return {"success": True, "message": "Sessione terminata."}


@router.get("/learning/status")
async def get_learning_status(user_id: str = "alessio"):
    """Dice se c'e' un'intervista aperta e a che punto e'."""
    session = interview_engine.get_session(user_id)
    return {"is_active": interview_engine.is_session_active(user_id), "session": session}
