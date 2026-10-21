"""Cio' che e' stato cancellato e non deve tornare: gli identificativi dei ricordi dimenticati (ADR 0009, punto 6)."""

from __future__ import annotations

from sqlalchemy import select

from shinra.infra.db.modelli_ricordi import RicordoCancellato
from shinra.infra.db.motore import sessione


def segna(identificativo: str) -> None:
    """Ricorda che questo ricordo e' stato cancellato. Chiamarla due volte non fa danni."""
    with sessione() as s:
        if s.get(RicordoCancellato, identificativo) is None:
            s.add(RicordoCancellato(id=identificativo))


def cancellati() -> set[str]:
    with sessione() as s:
        return set(s.scalars(select(RicordoCancellato.id)).all())
