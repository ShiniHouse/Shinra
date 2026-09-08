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

    INNESCHI = (
        "kyra istruisci",
        "kira istruisci",
        "chira istruisci",
        "shinra istruisci",
        "istruisci",
        "modalità apprendimento",
        "impara la casa",
        "intervista casa",
        "insegna abitudini",
        "voglio insegnarti",
        "impara abitudini",
    )
    INTERRUZIONI = (
        "annulla intervista",
        "ferma intervista",
        "esci da apprendimento",
        "stop intervista",
        "annulla",
    )

    def applicabile(self, richiesta: Richiesta) -> bool:
        from shinra.services.interview_engine import interview_engine

        if any(t in richiesta.minuscolo for t in self.INNESCHI):
            return True
        return interview_engine.is_session_active(richiesta.id_utente)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        from shinra.services.interview_engine import interview_engine

        utente = richiesta.id_utente

        if any(t in richiesta.minuscolo for t in self.INNESCHI):
            esito = interview_engine.start_session(utente)
            richiesta.annota("learning_interview", {"action": "start"}, esito)
            return Risposta(esito["message"], extra={"learning_session": esito})

        if any(p in richiesta.minuscolo for p in self.INTERRUZIONI):
            interview_engine.stop_session(utente)
            return Risposta("Modalità Apprendimento interrotta. Possiamo riprendere quando vuoi.")

        esito = await interview_engine.process_answer(utente, richiesta.testo)
        richiesta.annota("learning_interview", {"action": "answer", "answer": richiesta.testo}, esito)
        return Risposta(esito["message"], extra={"learning_session": esito})


class TimerEPromemoria(Intento):
    """«Timer di dieci minuti per la pasta», «ricordami di...»."""

    nome = "timer-e-promemoria"
    priorita = 15

    def applicabile(self, richiesta: Richiesta) -> bool:
        from shinra.services.timer_engine import timer_engine

        return timer_engine.parse_timer_or_reminder(richiesta.testo) is not None

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        from shinra.services.timer_engine import timer_engine

        letto = timer_engine.parse_timer_or_reminder(richiesta.testo)
        if not letto:
            return None

        if letto["type"] == "timer":
            voce = timer_engine.add_timer(
                label=letto["label"],
                duration_seconds=letto["duration_seconds"],
                user_id=richiesta.id_utente,
            )
            richiesta.annota("set_timer", letto, voce)
            return Risposta(f"Timer di {letto['amount']} {letto['unit']} impostato per {letto['label']}.")

        voce = timer_engine.add_reminder(
            text=letto["text"], remind_at_iso=letto["remind_at"], user_id=richiesta.id_utente
        )
        richiesta.annota("set_reminder", letto, voce)
        return Risposta(f"Perfetto, ti ricorderò di {letto['text']} {letto['formatted_time']}.")


registra(Apprendimento())
registra(TimerEPromemoria())
