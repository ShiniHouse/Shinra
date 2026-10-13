"""Far girare un compito di notte senza far danni (#259).

Il sogno (fase D) lavora su un mini-PC senza GPU, mentre la casa dorme: la lentezza non conta, contano il **tempo massimo**
e il **non disturbare**. Questo modulo non sa cosa fa il compito; sa solo quando *non* farlo e come fermarlo:

- **una volta per giornata**: la chiave e' (nome, data). Eseguito due volte nella stessa notte, la seconda non fa niente;
- **salta** se il modello non risponde o la macchina e' carica, e lo dice: si riprova la notte dopo;
- **si interrompe** allo scadere del tempo massimo, in modo pulito (il compito riceve la cancellazione);
- **non fa mai cadere il servizio**: un errore nel compito si registra e finisce li';
- **lascia una traccia**: stato, motivo e durata, nel log e nell'esito restituito.

Chi ha bisogno che la garanzia «una volta per giornata» sopravviva a un riavvio la deve avere anche dove scrive (la chiave
per data e' pensata per questo); qui la memoria della giornata e' del processo.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("Shinra.Notte")

# Oltre questo carico per core la macchina sta facendo altro: di notte non si aggiunge lavoro.
CARICO_MASSIMO_PER_CORE = 0.8

FATTO = "fatto"
GIA_FATTO = "gia_fatto"
SALTATO = "saltato"
INTERROTTO = "interrotto"
ERRORE = "errore"


@dataclass(frozen=True)
class Esito:
    nome: str
    giornata: str
    stato: str
    motivo: str = ""
    durata: float = 0.0
    risultato: Any = None

    def come_riga(self) -> str:
        dettaglio = f" ({self.motivo})" if self.motivo else ""
        return f"{self.nome} {self.giornata}: {self.stato}{dettaglio} in {self.durata:.1f}s"


def carico_per_core() -> Optional[float]:
    """Il carico medio dell'ultimo minuto diviso i core; `None` dove il sistema non lo dice (Windows)."""
    leggi = getattr(os, "getloadavg", None)
    if leggi is None:
        return None
    try:
        return float(leggi()[0]) / (os.cpu_count() or 1)
    except OSError:
        return None


async def modello_risponde() -> bool:
    from shinra.infra.llm.ollama import OllamaClient

    try:
        return (await OllamaClient().check_health()).get("status") == "online"
    except Exception:  # un modello che non risponde non e' un errore: e' un motivo per saltare
        return False


class CompitoNotturno:
    def __init__(self) -> None:
        self._fatti: set[tuple[str, str]] = set()

    async def esegui(
        self,
        nome: str,
        compito: Callable[[], Awaitable[Any]],
        tetto_secondi: float,
        *,
        adesso: Optional[datetime] = None,
        serve_il_modello: bool = True,
        modello_ok: Callable[[], Awaitable[bool]] = modello_risponde,
        carico: Callable[[], Optional[float]] = carico_per_core,
    ) -> Esito:
        giornata = (adesso or datetime.now()).date().isoformat()
        chiave = (nome, giornata)

        def esito(stato: str, motivo: str = "", partenza: float = 0.0, risultato: Any = None) -> Esito:
            e = Esito(
                nome, giornata, stato, motivo, (time.monotonic() - partenza) if partenza else 0.0, risultato
            )
            (logger.warning if stato in (INTERROTTO, ERRORE) else logger.info)(
                "Compito notturno: %s", e.come_riga()
            )
            return e

        if chiave in self._fatti:
            return esito(GIA_FATTO, "gia' eseguito in questa giornata")

        if serve_il_modello and not await modello_ok():
            return esito(SALTATO, "il modello non risponde: si riprova la notte dopo")

        letto = carico()
        if letto is not None and letto > CARICO_MASSIMO_PER_CORE:
            return esito(SALTATO, f"la macchina e' carica ({letto:.2f} per core): si riprova la notte dopo")

        partenza = time.monotonic()
        try:
            risultato = await asyncio.wait_for(compito(), timeout=tetto_secondi)
        except asyncio.TimeoutError:
            return esito(INTERROTTO, f"superato il tempo massimo di {tetto_secondi:g}s", partenza)
        except Exception as errore:
            logger.exception("Il compito notturno %s e' fallito", nome)
            return esito(ERRORE, f"{type(errore).__name__}: {errore}", partenza)

        self._fatti.add(chiave)
        return esito(FATTO, "", partenza, risultato)

    def giornate_fatte(self, nome: str) -> list[str]:
        return sorted(g for n, g in self._fatti if n == nome)

    def dimentica(self, nome: str, giornata: date) -> None:
        self._fatti.discard((nome, giornata.isoformat()))


compito_notturno = CompitoNotturno()
