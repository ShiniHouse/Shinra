"""Le proposte del sogno (#259, #260, #261, #263). In un file loro, come i ricordi, i luoghi e i riassunti."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from shinra.infra.db.base import Base, DataOra, adesso


class PropostaDelSogno(Base):
    """Cio' che Shinra ha notato di notte e propone, senza fare niente: una persona accetta o scarta.

    Non contiene frasi: solo **dati verificati dal codice** (di che tipo, su cosa, in quali giorni). Il testo che si legge in
    interfaccia lo compone chi la mostra, nella lingua della persona. E' di un profilo (o della casa, `profilo` vuoto) e lo
    vede solo lui. Non esce in un salvataggio: si rifa' ogni notte dal registro e dai ricordi.
    """

    __tablename__ = "proposte_del_sogno"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profilo: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # «abitudine», «ricordo_doppio», «ricordo_contraddittorio»: chi la mostra sa come raccontarla.
    tipo: Mapped[str] = mapped_column(String(32), nullable=False)
    # Identifica la proposta, non la notte: serve a non riproporre ogni notte la stessa cosa (e a non riproporre cio' che e'
    # stato scartato).
    chiave: Mapped[str] = mapped_column(String(200), nullable=False)
    dati: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), nullable=True)
    # «nuova», «accettata», «scartata».
    stato: Mapped[str] = mapped_column(String(16), nullable=False, default="nuova")
    creato_il: Mapped[datetime] = mapped_column(DataOra, nullable=False, default=adesso)
    deciso_il: Mapped[Optional[datetime]] = mapped_column(DataOra, nullable=True)
    scade_il: Mapped[datetime] = mapped_column(DataOra, nullable=False, index=True)
