"""I riassunti delle conversazioni (#255, ADR 0010). In un file loro, come i ricordi e i luoghi."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from shinra.infra.db.base import Base, DataOra, adesso


class RiassuntoConversazione(Base):
    """Cio' che resta di una conversazione dopo che i turni grezzi sono usciti dalla finestra.

    **Non e' il testo della conversazione**: e' un riassunto scritto dal codice dai fatti verificati (cosa e' stato chiesto
    e quali azioni sono state eseguite), per profilo, con una scadenza. Non esce in un salvataggio e non passa mai da un
    servizio esterno.
    """

    __tablename__ = "riassunti_conversazione"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    profilo: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    creato_il: Mapped[datetime] = mapped_column(DataOra, nullable=False, default=adesso)
    scade_il: Mapped[datetime] = mapped_column(DataOra, nullable=False, index=True)
    testo: Mapped[str] = mapped_column(Text, nullable=False)
    turni: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # «codice» (scritto dai fatti verificati) o «modello» (reso piu' leggibile da Ollama, #256).
    origine: Mapped[str] = mapped_column(String(16), nullable=False, default="codice")
    modello: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # Cio' da cui nasce il testo: le richieste e le azioni verificate. Serve a controllare una riscrittura (#256).
    struttura: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON(none_as_null=True), nullable=True)
