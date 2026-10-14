"""Il deposito dei luoghi (#342). A parte perche' `depositi.py` ha gia' il suo tetto di righe."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select, update

from shinra.infra.db.depositi import Deposito, _come_dizionario
from shinra.infra.db.modelli import Luogo
from shinra.infra.db.motore import sessione


class DepositoLuoghi(Deposito):
    modello = Luogo
    campi = (
        "id",
        "nome",
        "tipo",
        "principale",
        "latitudine",
        "longitudine",
        "raggio_m",
        "citta",
        "origine",
        "precisione_m",
        "creato_il",
    )
    ordine = "creato_il"

    def crea(self, dati: dict[str, Any], principale: bool = False) -> dict[str, Any]:
        """Aggiunge un luogo. Il primo in assoluto e' il principale; se si chiede un nuovo principale, il vecchio smette di esserlo."""
        with sessione() as s:
            esistono = s.scalars(select(Luogo.id).limit(1)).first() is not None
            fa_principale = bool(principale) or not esistono
            if fa_principale:
                s.execute(update(Luogo).values(principale=False))
            riga = Luogo(
                id=f"l_{uuid.uuid4().hex[:8]}",
                principale=fa_principale,
                **{
                    c: dati[c] for c in self.campi if c in dati and c not in ("id", "principale", "creato_il")
                },
            )
            s.add(riga)
            s.flush()
            return _come_dizionario(riga, self.campi)

    def imposta_principale(self, identificativo: str) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.get(Luogo, identificativo)
            if riga is None:
                return None
            s.execute(update(Luogo).values(principale=False))
            riga.principale = True
            s.flush()
            return _come_dizionario(riga, self.campi)

    def principale(self) -> Optional[dict[str, Any]]:
        with sessione() as s:
            riga = s.scalars(select(Luogo).where(Luogo.principale.is_(True))).first()
            return _come_dizionario(riga, self.campi) if riga else None

    def cancella_e_riassegna(self, identificativo: str) -> bool:
        """Cancella un luogo; se era il principale, lo diventa il piu' vecchio fra quelli che restano."""
        with sessione() as s:
            riga = s.get(Luogo, identificativo)
            if riga is None:
                return False
            era_principale = bool(riga.principale)
            s.delete(riga)
            s.flush()
            if era_principale:
                erede = s.scalars(select(Luogo).order_by(Luogo.creato_il)).first()
                if erede is not None:
                    erede.principale = True
            return True


luoghi = DepositoLuoghi()
