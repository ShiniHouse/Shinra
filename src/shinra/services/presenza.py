"""Il servizio che tiene il conto di chi c'e' in casa.

`domain/presenza.py` sa dire cosa e' cambiato fra due fotografie. Qui c'e'
tutto cio' che ha a che fare con il tempo — cioe' l'unica cosa difficile.

**Il ritardo sulle uscite.** Il GPS di un telefono perde il segnale in
garage, in ascensore, dietro un muro spesso; Home Assistant lo racconta come
«uscito» e lo ridice «rientrato» un minuto dopo. Senza attesa la casa
spegnerebbe tutto addosso a chi e' appena sceso in cantina, e lo
riaccenderebbe quando risale. Un'uscita si crede dopo un'attesa; un rientro
si crede subito, perche' chi torna vuole la luce accesa adesso e un falso
rientro non spegne niente a nessuno.

Riferimento: issue #22.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from shinra.domain import presenza as dominio
from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento, bus

logger = logging.getLogger("Shinra.Presenza")


class ServizioPresenza:
    def __init__(self) -> None:
        # Cio' a cui crediamo, che non e' sempre cio' che dice Home Assistant:
        # fra i due c'e' l'attesa.
        self._creduto: dict[str, str] = {}
        self._ultimo: Optional[dominio.StatoCasa] = None
        self._attese: dict[str, asyncio.Task] = {}
        self._annulla_ascolto: Optional[Any] = None

    # ------------------------------------------------------------ lettura

    @property
    def stato(self) -> dominio.StatoCasa:
        return dominio.leggi(self._creduto)

    def chi_c_e(self) -> list[str]:
        return sorted(self.stato.presenti)

    def dettaglio(self) -> dict[str, Any]:
        stato = self.stato
        return {
            "abitata": stato.abitata,
            "conosciuta": stato.conosciuta,
            "presenti": sorted(stato.presenti),
            "assenti": sorted(stato.assenti),
            "in_attesa": sorted(self._attese),
        }

    # ------------------------------------------------------------- avvio

    async def avvia(self) -> bool:
        from shinra.config.settings import settings

        if not settings.presenza.enabled:
            logger.info("Presenza disattivata.")
            return False

        await self.rileggi()
        self._annulla_ascolto = bus.sottoscrivi(HA_STATO_CAMBIATO, self._su_cambiamento)
        logger.info("Presenza in ascolto: %s", self.dettaglio())
        return True

    async def ferma(self) -> None:
        if self._annulla_ascolto is not None:
            self._annulla_ascolto()
            self._annulla_ascolto = None
        for attesa in list(self._attese.values()):
            attesa.cancel()
        self._attese.clear()

    async def rileggi(self) -> None:
        """La fotografia di partenza, dalla casa cosi' com'e' adesso.

        Non produce transizioni: `domain.transizioni` con `prima` nullo tace
        apposta, altrimenti ogni avvio annuncerebbe il rientro di tutti e
        farebbe partire le routine di benvenuto a ogni riavvio del servizio.
        """
        from shinra.infra.homeassistant.client import client_home_assistant

        stati = await client_home_assistant().stati_correnti()
        self._creduto = dominio.persone_dagli_stati(stati)
        self._ultimo = self.stato

    def azzera(self) -> None:
        """Solo per i test."""
        self._creduto.clear()
        self._ultimo = None
        for attesa in list(self._attese.values()):
            attesa.cancel()
        self._attese.clear()

    # ------------------------------------------------------------ ascolto

    def _su_cambiamento(self, evento: Evento) -> None:
        entita = str(evento.dati.get("entity_id", ""))
        if not entita.startswith(f"{dominio.DOMINIO}."):
            return

        valore = str(evento.dati.get("stato") or "")
        pulito = valore.strip().lower()

        # Un'attesa in corso decade appena arriva una notizia nuova su quella
        # persona, qualunque essa sia: se e' rientrata, l'uscita non e' mai
        # avvenuta.
        attesa = self._attese.pop(entita, None)
        if attesa is not None:
            attesa.cancel()

        if pulito in dominio.IGNOTO:
            # «Non lo so» non e' «fuori»: si resta su cio' che si credeva.
            logger.debug("Stato ignoto per %s: nessuna conclusione.", entita)
            return

        if pulito == dominio.IN_CASA:
            self._conferma(entita, pulito)
            return

        self._attese[entita] = asyncio.create_task(self._attendi_e_conferma(entita, pulito))

    async def _attendi_e_conferma(self, entita: str, valore: str) -> None:
        from shinra.config.settings import settings

        ritardo = max(0, int(settings.presenza.ritardo_uscita_secondi))
        try:
            await asyncio.sleep(ritardo)
        except asyncio.CancelledError:
            return
        self._attese.pop(entita, None)
        logger.info("Uscita confermata dopo %ds: %s", ritardo, entita)
        self._conferma(entita, valore)

    def _conferma(self, entita: str, valore: str) -> None:
        self._creduto[entita] = valore
        adesso = self.stato
        cambiamenti = dominio.transizioni(self._ultimo, adesso)
        self._ultimo = adesso

        for cambiamento in cambiamenti:
            dati: dict[str, Any] = {"persone_in_casa": sorted(adesso.presenti)}
            if cambiamento.persona:
                dati["entity_id"] = cambiamento.persona
                dati["persona"] = cambiamento.persona.split(".", 1)[-1]
            logger.info("Presenza: %s %s", cambiamento.tipo, cambiamento.persona or "")
            bus.pubblica_senza_attendere(Evento(tipo=cambiamento.tipo, dati=dati))


presenza = ServizioPresenza()
