"""Intenti di apprendimento, timer e promemoria."""

from __future__ import annotations

import logging
from typing import Optional

from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra

logger = logging.getLogger("Shinra.Intenti")


class Apprendimento(Intento):
    """La Modalita' Apprendimento: l'avvio, le risposte e l'interruzione."""

    nome = "apprendimento"
    priorita = 10  # prima di tutto: durante un'intervista ogni frase e' una risposta

    def applicabile(self, richiesta: Richiesta) -> bool:
        from shinra.services.interview_engine import interview_engine

        if any(t in richiesta.minuscolo for t in richiesta.schemi.avvii_apprendimento):
            return True
        return interview_engine.is_session_active(richiesta.id_utente)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        from shinra.services.interview_engine import interview_engine

        utente = richiesta.id_utente

        lingua = richiesta.schemi
        if any(t in richiesta.minuscolo for t in lingua.avvii_apprendimento):
            esito = interview_engine.start_session(utente)
            richiesta.annota("learning_interview", {"action": "start"}, esito)
            return Risposta(esito["message"], extra={"learning_session": esito})

        if any(p in richiesta.minuscolo for p in lingua.interruzioni_apprendimento):
            interview_engine.stop_session(utente)
            return Risposta(lingua.dice("apprendimento_interrotto"))

        esito = await interview_engine.process_answer(utente, richiesta.testo)
        richiesta.annota("learning_interview", {"action": "answer", "answer": richiesta.testo}, esito)
        return Risposta(esito["message"], extra={"learning_session": esito})


class TimerEPromemoria(Intento):
    """«Timer di dieci minuti per la pasta», «ricordami di...»."""

    nome = "timer-e-promemoria"
    priorita = 15

    def applicabile(self, richiesta: Richiesta) -> bool:
        from shinra.services.timer_engine import timer_engine

        return timer_engine.parse_timer_or_reminder(richiesta.testo, richiesta.schemi) is not None

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        from shinra.services.timer_engine import timer_engine

        letto = timer_engine.parse_timer_or_reminder(richiesta.testo, richiesta.schemi)
        if not letto:
            return None

        if letto["type"] == "timer":
            voce = timer_engine.add_timer(
                label=letto["label"],
                duration_seconds=letto["duration_seconds"],
                user_id=richiesta.id_utente,
            )
            richiesta.annota("set_timer", letto, voce)
            return Risposta(
                richiesta.schemi.dice(
                    "timer_impostato", quantita=letto["amount"], unita=letto["unit"], etichetta=letto["label"]
                )
            )

        voce = timer_engine.add_reminder(
            text=letto["text"], remind_at_iso=letto["remind_at"], user_id=richiesta.id_utente
        )
        richiesta.annota("set_reminder", letto, voce)
        return Risposta(
            richiesta.schemi.dice("promemoria_impostato", testo=letto["text"], quando=letto["formatted_time"])
        )


registra(Apprendimento())
registra(TimerEPromemoria())
