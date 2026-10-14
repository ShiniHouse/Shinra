"""La base comune di tutti i modelli, e l'ora di adesso: in un file suo perche' i modelli stanno in piu' file."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


def adesso() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class DataOra(TypeDecorator):
    """Una data e ora che accetta anche il testo ISO che un salvataggio JSON ha scritto.

    Un archivio di backup scrive le date come testo (`default=str`); riscriverle nel database cosi' com'e' farebbe
    fallire SQLite, che pretende un oggetto data. Cosi' un ripristino non deve sapere quali colonne sono date.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        return value
