"""Il modello dei luoghi (#342). In un file suo perche' `modelli.py` ha gia' il suo tetto di righe."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shinra.infra.db.base import Base


class Luogo(Base):
    """Un luogo registrato: la casa principale, un'altra abitazione, il lavoro (issue #342).

    Le coordinate sono quelle **effettive** di uno smartphone o di un PC, non una citta' scritta a mano. Sono un dato
    delicato: stanno solo qui, non entrano nei log, nel registro delle azioni, nel grafo, e non escono in un
    salvataggio. Questa tabella dice dove sono i luoghi; **non** dove sono le persone.
    """

    __tablename__ = "luoghi"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(16), nullable=False, default="abitazione")
    principale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latitudine: Mapped[float] = mapped_column(Float, nullable=False)
    longitudine: Mapped[float] = mapped_column(Float, nullable=False)
    # Entro quanti metri «sei li'». Non scende sotto la precisione con cui il luogo e' stato registrato.
    raggio_m: Mapped[int] = mapped_column(Integer, nullable=False, default=150)
    citta: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Da dove sono arrivate le coordinate: "telefono" (Home Assistant), "browser" (geolocalizzazione, meno precisa).
    origine: Mapped[str] = mapped_column(String(16), nullable=False, default="browser")
    precisione_m: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    creato_il: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
