"""Bus eventi interno: chi produce un fatto non sa chi lo consegnera'.

Serve allo scheduler. Quando un timer scade, lo scheduler non deve sapere se
l'utente e' davanti alla dashboard, ha il telefono in tasca o e' in cucina con
un Echo acceso: pubblica «questo timer e' scaduto» e i canali in ascolto
decidono cosa farne.

Senza questa separazione, aggiungere le notifiche push della v0.4.0
significherebbe tornare a modificare lo scheduler.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Union

logger = logging.getLogger("Shinra.Eventi")

Ascoltatore = Callable[["Evento"], Union[Awaitable[None], None]]


@dataclass(frozen=True)
class Evento:
    """Un fatto accaduto in casa."""

    tipo: str
    dati: dict[str, Any] = field(default_factory=dict)
    momento: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def come_json(self) -> dict[str, Any]:
        return {"tipo": self.tipo, "dati": self.dati, "momento": self.momento.isoformat()}


# Tipi di evento noti. Elencarli qui evita che un errore di battitura in una
# sottoscrizione produca un ascoltatore che non verra' mai chiamato.
TIMER_SCADUTO = "timer.scaduto"
PROMEMORIA_SCADUTO = "promemoria.scaduto"


class BusEventi:
    def __init__(self) -> None:
        self._ascoltatori: dict[str, list[Ascoltatore]] = {}

    def sottoscrivi(self, tipo: str, ascoltatore: Ascoltatore) -> Callable[[], None]:
        """Registra un ascoltatore e restituisce la funzione per rimuoverlo."""
        self._ascoltatori.setdefault(tipo, []).append(ascoltatore)

        def annulla() -> None:
            if ascoltatore in self._ascoltatori.get(tipo, []):
                self._ascoltatori[tipo].remove(ascoltatore)

        return annulla

    async def pubblica(self, evento: Evento) -> int:
        """Consegna l'evento a chi ascolta. Restituisce quanti l'hanno ricevuto.

        Un ascoltatore che solleva non impedisce agli altri di ricevere: se
        l'Echo e' irraggiungibile, la dashboard deve suonare lo stesso.
        """
        ascoltatori = list(self._ascoltatori.get(evento.tipo, []))
        if not ascoltatori:
            logger.debug("Evento %s senza ascoltatori", evento.tipo)
            return 0

        consegnati = 0
        for ascoltatore in ascoltatori:
            try:
                esito = ascoltatore(evento)
                if inspect.isawaitable(esito):
                    await esito
                consegnati += 1
            except Exception as e:
                logger.error(
                    "Ascoltatore di %s non riuscito (%s): %s",
                    evento.tipo,
                    getattr(ascoltatore, "__name__", ascoltatore),
                    e,
                    exc_info=True,
                )
        return consegnati

    def pubblica_senza_attendere(self, evento: Evento) -> None:
        """Pubblica da un contesto sincrono, senza bloccarlo."""
        try:
            asyncio.get_running_loop().create_task(self.pubblica(evento))
        except RuntimeError:
            asyncio.run(self.pubblica(evento))

    def azzera(self) -> None:
        """Solo per i test."""
        self._ascoltatori.clear()


bus = BusEventi()
