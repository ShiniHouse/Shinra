"""Il servizio che avvisa: un evento entra, le persone giuste lo sentono.

Prima di questo file la casa aveva un canale solo — l'annuncio sull'Echo — e
un evento che non lo trovava restava muto. `casa.intrusione` era il caso
peggiore: `services/allarme.py` lo pubblicava sul bus e **non lo ascoltava
nessuno**, nemmeno il WebSocket della dashboard. Un allarme che scatta mentre
nessuno guarda non ha avvisato nessuno, e le note della `v0.3.0` dicevano che
almeno alla dashboard arrivava: non era vero.

Qui gli eventi diventano avvisi, gli avvisi trovano i loro canali, e ogni
canale e' indipendente: se il telefono e' irraggiungibile la dashboard suona
lo stesso, e viceversa.

Riferimento: issue #29.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from shinra.domain import notifiche as dominio
from shinra.domain.eventi import (
    AVVISO,
    CASA_INTRUSIONE,
    PROMEMORIA_SCADUTO,
    TIMER_SCADUTO,
    Evento,
    bus,
)

logger = logging.getLogger("Shinra.Notifiche")


def _avviso_da(evento: Evento) -> Optional[dominio.Avviso]:
    """Da un evento del bus a qualcosa che si puo' dire a una persona.

    `None` per gli eventi che non meritano una notifica. Non tutto cio' che
    succede in casa va annunciato: una casa che notifica ogni cambio di stato
    di ogni lampadina viene silenziata il primo giorno, e poi non avvisa piu'
    nemmeno di cio' che conta.
    """
    dati = evento.dati or {}

    if evento.tipo == CASA_INTRUSIONE:
        chi = dati.get("persone_in_casa") or []
        dettaglio = f" In casa risultano {', '.join(chi)}." if chi else " In casa non risulta nessuno."
        return dominio.Avviso(
            categoria=dominio.SICUREZZA,
            titolo="Allarme: intrusione",
            testo=f"L'allarme e' scattato.{dettaglio}",
            priorita=dominio.URGENTE,
            destinazione="/#sicurezza",
            dati=dict(dati),
        )

    if evento.tipo == PROMEMORIA_SCADUTO:
        testo = str(dati.get("testo") or "").strip()
        return dominio.Avviso(
            categoria=dominio.PROMEMORIA,
            titolo="Promemoria",
            testo=testo or "Hai un promemoria.",
            priorita=dominio.IMPORTANTE,
            destinazione="/#promemoria",
            dati=dict(dati),
        )

    if evento.tipo == TIMER_SCADUTO:
        etichetta = str(dati.get("etichetta") or "").strip()
        return dominio.Avviso(
            categoria=dominio.TIMER,
            titolo="Timer scaduto",
            testo=f"Il timer per {etichetta} e' scaduto." if etichetta else "Il timer e' scaduto.",
            priorita=dominio.IMPORTANTE,
            destinazione="/#timer",
            dati=dict(dati),
        )

    return None


class ServizioNotifiche:
    def __init__(self) -> None:
        self._annulla: list[Any] = []

    # ------------------------------------------------------------ ciclo

    def avvia(self) -> bool:
        if self._annulla:
            return False
        for tipo in (CASA_INTRUSIONE, PROMEMORIA_SCADUTO, TIMER_SCADUTO):
            self._annulla.append(bus.sottoscrivi(tipo, self._su_evento))
        logger.info("Servizio notifiche in ascolto.")
        return True

    def ferma(self) -> None:
        for annulla in self._annulla:
            annulla()
        self._annulla = []

    async def _su_evento(self, evento: Evento) -> None:
        avviso = _avviso_da(evento)
        if avviso is not None:
            await self.avvisa(avviso)

    # ------------------------------------------------------------ invio

    async def avvisa(self, avviso: dominio.Avviso, utente: Optional[str] = None) -> dict[str, Any]:
        """Manda un avviso a chi di dovere, su tutti i canali che vuole.

        Torna cosa e' stato fatto, canale per canale: serve a chi guarda i
        log per capire perche' non ha ricevuto qualcosa, che e' la domanda
        piu' frequente su un sistema di notifiche.
        """
        destinatari = [utente] if utente else self._tutti_gli_utenti()
        esito: dict[str, Any] = {"inviate": 0, "per_canale": {}, "saltati": []}

        for persona in destinatari:
            preferenze = self.preferenze_di(persona)
            canali = dominio.canali_per(avviso, preferenze)

            if not canali:
                esito["saltati"].append(persona)
                continue

            for canale in canali:
                fatte = await self._su_canale(canale, avviso, persona)
                esito["per_canale"][canale] = esito["per_canale"].get(canale, 0) + fatte
                esito["inviate"] += fatte

        logger.info("Avviso «%s» (%s): %s", avviso.titolo, avviso.priorita, esito["per_canale"] or "nessuno")
        return esito

    async def _su_canale(self, canale: str, avviso: dominio.Avviso, utente: str) -> int:
        if canale == dominio.PUSH:
            return await self._push(avviso, utente)
        if canale == dominio.VOCE:
            return await self._voce(avviso)
        if canale == dominio.WEB:
            return self._web(avviso, utente)
        return 0

    def _web(self, avviso: dominio.Avviso, utente: str) -> int:
        """La dashboard aperta. Passa dal bus, come tutto il resto."""
        bus.pubblica_senza_attendere(
            Evento(
                tipo=AVVISO,
                dati={
                    "categoria": avviso.categoria,
                    "titolo": avviso.titolo,
                    "testo": avviso.testo,
                    "priorita": avviso.priorita,
                    "destinazione": avviso.destinazione,
                    "utente": utente,
                },
            )
        )
        return 1

    async def _push(self, avviso: dominio.Avviso, utente: str) -> int:
        from shinra.infra.db import depositi
        from shinra.infra.push import mittente

        sottoscrizioni = depositi.sottoscrizioni_push.per_utente(utente)
        if not sottoscrizioni:
            return 0

        carico = {
            "titolo": avviso.titolo,
            "testo": avviso.testo,
            "categoria": avviso.categoria,
            "priorita": avviso.priorita,
            "destinazione": avviso.destinazione,
        }

        riuscite = 0
        for sottoscrizione in sottoscrizioni:
            esito = mittente.invia(sottoscrizione, carico)
            if esito.riuscito:
                riuscite += 1
                depositi.sottoscrizioni_push.aggiorna(
                    str(sottoscrizione["id"]), {"ultimo_invio": datetime.now(), "fallimenti": 0}
                )
                continue
            self._ha_fallito(sottoscrizione, esito)

        return riuscite

    def _ha_fallito(self, sottoscrizione: dict[str, Any], esito: Any) -> None:
        """Un telefono che non risponde va tolto, ma solo quando e' sicuro.

        Un 404 o un 410 sono il servizio push che dice «questo indirizzo non
        esiste piu'»: definitivo. Un timeout e' un'altra cosa, e togliere una
        sottoscrizione per un problema di rete vorrebbe dire smettere di
        avvisare qualcuno senza dirglielo.
        """
        from shinra.infra.db import depositi
        from shinra.infra.push.mittente import FALLIMENTI_MASSIMI

        identificativo = str(sottoscrizione["id"])
        conteggio = int(sottoscrizione.get("fallimenti") or 0) + 1

        if esito.definitivo or conteggio >= FALLIMENTI_MASSIMI:
            depositi.sottoscrizioni_push.cancella(identificativo)
            logger.info(
                "Sottoscrizione %s rimossa (%s).",
                identificativo,
                "revocata dal browser" if esito.definitivo else f"{conteggio} fallimenti",
            )
            return

        depositi.sottoscrizioni_push.aggiorna(identificativo, {"fallimenti": conteggio})
        logger.warning("Invio push non riuscito (%s): %s", conteggio, esito.errore)

    async def _voce(self, avviso: dominio.Avviso) -> int:
        from shinra.config.settings import settings
        from shinra.infra.homeassistant.client import client_home_assistant

        entita = (settings.home_assistant.alexa_media_player_entity or "").strip()
        if not entita:
            return 0

        frase = f"{avviso.titolo}. {avviso.testo}".strip()
        esito = await client_home_assistant().speak_on_alexa(frase, entita)
        return 1 if esito.get("success") else 0

    # ------------------------------------------------------- preferenze

    def preferenze_di(self, utente: str) -> dominio.Preferenze:
        from shinra.infra.db import depositi

        return dominio.preferenze_da_righe(utente, depositi.preferenze_notifiche.per_utente(utente))

    def imposta(self, utente: str, chiave: str, valore: bool) -> dict[str, Any]:
        from shinra.infra.db import depositi

        return depositi.preferenze_notifiche.imposta(utente, chiave, valore)

    def _tutti_gli_utenti(self) -> list[str]:
        """Chi ha almeno un telefono registrato, piu' chi ha preferenze.

        Non tutti gli utenti dell'anagrafica: mandare una notifica a chi non
        ne ha mai chiesta una vuol dire non mandarla a nessuno e scrivere
        nei log che e' partita.
        """
        from shinra.infra.db import depositi

        persone = {str(r["user_id"]) for r in depositi.sottoscrizioni_push.elenco()}
        persone |= {str(r["user_id"]) for r in depositi.preferenze_notifiche.elenco()}
        return sorted(persone) or ["alessio"]

    # ----------------------------------------------------- sottoscrizioni

    def registra_dispositivo(
        self, utente: str, endpoint: str, p256dh: str, auth: str, nome: str = "Dispositivo"
    ) -> dict[str, Any]:
        """Registra un telefono, o aggiorna quello che c'era.

        L'endpoint identifica la sottoscrizione: lo stesso endpoint che
        torna e' lo stesso telefono che si e' ri-registrato, non un secondo
        telefono. Senza questo, ogni ricaricamento della pagina lascerebbe
        una riga in piu' e ogni notifica arriverebbe moltiplicata.
        """
        from shinra.infra.db import depositi

        esistente = depositi.sottoscrizioni_push.per_endpoint(endpoint)
        if esistente:
            return (
                depositi.sottoscrizioni_push.aggiorna(
                    str(esistente["id"]),
                    {"user_id": utente, "p256dh": p256dh, "auth": auth, "nome": nome, "fallimenti": 0},
                )
                or esistente
            )

        return depositi.sottoscrizioni_push.aggiungi(
            {
                "id": f"push_{uuid.uuid4().hex[:8]}",
                "user_id": utente,
                "endpoint": endpoint,
                "p256dh": p256dh,
                "auth": auth,
                "nome": nome,
                "fallimenti": 0,
            }
        )

    def dimentica_dispositivo(self, endpoint: str, utente: Optional[str] = None) -> bool:
        """Toglie un telefono. Con `utente`, solo se e' suo.

        Senza quel controllo, chiunque avesse una sessione potrebbe togliere
        il telefono di un altro conoscendone l'endpoint — e l'altro
        smetterebbe di ricevere gli allarmi senza accorgersene. L'ha trovato
        il test che pretende un permesso su ogni rotta che cambia qualcosa:
        qui il permesso non serve, ma il controllo di proprieta' si'.
        """
        from shinra.infra.db import depositi

        if utente is not None:
            riga = depositi.sottoscrizioni_push.per_endpoint(endpoint)
            if riga is None or str(riga.get("user_id")) != utente:
                return False

        return depositi.sottoscrizioni_push.cancella_per_endpoint(endpoint)

    def dispositivi_di(self, utente: str) -> list[dict[str, Any]]:
        """I telefoni registrati, **senza le chiavi**.

        Le chiavi servono a cifrare, non a farsi guardare: mostrarle in
        un'interfaccia vorrebbe dire farle finire nella cronologia del
        browser, negli screenshot, e nei log di chiunque intercetti una
        risposta.
        """
        from shinra.infra.db import depositi

        return [
            {
                "id": v.get("id"),
                "nome": v.get("nome"),
                "creata_il": v.get("creata_il"),
                "ultimo_invio": v.get("ultimo_invio"),
                "fallimenti": v.get("fallimenti"),
            }
            for v in depositi.sottoscrizioni_push.per_utente(utente)
        ]

    def chiave_pubblica(self) -> Optional[str]:
        """La chiave con cui un browser si registra, o `None` se le notifiche
        non sono disponibili."""
        from shinra.infra.push import mittente

        chiavi = mittente.chiavi()
        return chiavi.pubblica if chiavi else None


servizio_notifiche = ServizioNotifiche()
