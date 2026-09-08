"""Chi guarda la casa mentre la simulazione finge.

La capacita' — pianificare la serata, accendere, spegnere — sta in
`skills/simulazione.py`. Qui c'e' solo cio' che reagisce da solo: **smettere
appena qualcuno rientra.**

Non e' una cortesia. Una casa che continua a fingere mentre ci vive qualcuno
accende e spegne le luci addosso alle persone, ed e' il modo piu' rapido
perche' la funzione venga disattivata per sempre. La presenza (issue #22) era
il pezzo che mancava per poterlo fare.

Il servizio ascolta un evento del bus e non conosce chi lo pubblica: la
simulazione non sa niente della presenza, e la presenza non sa niente della
simulazione.

Riferimento: issue #23.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from shinra.domain.eventi import CASA_ABITATA, Evento, bus
from shinra.skills.simulazione import simulazione

logger = logging.getLogger("Shinra.Simulazione")


class ServizioSimulazione:
    def __init__(self) -> None:
        self._annulla_ascolto: Optional[Any] = None

    def avvia(self) -> bool:
        if self._annulla_ascolto is not None:
            return False
        self._annulla_ascolto = bus.sottoscrivi(CASA_ABITATA, self._qualcuno_e_tornato)
        logger.info("Simulazione di presenza: in ascolto dei rientri.")
        return True

    def ferma(self) -> None:
        if self._annulla_ascolto is not None:
            self._annulla_ascolto()
            self._annulla_ascolto = None

    def _qualcuno_e_tornato(self, evento: Evento) -> None:
        if not simulazione.attiva:
            return
        logger.info("Qualcuno e' rientrato: smetto di fingere.")
        asyncio.get_event_loop().create_task(simulazione.spegni("rientro"))


servizio_simulazione = ServizioSimulazione()
