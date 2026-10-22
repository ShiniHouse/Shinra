"""Il deposito dei lavori in background (#431)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import delete, select

from shinra.domain import lavori as dominio
from shinra.infra.db.modelli_lavori import Lavoro
from shinra.infra.db.motore import sessione

CAMPI = (
    "id",
    "proprietario",
    "scopo",
    "richiesta",
    "stato",
    "avanzamento",
    "fase",
    "tetto_secondi",
    "esito",
    "motivo",
    "consegnato",
    "creato_il",
    "iniziato_il",
    "finito_il",
)


def _come_dizionario(riga: Lavoro) -> dict[str, Any]:
    return {c: getattr(riga, c) for c in CAMPI}


class DepositoLavori:
    def crea(self, proprietario: str, richiesta: str, scopo: str, tetto_secondi: int) -> dict[str, Any]:
        with sessione() as s:
            riga = Lavoro(
                id=f"l_{uuid.uuid4().hex[:10]}",
                proprietario=proprietario,
                scopo=scopo,
                richiesta=richiesta,
                stato=dominio.IN_CODA,
                tetto_secondi=tetto_secondi,
            )
            s.add(riga)
            s.flush()
            return _come_dizionario(riga)

    def trova(self, identificativo: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.get(Lavoro, identificativo)
            return _come_dizionario(riga) if riga is not None else None

    def del_profilo(self, proprietario: str, limite: int = 50) -> list[dict[str, Any]]:
        with sessione() as s:
            query = (
                select(Lavoro)
                .where(Lavoro.proprietario == proprietario)
                .order_by(Lavoro.creato_il.desc())
                .limit(limite)
            )
            return [_come_dizionario(r) for r in s.scalars(query).all()]

    def attivi(self) -> list[dict[str, Any]]:
        """I lavori non ancora finiti, di tutti: serve all'avvio per dichiarare interrotti quelli rimasti a meta'."""
        with sessione() as s:
            query = select(Lavoro).where(Lavoro.stato.in_((dominio.IN_CODA, dominio.IN_CORSO)))
            return [_come_dizionario(r) for r in s.scalars(query).all()]

    def passa_a(
        self, identificativo: str, stato: str, quando: datetime, motivo: str = "", esito: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Cambia stato **solo se la transizione e' consentita**; ritorna il lavoro aggiornato, o `None` se non si poteva."""
        with sessione() as s:
            riga = s.get(Lavoro, identificativo)
            if riga is None or not dominio.puo_passare(riga.stato, stato):
                return None
            riga.stato = stato
            if stato == dominio.IN_CORSO:
                riga.iniziato_il = quando
            if dominio.e_terminale(stato):
                riga.finito_il = quando
                if stato == dominio.FATTO:
                    riga.avanzamento = 100
            if motivo:
                riga.motivo = motivo[:200]
            if esito is not None:
                riga.esito = esito
            s.flush()
            return _come_dizionario(riga)

    def avanza(self, identificativo: str, avanzamento: int, fase: str = "") -> bool:
        with sessione() as s:
            riga = s.get(Lavoro, identificativo)
            if riga is None or dominio.e_terminale(riga.stato):
                return False
            riga.avanzamento = dominio.avanzamento_valido(riga.avanzamento, avanzamento)
            if fase:
                riga.fase = fase[:80]
            return True

    def segna_consegnato(self, identificativo: str) -> None:
        with sessione() as s:
            riga = s.get(Lavoro, identificativo)
            if riga is not None:
                riga.consegnato = True

    def dimentica_profilo(self, proprietario: str) -> int:
        """Toglie tutti i lavori di un profilo (richiesta ed esito compresi): «dimentica tutto di me» non lascia copie."""
        with sessione() as s:
            esito = s.execute(delete(Lavoro).where(Lavoro.proprietario == proprietario))
            return int(getattr(esito, "rowcount", 0) or 0)


lavori = DepositoLavori()
