"""I lavori in background (#431). In un file loro, come i ricordi, i luoghi, i riassunti e le proposte."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shinra.infra.db.base import Base, DataOra, adesso


class Lavoro(Base):
    """Una richiesta che prende tempo. E' **di un profilo** e lo vede solo lui.

    Contiene il testo della richiesta e l'esito (parole della persona e di Shinra): per questo non esce in un salvataggio, si cancella con
    «dimentica tutto di me» e il registro delle azioni non lo riporta mai (dice solo che un lavoro e' nato e come e' finito).
    """

    __tablename__ = "lavori"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    proprietario: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # A cosa serve (`chat`, in seguito `pianifica`...): sceglie il modello e il tetto.
    scopo: Mapped[str] = mapped_column(String(32), nullable=False, default="chat")
    richiesta: Mapped[str] = mapped_column(Text, nullable=False)
    stato: Mapped[str] = mapped_column(String(16), nullable=False, default="in_coda", index=True)
    # 0-100, e una parola su cosa sta facendo («consulto la casa»). Mai il contenuto di una conversazione.
    avanzamento: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fase: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    tetto_secondi: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    esito: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Il perche' di un fallimento o di un'interruzione, in poche parole e senza dettagli tecnici.
    motivo: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    consegnato: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creato_il: Mapped[datetime] = mapped_column(DataOra, nullable=False, default=adesso)
    iniziato_il: Mapped[Optional[datetime]] = mapped_column(DataOra, nullable=True)
    finito_il: Mapped[Optional[datetime]] = mapped_column(DataOra, nullable=True)
