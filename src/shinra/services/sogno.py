"""Il sogno notturno: il materiale su cui riflette (#258).

Qui si **raccoglie** soltanto: dal registro delle azioni, dai riassunti delle conversazioni e dai ricordi, per profilo, con un
tetto (`domain/sogno.py`). Non chiama il modello, non scrive niente e non propone niente: quello e' il lavoro delle schede
successive (#260 ricordi doppi o in contraddizione, #261 abitudini), che partono da questo materiale e producono solo
**proposte**, mai modifiche.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from shinra.domain import sogno as dominio
from shinra.infra.db import depositi
from shinra.infra.db.riassunti import riassunti as deposito_riassunti
from shinra.services import registro

ORE_DEL_GIORNO = 24
VOCI_MASSIME = 1000


def materiali_del_periodo(
    profilo_id: str, adesso: Optional[datetime] = None, ore: int = ORE_DEL_GIORNO
) -> dominio.Materiale:
    """Cio' che e' successo a questo profilo nelle ultime `ore`, piu' la casa condivisa. Mai niente di un altro profilo."""
    fine = (adesso or datetime.now(timezone.utc)).replace(tzinfo=None)
    inizio = fine - timedelta(hours=ore)

    proprie = registro.voci(limite=VOCI_MASSIME, attore=profilo_id, dal=inizio, al=fine) if profilo_id else []
    della_casa = registro.voci(limite=VOCI_MASSIME, dal=inizio, al=fine, senza_attore=True)
    riassunti = deposito_riassunti.creati_tra(profilo_id, inizio, fine) if profilo_id else []

    ricordi = []
    for r in depositi.fatti.elenco():
        toccato = r.get("aggiornato_il")
        if toccato is not None and inizio <= toccato.replace(tzinfo=None) <= fine:
            ricordi.append(r)

    return dominio.raccogli(profilo_id, [*proprie, *della_casa], riassunti, ricordi, inizio, fine)
