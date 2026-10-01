"""Chi racconta il ciclo dell'agente sul bus (issue #188).

L'agente chiama questi metodi nei suoi punti di passaggio; qui si decide cosa
pubblicare. **Raccontare non puo' rallentare ne' rompere una risposta**: ogni
metodo costruisce l'evento, lo consegna al bus in un compito a parte e non
attende nessuno; qualunque eccezione si ferma qui e finisce nel log.

Il contenuto della richiesta non entra mai: vedi `domain/eventi_agente.py`.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, Iterable, Mapping, Optional, Set

from shinra.domain import eventi_agente as ev
from shinra.domain.eventi import bus

logger = logging.getLogger("Shinra.Cronaca")

# I compiti in volo: l'event loop tiene solo un riferimento debole, e un
# compito senza padrone puo' sparire a meta' consegna.
_in_volo: Set["asyncio.Task[Any]"] = set()


class Cronaca:
    """Il racconto di una richiesta: ha un identificativo suo e un proprietario."""

    def __init__(self, profilo: Optional[str]) -> None:
        self.profilo = profilo
        self.richiesta = uuid.uuid4().hex[:12]

    def _pubblica(self, tipo: str, nodi: Iterable[str] = (), **extra: Any) -> None:
        try:
            evento = ev.evento(tipo, profilo=self.profilo, richiesta=self.richiesta, nodi=nodi, **extra)
            compito = asyncio.get_running_loop().create_task(bus.pubblica(evento))
            _in_volo.add(compito)
            compito.add_done_callback(_in_volo.discard)
        except Exception as errore:  # raccontare non deve mai costare una risposta
            logger.debug("Evento %s non pubblicato: %s", tipo, errore)

    def richiesta_ricevuta(self) -> None:
        # Ancora non si sa chi rispondera': un intento o il modello. Nessun nodo.
        self._pubblica(ev.RICHIESTA_RICEVUTA)

    def conoscenza_consultata(self, fatti: Iterable[Mapping[str, Any]]) -> None:
        nodi = ev.nodi_dei_fatti(fatti)
        if nodi:
            self._pubblica(ev.CONOSCENZA_CONSULTATA, nodi)

    def strumento(
        self, nome: str, argomenti: Optional[Dict[str, Any]], esito: Optional[Dict[str, Any]]
    ) -> None:
        """Lo strumento scelto e, se comanda qualcosa, il dispositivo toccato."""
        if not nome:
            return
        self._pubblica(ev.SKILL_SCELTA, [ev.nodo_strumento(nome)])
        entita = (argomenti or {}).get("entity_id") if isinstance(argomenti, dict) else None
        if nome in ev.STRUMENTI_CHE_COMANDANO and isinstance(entita, str) and entita.strip():
            riuscito = not (isinstance(esito, dict) and (esito.get("error") or esito.get("success") is False))
            self._pubblica(ev.DISPOSITIVO_COMANDATO, [ev.nodo_dispositivo(entita.strip())], riuscito=riuscito)

    def azioni(self, azioni: Iterable[Dict[str, Any]]) -> None:
        """Le azioni che un intento ha gia' compiuto senza passare dal modello."""
        for azione in azioni:
            self.strumento(str(azione.get("tool") or ""), azione.get("args"), azione.get("result"))

    def risposta_data(self, dal_modello: bool) -> None:
        self._pubblica(ev.RISPOSTA_DATA, [ev.NODO_MODELLO] if dal_modello else [])

    def errore(self, motivo: str) -> None:
        self._pubblica(ev.ERRORE, [ev.NODO_MODELLO], motivo=motivo)
