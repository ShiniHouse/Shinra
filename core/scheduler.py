"""Scheduler persistente: timer e promemoria che scattano davvero.

Prima non esisteva alcuno scheduler lato server. Il conto alla rovescia dei
timer viveva in un `setInterval` nel browser: chiusa la scheda, nessun timer
suonava. I promemoria stavano peggio — venivano scritti in
`data/reminders.json` e nessun processo li rileggeva mai, quindi non si
attivavano in nessuna circostanza, mentre l'assistente aveva gia' risposto
«ti ricordero'».

**Persistente** significa che i job sopravvivono al riavvio del servizio: un
promemoria per le 17:30 deve scattare anche se il server e' stato riavviato
alle 17:00. E' il requisito, non un dettaglio.

Vedi docs/adr/0003-scheduler-persistente.md
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from core.eventi import PROMEMORIA_SCADUTO, TIMER_SCADUTO, Evento, bus

logger = logging.getLogger("Shinra.Scheduler")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ARCHIVIO_JOB = DATA_DIR / "scheduler.db"

# Quanto tardi un job puo' ancora essere eseguito se il servizio era fermo
# quando sarebbe dovuto scattare. La distinzione conta: un promemoria di
# mezz'ora fa va probabilmente ancora consegnato — «prendi le medicine» resta
# utile —, un timer della pasta no, perche' la pasta e' andata comunque.
TOLLERANZA_PROMEMORIA = 30 * 60
TOLLERANZA_TIMER = 60

PREFISSO_TIMER = "timer:"
PREFISSO_PROMEMORIA = "promemoria:"


async def _scade_timer(timer_id: str, etichetta: str, user_id: str) -> None:
    """Eseguita dallo scheduler alla scadenza di un timer."""
    from core.timer_engine import timer_engine

    logger.info("Timer scaduto: %s (%s)", etichetta, timer_id)
    timer_engine.segna_completato(timer_id)
    await bus.pubblica(
        Evento(
            tipo=TIMER_SCADUTO,
            dati={"id": timer_id, "etichetta": etichetta, "user_id": user_id},
        )
    )


async def _scade_promemoria(promemoria_id: str, testo: str, user_id: str) -> None:
    from core.timer_engine import timer_engine

    logger.info("Promemoria scaduto: %s (%s)", testo, promemoria_id)
    timer_engine.segna_promemoria_completato(promemoria_id)
    await bus.pubblica(
        Evento(
            tipo=PROMEMORIA_SCADUTO,
            dati={"id": promemoria_id, "testo": testo, "user_id": user_id},
        )
    )


class ServizioScheduler:
    def __init__(self) -> None:
        self._scheduler: Optional[AsyncIOScheduler] = None

    @property
    def attivo(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def avvia(self) -> None:
        if self.attivo:
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{ARCHIVIO_JOB}")},
            timezone=timezone.utc,
        )
        self._scheduler.start()
        logger.info("Scheduler avviato con %d job ripresi.", len(self._scheduler.get_jobs()))

    def ferma(self) -> None:
        if self._scheduler is not None and self._scheduler.running:
            # wait=False: allo spegnimento non si attende un job in corso, e i
            # job restano nell'archivio per la prossima accensione.
            self._scheduler.shutdown(wait=False)
        self._scheduler = None

    # ---------------------------------------------------------------- timer

    def programma_timer(self, timer_id: str, etichetta: str, scade_il: float, user_id: str) -> bool:
        return self._programma(
            identificativo=f"{PREFISSO_TIMER}{timer_id}",
            funzione=_scade_timer,
            argomenti=[timer_id, etichetta, user_id],
            quando=datetime.fromtimestamp(scade_il, tz=timezone.utc),
            tolleranza=TOLLERANZA_TIMER,
        )

    def programma_promemoria(self, promemoria_id: str, testo: str, quando_iso: str, user_id: str) -> bool:
        try:
            quando = datetime.fromisoformat(quando_iso)
        except ValueError:
            logger.error("Momento illeggibile per il promemoria %s: %r", promemoria_id, quando_iso)
            return False
        if quando.tzinfo is None:
            # Gli orari salvati sono locali: si interpretano come tali.
            quando = quando.astimezone()
        return self._programma(
            identificativo=f"{PREFISSO_PROMEMORIA}{promemoria_id}",
            funzione=_scade_promemoria,
            argomenti=[promemoria_id, testo, user_id],
            quando=quando,
            tolleranza=TOLLERANZA_PROMEMORIA,
        )

    def annulla(self, identificativo: str) -> bool:
        if not self.attivo:
            return False
        try:
            self._scheduler.remove_job(identificativo)
            return True
        except Exception:
            return False

    def annulla_timer(self, timer_id: str) -> bool:
        return self.annulla(f"{PREFISSO_TIMER}{timer_id}")

    def annulla_promemoria(self, promemoria_id: str) -> bool:
        return self.annulla(f"{PREFISSO_PROMEMORIA}{promemoria_id}")

    def job_programmati(self) -> list[dict[str, Any]]:
        if not self.attivo:
            return []
        return [
            {
                "id": j.id,
                "prossima_esecuzione": j.next_run_time.isoformat() if j.next_run_time else None,
            }
            for j in self._scheduler.get_jobs()
        ]

    # -------------------------------------------------------------- interno

    def _programma(
        self,
        identificativo: str,
        funzione: Any,
        argomenti: list[Any],
        quando: datetime,
        tolleranza: int,
    ) -> bool:
        if not self.attivo:
            logger.warning("Scheduler non attivo: %s non programmato.", identificativo)
            return False

        adesso = datetime.now(timezone.utc)
        if quando <= adesso - timedelta(seconds=tolleranza):
            logger.info("%s e' gia' scaduto oltre la tolleranza: non programmato.", identificativo)
            return False

        self._scheduler.add_job(
            funzione,
            trigger=DateTrigger(run_date=quando),
            args=argomenti,
            id=identificativo,
            replace_existing=True,
            misfire_grace_time=tolleranza,
            coalesce=True,
        )
        logger.info("%s programmato per %s", identificativo, quando.isoformat())
        return True


scheduler = ServizioScheduler()
