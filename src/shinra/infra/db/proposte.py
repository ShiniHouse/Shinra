"""Il deposito delle proposte del sogno (#259, #263)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select

from shinra.infra.db.modelli_proposte import PropostaDelSogno
from shinra.infra.db.motore import sessione

CAMPI = ("id", "profilo", "tipo", "chiave", "dati", "stato", "creato_il", "deciso_il", "scade_il")

NUOVA = "nuova"
ACCETTATA = "accettata"
SCARTATA = "scartata"


def _come_dizionario(riga: PropostaDelSogno) -> dict[str, Any]:
    return {c: getattr(riga, c) for c in CAMPI}


class DepositoProposte:
    def proponi(
        self,
        profilo: str,
        tipo: str,
        chiave: str,
        dati: dict[str, Any],
        creato_il: datetime,
        scade_il: datetime,
    ) -> Optional[dict[str, Any]]:
        """Scrive una proposta nuova, **a meno che la stessa non esista gia'** (in attesa, accettata o scartata).

        Una proposta scartata non torna: chi ha detto «no» una volta non se lo sente richiedere ogni notte. Ritorna None se
        non ha scritto niente.
        """
        with sessione() as s:
            esiste = s.scalars(
                select(PropostaDelSogno.id)
                .where(PropostaDelSogno.profilo == profilo)
                .where(PropostaDelSogno.chiave == chiave)
                .where(PropostaDelSogno.scade_il > creato_il)
            ).first()
            if esiste is not None:
                return None
            riga = PropostaDelSogno(
                id=f"p_{uuid.uuid4().hex[:10]}",
                profilo=profilo,
                tipo=tipo,
                chiave=chiave,
                dati=dati,
                stato=NUOVA,
                creato_il=creato_il,
                scade_il=scade_il,
            )
            s.add(riga)
            s.flush()
            return _come_dizionario(riga)

    def del_profilo(self, profilo: str, solo_nuove: bool = True) -> list[dict[str, Any]]:
        with sessione() as s:
            query = select(PropostaDelSogno).where(PropostaDelSogno.profilo == profilo)
            if solo_nuove:
                query = query.where(PropostaDelSogno.stato == NUOVA)
            query = query.order_by(PropostaDelSogno.creato_il.desc())
            return [_come_dizionario(r) for r in s.scalars(query).all()]

    def trova(self, identificativo: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.get(PropostaDelSogno, identificativo)
            return _come_dizionario(riga) if riga is not None else None

    def decidi(self, identificativo: str, stato: str, quando: datetime) -> bool:
        """Accetta o scarta. Una proposta gia' decisa non cambia piu'."""
        with sessione() as s:
            riga = s.get(PropostaDelSogno, identificativo)
            if riga is None or riga.stato != NUOVA or stato not in (ACCETTATA, SCARTATA):
                return False
            riga.stato = stato
            riga.deciso_il = quando
            return True

    def dimentica_profilo(self, profilo: str) -> int:
        with sessione() as s:
            esito = s.execute(delete(PropostaDelSogno).where(PropostaDelSogno.profilo == profilo))
            return int(getattr(esito, "rowcount", 0) or 0)

    def purga_scadute(self, adesso: datetime) -> int:
        with sessione() as s:
            esito = s.execute(delete(PropostaDelSogno).where(PropostaDelSogno.scade_il <= adesso))
            return int(getattr(esito, "rowcount", 0) or 0)

    def conta(self) -> int:
        with sessione() as s:
            return len(s.scalars(select(PropostaDelSogno.id)).all())


proposte = DepositoProposte()
