import json
import logging
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger("Shinra.TimerEngine")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TIMERS_FILE = DATA_DIR / "timers.json"
REMINDERS_FILE = DATA_DIR / "reminders.json"


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
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # --- Timers ---
    def get_timers(self) -> List[Dict[str, Any]]:
        try:
            if TIMERS_FILE.exists():
                with open(TIMERS_FILE, "r", encoding="utf-8") as f:
                    timers = json.load(f)
                    now = time.time()
                    # Aggiunge tempo rimanente calcolato
                    for t in timers:
                        remaining = max(0, int(t.get("expires_at", now) - now))
                        t["remaining_seconds"] = remaining
                    return timers
            return []
        except Exception as e:
            logger.error(f"Errore lettura timers.json: {e}")
            return []

    def save_timers(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(TIMERS_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura timers.json: {e}")

    def add_timer(self, label: str, duration_seconds: int, user_id: str = "alessio") -> Dict[str, Any]:
        timers = self.get_timers()
        now = time.time()
        t_id = f"timer_{uuid.uuid4().hex[:6]}"
        item = {
            "id": t_id,
            "label": label or "Timer",
            "duration_seconds": duration_seconds,
            "started_at": now,
            "expires_at": now + duration_seconds,
            "user_id": user_id,
            "completed": False,
            "remaining_seconds": duration_seconds,
        }
        timers.append(item)
        self.save_timers(timers)
        return item

    def delete_timer(self, timer_id: str) -> bool:
        timers = self.get_timers()
        filtered = [t for t in timers if t.get("id") != timer_id]
        if len(filtered) != len(timers):
            self.save_timers(filtered)
            return True
        return False

    # --- Reminders ---
    def get_reminders(self) -> List[Dict[str, Any]]:
        try:
            if REMINDERS_FILE.exists():
                with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Errore lettura reminders.json: {e}")
            return []

    def save_reminders(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura reminders.json: {e}")

    def add_reminder(self, text: str, remind_at_iso: str, user_id: str = "alessio") -> Dict[str, Any]:
        reminders = self.get_reminders()
        r_id = f"rem_{uuid.uuid4().hex[:6]}"
        item = {
            "id": r_id,
            "text": text,
            "remind_at": remind_at_iso,
            "user_id": user_id,
            "completed": False,
            "created_at": datetime.now().isoformat(),
        }
        reminders.append(item)
        self.save_reminders(reminders)
        return item

    def delete_reminder(self, reminder_id: str) -> bool:
        reminders = self.get_reminders()
        filtered = [r for r in reminders if r.get("id") != reminder_id]
        if len(filtered) != len(reminders):
            self.save_reminders(filtered)
            return True
        return False

    # --- Natural Language Parser per Timer & Promemoria ---
    def parse_timer_or_reminder(self, user_text: str) -> Optional[Dict[str, Any]]:
        """Estrae durata, etichetta o orario da frasi in linguaggio naturale."""
        t_lower = user_text.lower().strip()

        # 1. Parsing Timer: "timer 10 minuti", "timer di 5 minuti per la pasta", "metti un timer di 30 secondi"
        timer_match = re.search(
            r"\b(?:metti|imposta|avvia|crea)?\s*(?:un\s+)?timer\s+(?:di\s+)?(\d+)\s*(minuti|minuto|secondi|secondo|ore|ora)\b(?:\s+(?:per|da|chiamato)\s+(.+))?",
            t_lower,
        )
        if timer_match:
            amount = int(timer_match.group(1))
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
            r"\bricordami\s+di\s+(.+?)\s+tra\s+(\d+)\s*(minuti|minuto|ore|ora)\b", t_lower
        )
        if remind_delta_match:
            action = remind_delta_match.group(1).strip()
            amount = int(remind_delta_match.group(2))
            unit = remind_delta_match.group(3)
            delta = timedelta(minutes=amount) if "minut" in unit else timedelta(hours=amount)
            target_time = datetime.now() + delta
            return {
                "type": "reminder",
                "text": action.capitalize(),
                "remind_at": target_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "formatted_time": target_time.strftime("alle ore %H:%M"),
            }

        remind_time_match = re.search(r"\bricordami\s+di\s+(.+?)\s+alle\s+(\d{1,2})[:.](\d{2})\b", t_lower)
        if remind_time_match:
            action = remind_time_match.group(1).strip()
            hours = int(remind_time_match.group(2))
            minutes = int(remind_time_match.group(3))
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


timer_engine = TimerEngine()
