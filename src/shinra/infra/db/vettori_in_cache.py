"""I vettori dei ricordi, riletti dal database solo quando la tabella e' cambiata (#248).

Misurato il 2026-10-14 (ADR 0012): a mille ricordi il coseno costa ~70 ms e rileggere i vettori dal database, dove stanno
come JSON, ~230 ms, **a ogni richiesta**. Qui si tengono in memoria e li si rilegge solo se la *firma* della tabella e'
cambiata: quanti vettori ci sono e quando e' stato calcolato l'ultimo. La firma e' una sola interrogazione leggera, e cambia a
ogni aggiunta, ricalcolo o cancellazione (anche di orfani).

I valori restituiti sono condivisi: **non vanno modificati**. I vettori sono tuple per questo.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select

from shinra.infra.db.depositi import embedding as deposito_embedding
from shinra.infra.db.modelli import EmbeddingFatto
from shinra.infra.db.motore import sessione


class VettoriInCache:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}
        self._firma: Optional[tuple[Any, ...]] = None

    def firma(self) -> tuple[Any, ...]:
        with sessione() as s:
            riga = s.execute(select(func.count(), func.max(EmbeddingFatto.calcolato_il))).one()
            return (riga[0], riga[1], deposito_embedding.versione)

    def tutti(self) -> dict[str, dict[str, Any]]:
        firma = self.firma()
        if firma != self._firma:
            self._cache = {
                i: {**v, "vettore": tuple(v.get("vettore") or ())}
                for i, v in deposito_embedding.tutti().items()
            }
            self._firma = firma
        return self._cache

    def dimentica(self) -> None:
        """Forza la rilettura alla prossima richiesta (per i test, o dopo un ripristino che sostituisce il database)."""
        self._firma = None


vettori_in_cache = VettoriInCache()
