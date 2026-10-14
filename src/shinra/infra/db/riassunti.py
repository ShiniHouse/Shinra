"""Il deposito dei riassunti di conversazione (#255, ADR 0010)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select

from shinra.infra.db.modelli_riassunti import RiassuntoConversazione
from shinra.infra.db.motore import sessione

CAMPI = ("id", "profilo", "creato_il", "scade_il", "testo", "turni", "origine", "modello")


def _come_dizionario(riga: RiassuntoConversazione) -> dict[str, Any]:
    return {c: getattr(riga, c) for c in CAMPI}


class DepositoRiassunti:
    def aggiungi(
        self,
        profilo: str,
        testo: str,
        turni: int,
        creato_il: datetime,
        scade_il: datetime,
        origine: str = "codice",
        modello: str = "",
    ) -> dict[str, Any]:
        with sessione() as s:
            riga = RiassuntoConversazione(
                id=f"r_{uuid.uuid4().hex[:10]}",
                profilo=profilo,
                testo=testo,
                turni=turni,
                creato_il=creato_il,
                scade_il=scade_il,
                origine=origine,
                modello=modello,
            )
            s.add(riga)
            s.flush()
            return _come_dizionario(riga)

    def del_profilo(
        self, profilo: str, ancora_validi_a: Optional[datetime] = None, massimo: int = 3
    ) -> list[dict[str, Any]]:
        """I riassunti di un profilo, i piu' recenti per primi, escludendo quelli scaduti a `ancora_validi_a`."""
        with sessione() as s:
            query = select(RiassuntoConversazione).where(RiassuntoConversazione.profilo == profilo)
            if ancora_validi_a is not None:
                query = query.where(RiassuntoConversazione.scade_il > ancora_validi_a)
            query = query.order_by(RiassuntoConversazione.creato_il.desc()).limit(massimo)
            return [_come_dizionario(r) for r in s.scalars(query).all()]

    def dimentica_profilo(self, profilo: str) -> int:
        with sessione() as s:
            esito = s.execute(delete(RiassuntoConversazione).where(RiassuntoConversazione.profilo == profilo))
            return int(getattr(esito, "rowcount", 0) or 0)

    def purga_scaduti(self, adesso: datetime) -> int:
        with sessione() as s:
            esito = s.execute(delete(RiassuntoConversazione).where(RiassuntoConversazione.scade_il <= adesso))
            return int(getattr(esito, "rowcount", 0) or 0)

    def tutti(self) -> list[dict[str, Any]]:
        with sessione() as s:
            return [_come_dizionario(r) for r in s.scalars(select(RiassuntoConversazione)).all()]

    def conta(self) -> int:
        return len(self.tutti())


riassunti = DepositoRiassunti()
