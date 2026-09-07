import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel

from core.archivio import depositi

logger = logging.getLogger("Shinra.TimerEngine")

# Ordinati per lunghezza decrescente: nell'alternativa della regex
# "venticinque" deve essere provato prima di "venti".
NUMERI_TIMER: list[str] = []  # riempito sotto, dopo la definizione della mappa


class TimerItem(BaseModel):
    id: str
    label: str
    duration_seconds: int
    started_at: float
    expires_at: float
    user_id: str = "alessio"
    completed: bool = False


class ReminderItem(BaseModel):
    id: str
    text: str
    remind_at: str  # ISO format YYYY-MM-DDTHH:MM:SS
    user_id: str = "alessio"
    completed: bool = False
    created_at: str


class TimerEngine:
    """Timer e promemoria.

    Dalla v0.2.0 stanno nel database. Le firme restano quelle di prima: le
    usano le rotte, l'agente, lo scheduler e la skill Alexa.
    """

    # ---------------------------------------------------------------- timer

    def get_timers(self) -> List[Dict[str, Any]]:
        adesso = time.time()
        timers = depositi.timer.elenco()
        for t in timers:
            # Calcolato al momento della lettura, non salvato: un valore
            # scritto su disco sarebbe sbagliato un secondo dopo.
            t["remaining_seconds"] = max(0, int(t.get("expires_at", adesso) - adesso))
        return timers

    def save_timers(self, items: List[Dict[str, Any]]) -> None:
        """Riscrive tutti i timer. Resta per compatibilita': preferisci add/delete."""
        depositi.timer.sostituisci_tutto(items)

    def add_timer(self, label: str, duration_seconds: int, user_id: str = "alessio") -> Dict[str, Any]:
        adesso = time.time()
        t_id = f"timer_{uuid.uuid4().hex[:6]}"
        item = depositi.timer.aggiungi(
            {
                "id": t_id,
                "label": label or "Timer",
                "duration_seconds": duration_seconds,
                "started_at": adesso,
                "expires_at": adesso + duration_seconds,
                "user_id": user_id,
                "completed": False,
            }
        )
        item["remaining_seconds"] = duration_seconds

        # Il conto alla rovescia non vive piu' solo nel browser: alla scadenza
        # e' lo scheduler a suonare, anche a scheda chiusa.
        from core.scheduler import scheduler

        scheduler.programma_timer(t_id, item["label"], item["expires_at"], user_id)
        return item

    def delete_timer(self, timer_id: str) -> bool:
        from core.scheduler import scheduler

        scheduler.annulla_timer(timer_id)
        return depositi.timer.cancella(timer_id)

    def segna_completato(self, timer_id: str) -> bool:
        """Marca un timer come scaduto.

        Prima nessuno lo faceva: `completed` restava sempre falso, l'elenco
        cresceva all'infinito e ogni voce vecchia riappariva scaduta al
        caricamento successivo della dashboard.
        """
        return depositi.timer.segna_completato(timer_id)

    def pulisci_scaduti(self, conserva_ore: int = 24) -> int:
        """Rimuove i timer completati piu' vecchi del periodo di conservazione."""
        return depositi.timer.pulisci_completati(conserva_ore)

    # ----------------------------------------------------------- promemoria

    def get_reminders(self) -> List[Dict[str, Any]]:
        return depositi.promemoria.elenco()

    def save_reminders(self, items: List[Dict[str, Any]]) -> None:
        depositi.promemoria.sostituisci_tutto(items)

    def add_reminder(self, text: str, remind_at_iso: str, user_id: str = "alessio") -> Dict[str, Any]:
        r_id = f"rem_{uuid.uuid4().hex[:6]}"
        item = depositi.promemoria.aggiungi(
            {
                "id": r_id,
                "text": text,
                "remind_at": remind_at_iso,
                "user_id": user_id,
                "completed": False,
                "created_at": datetime.now().isoformat(),
            }
        )

        from core.scheduler import scheduler

        scheduler.programma_promemoria(r_id, item["text"], remind_at_iso, user_id)
        return item

    def delete_reminder(self, reminder_id: str) -> bool:
        from core.scheduler import scheduler

        scheduler.annulla_promemoria(reminder_id)
        return depositi.promemoria.cancella(reminder_id)

    def segna_promemoria_completato(self, reminder_id: str) -> bool:
        return depositi.promemoria.segna_completato(reminder_id)

    # -------------------------------------------------------------- ripresa

    def ripristina_job(self) -> dict[str, int]:
        """Riprogramma i job per timer e promemoria ancora in attesa.

        Serve dopo un riavvio: l'archivio dei job di APScheduler li conserva,
        ma un'installazione che aggiorna da una versione senza scheduler ha
        timer e promemoria in attesa e nessun job corrispondente.
        """
        from core.scheduler import scheduler

        contati = {"timer": 0, "promemoria": 0}
        for t in depositi.timer.attivi():
            if scheduler.programma_timer(
                t["id"], t.get("label", "Timer"), t.get("expires_at", 0), t.get("user_id", "")
            ):
                contati["timer"] += 1
        for r in depositi.promemoria.attivi():
            if scheduler.programma_promemoria(
                r["id"], r.get("text", ""), r.get("remind_at", ""), r.get("user_id", "")
            ):
                contati["promemoria"] += 1
        return contati

    # --- Natural Language Parser per Timer & Promemoria ---

    # I numeri che si dicono a voce. «Metti un timer di un minuto» e'
    # italiano normale: prima non veniva riconosciuto perche' la regex
    # pretendeva una cifra, e la frase finiva al modello.
    NUMERI_A_PAROLE: ClassVar[Dict[str, int]] = {
        "un": 1,
        "uno": 1,
        "una": 1,
        "due": 2,
        "tre": 3,
        "quattro": 4,
        "cinque": 5,
        "sei": 6,
        "sette": 7,
        "otto": 8,
        "nove": 9,
        "dieci": 10,
        "undici": 11,
        "dodici": 12,
        "quindici": 15,
        "venti": 20,
        "venticinque": 25,
        "trenta": 30,
        "quaranta": 40,
        "quarantacinque": 45,
        "cinquanta": 50,
        "sessanta": 60,
        "novanta": 90,
    }

    @classmethod
    def _quantita(cls, testo: str) -> Optional[int]:
        testo = (testo or "").strip().lower()
        if testo.isdigit():
            return int(testo)
        return cls.NUMERI_A_PAROLE.get(testo)

    def parse_timer_or_reminder(self, user_text: str) -> Optional[Dict[str, Any]]:
        """Estrae durata, etichetta o orario da frasi in linguaggio naturale."""
        t_lower = user_text.lower().strip()

        # "mezz'ora" non ha un numero da estrarre: si tratta a parte.
        mezzora = re.search(
            r"\btimer\s+(?:di\s+)?(?:mezz.ora|mezzora)\b(?:\s+(?:per|da|chiamato)\s+(.+))?", t_lower
        )
        if mezzora:
            etichetta = (mezzora.group(1) or "Timer").strip(" .?!,")
            return {
                "type": "timer",
                "label": etichetta.capitalize(),
                "duration_seconds": 1800,
                "amount": 30,
                "unit": "minuti",
            }

        # 1. Parsing Timer: "timer 10 minuti", "timer di 5 minuti per la pasta", "metti un timer di 30 secondi"
        numeri = "|".join(NUMERI_TIMER)
        timer_match = re.search(
            rf"\b(?:metti|imposta|avvia|crea)?\s*(?:un\s+)?timer\s+(?:di\s+)?({numeri}|\d+)\s*(minuti|minuto|secondi|secondo|ore|ora)\b(?:\s+(?:per|da|chiamato)\s+(.+))?",
            t_lower,
        )
        if timer_match:
            amount = self._quantita(timer_match.group(1))
            if amount is None:
                return None
            unit = timer_match.group(2)
            label = timer_match.group(3) or "Timer"
            label = label.strip(" .?!,")

            secs = amount
            if "minut" in unit:
                secs = amount * 60
            elif "or" in unit:
                secs = amount * 3600

            return {
                "type": "timer",
                "label": label.capitalize(),
                "duration_seconds": secs,
                "amount": amount,
                "unit": unit,
            }

        # 2. Parsing Promemoria temporizzato: "ricordami di comprare il pane alle 17:30" / "ricordami di prendere le medicine tra 20 minuti"
        remind_delta_match = re.search(
            rf"\bricordami\s+di\s+(.+?)\s+tra\s+({numeri}|\d+)\s*(minuti|minuto|ore|ora)\b", t_lower
        )
        if remind_delta_match:
            action = remind_delta_match.group(1).strip()
            amount = self._quantita(remind_delta_match.group(2)) or 0
            unit = remind_delta_match.group(3)
            delta = timedelta(minutes=amount) if "minut" in unit else timedelta(hours=amount)
            target_time = datetime.now() + delta
            return {
                "type": "reminder",
                "text": action.capitalize(),
                "remind_at": target_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "formatted_time": target_time.strftime("alle ore %H:%M"),
            }

        # I minuti sono facoltativi: «alle 18» vale quanto «alle 18:00». Chi
        # parla dice l'ora tonda molto piu' spesso di quella con i minuti.
        remind_time_match = re.search(
            r"\bricordami\s+di\s+(.+?)\s+alle\s+(\d{1,2})(?:[:.](\d{2}))?\b", t_lower
        )
        if remind_time_match:
            action = remind_time_match.group(1).strip()
            hours = int(remind_time_match.group(2))
            minutes = int(remind_time_match.group(3) or 0)
            now = datetime.now()
            target_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if target_time < now:
                target_time += timedelta(days=1)
            return {
                "type": "reminder",
                "text": action.capitalize(),
                "remind_at": target_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "formatted_time": target_time.strftime("alle ore %H:%M"),
            }

        return None


NUMERI_TIMER.extend(sorted(TimerEngine.NUMERI_A_PAROLE, key=len, reverse=True))

timer_engine = TimerEngine()
