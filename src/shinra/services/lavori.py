"""I lavori in background: «ci penso» (#431, ADR 0013).

Una richiesta che prende tempo non blocca la chat: diventa un **lavoro** che gira in coda, con un tetto di tempo, e consegna l'esito
quando ha finito. Questo servizio non sa cosa fa il lavoro: riceve una funzione asincrona e la fa girare con le garanzie dell'ADR:

- **uno alla volta** per i lavori pesanti (`asyncio.Semaphore(1)`): su un server senza GPU un lavoro lungo compete con la chat e con
  Home Assistant, e due insieme sono peggio di uno dopo l'altro;
- **un tetto di tempo** che nessuno supera: allo scadere il lavoro e' `fallito` con il motivo «tetto di tempo», e la funzione riceve la
  cancellazione;
- **annullabile** da chi lo ha chiesto, in coda o in corso;
- **di un profilo**: ognuno vede, annulla e legge l'esito solo dei propri (per gli altri un lavoro «non esiste»);
- **onesto al riavvio**: un lavoro che era in coda o in corso quando il servizio si e' fermato non si riprende da solo (non si sa a che
  punto fosse, e potrebbe aver comandato qualcosa): diventa `interrotto`, e la persona decide se rifarlo;
- **nel registro** nasce e finisce (`lavoro.creato`, `lavoro.finito`) con id, stato e durata, **mai** il testo della richiesta o dell'esito.

La funzione puo' dichiarare l'avanzamento con la callback che riceve: sale e basta.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from shinra.config import settings as impostazioni
from shinra.domain import lavori as dominio
from shinra.infra.db.lavori import lavori as deposito
from shinra.services import registro

logger = logging.getLogger("Shinra.Lavori")

# Dichiarare l'avanzamento: `avanza(40, "consulto la casa")`.
Avanza = Callable[[int, str], None]
Funzione = Callable[[Avanza], Awaitable[str]]
# Chiamata quando un lavoro finisce (con qualunque stato terminale), per consegnare l'esito: notifica, evento, chat.
AllaFine = Callable[[dict[str, Any]], Awaitable[None]]

MASSIMO_ATTIVI_PER_PROFILO = 5


class LavoroNonTrovato(Exception):
    pass


class TroppiLavori(Exception):
    pass


def _adesso() -> datetime:
    return datetime.now(timezone.utc)


def _come_si_vede(lavoro: dict[str, Any]) -> dict[str, Any]:
    """Cio' che vede chi lo ha chiesto: niente di tecnico, e l'esito solo quando c'e'."""
    return {
        "id": lavoro["id"],
        "scopo": lavoro["scopo"],
        "richiesta": lavoro["richiesta"],
        "stato": lavoro["stato"],
        "avanzamento": lavoro["avanzamento"],
        "fase": lavoro["fase"],
        "esito": lavoro["esito"],
        "motivo": lavoro["motivo"],
        "creato_il": lavoro["creato_il"],
        "finito_il": lavoro["finito_il"],
    }


class ServizioLavori:
    def __init__(self) -> None:
        self._pesanti = asyncio.Semaphore(1)
        self._compiti: dict[str, asyncio.Task[None]] = {}
        self._alla_fine: Optional[AllaFine] = None
        # Vero mentre il servizio si spegne: una cancellazione allora non e' un annullo della persona, e' un'interruzione.
        self._fermando = False

    def alla_fine(self, funzione: Optional[AllaFine]) -> None:
        """Chi consegna l'esito (notifiche, eventi). Se non c'e', l'esito si legge comunque con `trova`."""
        self._alla_fine = funzione

    # ------------------------------------------------------------------ avvio

    def riconcilia(self) -> int:
        """All'avvio: i lavori rimasti in coda o in corso non si riprendono. Diventano `interrotto`, e lo dicono."""
        quanti = 0
        for lavoro in deposito.attivi():
            aggiornato = deposito.passa_a(lavoro["id"], dominio.INTERROTTO, _adesso(), dominio.MOTIVO_RIAVVIO)
            if aggiornato is not None:
                quanti += 1
                registro.registra(
                    "lavoro.finito",
                    esito=registro.ESITO_ERRORE,
                    dettagli={"id": lavoro["id"], "stato": "interrotto"},
                )
        if quanti:
            logger.warning("%d lavori erano rimasti a meta': segnati come interrotti.", quanti)
        return quanti

    # ------------------------------------------------------------------ richieste

    def prendi_in_carico(
        self, proprietario: str, richiesta: str, funzione: Funzione, scopo: str = "chat"
    ) -> dict[str, Any]:
        """Mette un lavoro in coda e lo fa partire senza aspettarlo. Ritorna subito, col lavoro com'e' adesso."""
        if not proprietario:
            raise ValueError("un lavoro ha un proprietario")
        attivi = [
            lv
            for lv in deposito.del_profilo(proprietario)
            if lv["stato"] in (dominio.IN_CODA, dominio.IN_CORSO)
        ]
        if len(attivi) >= MASSIMO_ATTIVI_PER_PROFILO:
            raise TroppiLavori(f"ci sono gia' {len(attivi)} lavori in corso")
        tetto = dominio.tetto_valido(impostazioni.settings.lavori.tetto_secondi)
        lavoro = deposito.crea(proprietario, richiesta, scopo, tetto)
        registro.registra(
            "lavoro.creato",
            attore=proprietario,
            dettagli={"id": lavoro["id"], "scopo": scopo, "tetto_s": tetto},
        )
        self._compiti[lavoro["id"]] = asyncio.get_running_loop().create_task(
            self._esegui(lavoro["id"], funzione, tetto)
        )
        return _come_si_vede(lavoro)

    async def _esegui(self, identificativo: str, funzione: Funzione, tetto: int) -> None:
        stato, motivo, esito = dominio.FALLITO, "", ""
        inizio = time.monotonic()
        try:
            async with self._pesanti:
                # Se nel frattempo e' stato annullato mentre aspettava il turno, non parte.
                if deposito.passa_a(identificativo, dominio.IN_CORSO, _adesso()) is None:
                    return

                def avanza(valore: int, fase: str = "") -> None:
                    deposito.avanza(identificativo, valore, fase)

                esito = await asyncio.wait_for(funzione(avanza), timeout=tetto)
                stato = dominio.FATTO
        except asyncio.TimeoutError:
            motivo = dominio.MOTIVO_TETTO
        except asyncio.CancelledError:
            if self._fermando:
                stato, motivo = dominio.INTERROTTO, dominio.MOTIVO_RIAVVIO
            else:
                stato, motivo = dominio.ANNULLATO, "annullato"
        except Exception as errore:
            # Il dettaglio resta nel log: alla persona basta sapere che non e' riuscito, non un errore tecnico.
            logger.error("Il lavoro %s e' fallito: %s", identificativo, errore, exc_info=True)
            motivo = "non e' riuscito"
        finally:
            self._compiti.pop(identificativo, None)
        aggiornato = deposito.passa_a(
            identificativo, stato, _adesso(), motivo, esito if stato == dominio.FATTO else ""
        )
        if aggiornato is None:
            return  # gia' terminale (per esempio annullato dalla persona): niente da consegnare due volte
        registro.registra(
            "lavoro.finito",
            esito=registro.ESITO_OK if stato == dominio.FATTO else registro.ESITO_ERRORE,
            attore=aggiornato["proprietario"],
            dettagli={"id": identificativo, "stato": stato, "durata_s": round(time.monotonic() - inizio, 1)},
        )
        await self._consegna(aggiornato)

    async def _consegna(self, lavoro: dict[str, Any]) -> None:
        if self._alla_fine is None:
            return
        try:
            await self._alla_fine(_come_si_vede(lavoro))
            deposito.segna_consegnato(lavoro["id"])
        except Exception:
            logger.exception("Consegna dell'esito del lavoro %s non riuscita", lavoro["id"])

    # ------------------------------------------------------------------ letture e annullo

    def elenco(self, proprietario: str) -> list[dict[str, Any]]:
        return [_come_si_vede(lv) for lv in deposito.del_profilo(proprietario)]

    def trova(self, proprietario: str, identificativo: str) -> dict[str, Any]:
        """Il lavoro, se e' di chi chiede. Quello di un altro profilo «non esiste»."""
        lavoro = deposito.trova(identificativo)
        if lavoro is None or lavoro["proprietario"] != proprietario:
            raise LavoroNonTrovato(identificativo)
        return _come_si_vede(lavoro)

    async def annulla(self, proprietario: str, identificativo: str) -> dict[str, Any]:
        """Annulla un lavoro in coda o in corso, solo se e' di chi chiede. Uno gia' finito non cambia."""
        self.trova(proprietario, identificativo)  # 404 se non e' suo
        compito = self._compiti.get(identificativo)
        if compito is not None:
            compito.cancel()
            # La fine del lavoro e' gia' registrata dentro `_esegui`: qui basta aspettare che si sia fermato.
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await compito
        else:
            deposito.passa_a(identificativo, dominio.ANNULLATO, _adesso(), "annullato")
        return self.trova(proprietario, identificativo)

    def dimentica_profilo(self, proprietario: str) -> int:
        """«Dimentica tutto di me»: ferma i lavori in corso e cancella tutti quelli del profilo."""
        for lavoro in deposito.del_profilo(proprietario, limite=1000):
            compito = self._compiti.get(lavoro["id"])
            if compito is not None:
                compito.cancel()
        return deposito.dimentica_profilo(proprietario)

    async def ferma(self) -> None:
        """Allo spegnimento: chiede ai lavori in corso di fermarsi, cosi' lo stato resta coerente."""
        self._fermando = True
        compiti = list(self._compiti.values())
        for compito in compiti:
            compito.cancel()
        if compiti:
            await asyncio.gather(*compiti, return_exceptions=True)


servizio_lavori = ServizioLavori()
