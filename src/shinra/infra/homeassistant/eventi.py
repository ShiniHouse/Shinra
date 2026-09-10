"""La casa che dice cosa succede, invece di rispondere quando le si chiede.

Fino alla v0.2.0 ogni informazione da Home Assistant arrivava da
`GET /api/states`: una fotografia su domanda. Il sistema non sapeva mai
**quando** qualcosa accadeva, e senza quel «quando» una regola come «se la
porta si apre dopo le 23, accendi l'ingresso» non e' scrivibile. E' il
vincolo che blocca l'intera fase v0.4.0.

Il file e' diviso in due meta', e la divisione e' voluta.

`Protocollo` sa cosa rispondere a ogni messaggio e cosa farne. Non conosce
il socket: riceve dizionari gia' decodificati e restituisce dizionari da
inviare. Si prova per intero senza rete, senza un finto server, senza
attese — ed e' il pezzo che regge la v0.4.0, quindi doveva essere provabile
davvero.

`ConnessioneEventi` e' l'anello attorno: apre, riconnette, decodifica, e
passa i messaggi al protocollo. Poco codice, e quel poco non decide niente.

Riferimento: issue #19.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from shinra.domain.eventi import HA_STATI_PRONTI, HA_STATO_CAMBIATO, Evento, bus
from shinra.infra.homeassistant.stati import DOMINI_OSSERVATI, CacheStati, cache_stati, dominio_di

logger = logging.getLogger("Shinra.HomeAssistant.Eventi")

# L'attesa fra un tentativo di riconnessione e il successivo: raddoppia fino
# al tetto. Home Assistant che si riavvia torna in pochi secondi; Home
# Assistant spento resta spento per ore, e insistere ogni secondo per ore
# riempie il log e scalda il processore senza avvicinare la soluzione.
ATTESA_INIZIALE = 2.0
ATTESA_MASSIMA = 60.0


class ErroreAutenticazione(Exception):
    """Il token non e' valido. Riprovare non serve: serve un token nuovo."""


class Protocollo:
    """La conversazione con Home Assistant, senza il socket sotto.

    Il dialogo e' fisso: il server saluta con `auth_required`, si manda il
    token, si riceve `auth_ok`, ci si sottoscrive agli eventi e da li' in poi
    arrivano. Ogni passo e' un messaggio che entra e zero o piu' messaggi che
    escono.
    """

    ID_SOTTOSCRIZIONE = 1

    def __init__(
        self,
        token: str,
        cache: Optional[CacheStati] = None,
        su_cambiamento: Optional[Callable[[str, dict[str, Any]], None]] = None,
        domini: frozenset[str] = DOMINI_OSSERVATI,
    ) -> None:
        self._token = token
        self.cache = cache if cache is not None else cache_stati
        self._su_cambiamento = su_cambiamento
        self._domini = domini
        self.autenticato = False
        self.sottoscritto = False

    def ricevi(self, messaggio: dict[str, Any]) -> list[dict[str, Any]]:
        """Cosa rispondere a questo messaggio. Gli effetti li applica qui."""
        tipo = messaggio.get("type")

        if tipo == "auth_required":
            return [{"type": "auth", "access_token": self._token}]

        if tipo == "auth_ok":
            self.autenticato = True
            logger.info("Autenticato su Home Assistant (versione %s).", messaggio.get("ha_version", "?"))
            return [
                {
                    "id": self.ID_SOTTOSCRIZIONE,
                    "type": "subscribe_events",
                    "event_type": "state_changed",
                }
            ]

        if tipo == "auth_invalid":
            raise ErroreAutenticazione(messaggio.get("message") or "Token rifiutato da Home Assistant.")

        if tipo == "result":
            if messaggio.get("id") == self.ID_SOTTOSCRIZIONE:
                self.sottoscritto = bool(messaggio.get("success"))
                if not self.sottoscritto:
                    logger.error("Sottoscrizione agli eventi rifiutata: %s", messaggio.get("error"))
                else:
                    logger.info("Sottoscritto agli eventi di stato.")
            return []

        if tipo == "event":
            self._stato_cambiato(messaggio.get("event") or {})
            return []

        if tipo == "pong":
            return []

        logger.debug("Messaggio non gestito da Home Assistant: %s", tipo)
        return []

    # ------------------------------------------------------------ interno

    def _stato_cambiato(self, evento: dict[str, Any]) -> None:
        if evento.get("event_type") != "state_changed":
            return
        dati = evento.get("data") or {}
        entity_id = dati.get("entity_id") or ""
        nuovo = dati.get("new_state")

        if not entity_id:
            return

        # Un'entita' rimossa arriva con `new_state` nullo.
        if nuovo is None:
            if self.cache.dimentica(entity_id):
                logger.debug("Entita' rimossa: %s", entity_id)
            return

        self.cache.aggiorna(nuovo)

        # Il filtro sta qui e non nella cache: la cache serve anche a
        # rispondere «com'e' messo quel sensore», mentre sul bus finisce solo
        # cio' che qualcuno vuole davvero ascoltare. `state_changed` scatta
        # per ogni entita' della casa, comprese le batterie dei telecomandi.
        if dominio_di(entity_id) not in self._domini:
            return

        vecchio = dati.get("old_state") or {}
        if vecchio.get("state") == nuovo.get("state"):
            # Cambia un attributo, non lo stato: la luce era gia' accesa e ha
            # solo variato luminosita'. Sul bus non e' una notizia.
            return

        if self._su_cambiamento is not None:
            self._su_cambiamento(entity_id, nuovo)

        bus.pubblica_senza_attendere(
            Evento(
                tipo=HA_STATO_CAMBIATO,
                dati={
                    "entity_id": entity_id,
                    "stato": nuovo.get("state"),
                    "stato_precedente": vecchio.get("state"),
                    "nome": (nuovo.get("attributes") or {}).get("friendly_name") or entity_id,
                    "dominio": dominio_di(entity_id),
                },
            )
        )


def indirizzo_websocket(base_url: str) -> str:
    """`http://casa:8123` diventa `ws://casa:8123/api/websocket`."""
    indirizzo = (base_url or "").rstrip("/")
    if indirizzo.startswith("https://"):
        return "wss://" + indirizzo[len("https://") :] + "/api/websocket"
    if indirizzo.startswith("http://"):
        return "ws://" + indirizzo[len("http://") :] + "/api/websocket"
    return indirizzo + "/api/websocket"


def attesa_successiva(attesa: float) -> float:
    return min(attesa * 2, ATTESA_MASSIMA)


class ConnessioneEventi:
    """L'anello che tiene aperta la connessione, e la riapre quando cade."""

    def __init__(self, cache: Optional[CacheStati] = None) -> None:
        self.cache = cache if cache is not None else cache_stati
        self._compito: Optional[asyncio.Task] = None
        self._acceso = False
        self.connessa = False

    @property
    def attiva(self) -> bool:
        return self._acceso

    async def prendi_istantanea(self, cliente: Any) -> int:
        """La fotografia iniziale della casa, e l'annuncio che c'e'.

        L'annuncio serve a chi **programma** qualcosa in base a cio' che la
        casa sa. All'avvio la cache e' vuota, quindi una regola all'alba non
        ha modo di sapere a che ora sorge il sole e non viene messa nello
        scheduler: senza questo evento resterebbe non programmata fino al
        primo tramonto utile, cioe' fino a dodici ore dopo.

        Sta in un metodo suo e non dentro l'anello di ascolto per poterla
        provare: la riga che pubblica l'evento era l'unica cosa non coperta di
        tutta la correzione.
        """
        quanti = self.cache.sostituisci(await cliente.get_states())
        logger.info("Stati iniziali in memoria: %d entita'.", quanti)
        bus.pubblica_senza_attendere(Evento(tipo=HA_STATI_PRONTI, dati={"quanti": quanti}))
        return quanti

    async def avvia(self) -> bool:
        """Parte in sottofondo. Non blocca l'avvio del servizio.

        Se Home Assistant non c'e', l'applicazione deve partire lo stesso e
        continuare a funzionare in modo ridotto: e' una casa, non un
        datacenter, e il servizio che si rifiuta di partire perche' manca un
        pezzo e' il modo piu' sicuro di lasciare tutti al buio.

        *Se* valga la pena aprirla lo decide `services.eventi_casa`: qui c'e'
        solo il come.
        """
        self._acceso = True
        self._compito = asyncio.create_task(self._anello())
        return True

    async def ferma(self) -> None:
        self._acceso = False
        self.connessa = False
        if self._compito is not None:
            self._compito.cancel()
            try:
                await self._compito
            except asyncio.CancelledError:
                pass  # e' cio' che abbiamo appena chiesto
            except Exception as e:
                logger.debug("Chiusura della connessione agli eventi: %s", e)
            self._compito = None
        self.cache.svuota()

    async def _anello(self) -> None:
        attesa = ATTESA_INIZIALE
        while self._acceso:
            try:
                await self._una_connessione()
                attesa = ATTESA_INIZIALE  # e' andata: si riparte dal minimo
            except asyncio.CancelledError:
                raise
            except ErroreAutenticazione as e:
                logger.error("Home Assistant rifiuta il token: %s. Non riprovo.", e)
                self._acceso = False
                return
            except Exception as e:
                logger.warning("Connessione agli eventi caduta (%s). Riprovo fra %.0fs.", e, attesa)
            finally:
                self.connessa = False
                self.cache.svuota()

            if not self._acceso:
                return
            await asyncio.sleep(attesa)
            attesa = attesa_successiva(attesa)

    async def _una_connessione(self) -> None:
        import websockets

        from shinra.infra.homeassistant.client import client_home_assistant

        cliente = client_home_assistant()
        protocollo = Protocollo(cliente.token, cache=self.cache)

        async with websockets.connect(indirizzo_websocket(cliente.base_url), max_size=4 * 1024 * 1024) as ws:
            async for grezzo in ws:
                try:
                    messaggio = json.loads(grezzo)
                except (ValueError, TypeError):
                    logger.warning("Messaggio illeggibile da Home Assistant, ignorato.")
                    continue

                for risposta in protocollo.ricevi(messaggio):
                    await ws.send(json.dumps(risposta))

                # L'istantanea si prende una volta sola, appena sottoscritti:
                # da li' in poi arrivano solo le differenze, e senza la base
                # la cache conoscerebbe soltanto cio' che e' cambiato dopo.
                if protocollo.sottoscritto and not self.connessa:
                    self.connessa = True
                    await self.prendi_istantanea(cliente)


connessione_eventi = ConnessioneEventi()
