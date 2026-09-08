"""Decidere se e quando ascoltare la casa.

Un modulo sottile, e non e' cerimonia: `api/` non parla mai direttamente a
`infra/`, ed e' la regola che ha appena impedito al collegamento della issue
#19 di entrare come una dipendenza all'indietro. Il test
`test_architettura.py` l'ha segnalata prima che finisse in un commit.

Ma il livello serve anche a qualcosa di piu' concreto: la **decisione** se
connettersi appartiene qui, non al trasporto. `infra/homeassistant/eventi.py`
sa aprire una connessione e riaprirla quando cade; sapere che non ha senso
aprirla quando Home Assistant e' disattivato o il token non e' configurato e'
una regola dell'applicazione.

Riferimento: issue #19.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("Shinra.EventiCasa")


def _token_utilizzabile(token: str) -> bool:
    """Un segnaposto non e' un token.

    Il valore di esempio nella configurazione supera qualunque controllo di
    presenza, e senza questa verifica il servizio proverebbe a riconnettersi
    per sempre a un Home Assistant che lo rifiuta a ogni tentativo.
    """
    pulito = (token or "").strip()
    return bool(pulito) and not pulito.startswith("INSERISCI_QUI") and len(pulito) >= 20


async def avvia() -> bool:
    """Comincia ad ascoltare, se ha senso farlo. Non blocca l'avvio."""
    from shinra.config.settings import settings
    from shinra.infra.homeassistant.client import client_home_assistant
    from shinra.infra.homeassistant.eventi import connessione_eventi

    if not settings.home_assistant.enabled:
        logger.info("Home Assistant disattivato: la casa non verra' ascoltata.")
        return False

    if not _token_utilizzabile(client_home_assistant().token):
        logger.warning(
            "Token di Home Assistant assente o segnaposto: niente eventi in tempo reale. "
            "Lo stato della casa continuera' ad arrivare su richiesta."
        )
        return False

    return await connessione_eventi.avvia()


async def ferma() -> None:
    from shinra.infra.homeassistant.eventi import connessione_eventi

    await connessione_eventi.ferma()


def in_ascolto() -> bool:
    """Se in questo momento gli stati arrivano da soli."""
    from shinra.infra.homeassistant.eventi import connessione_eventi

    return connessione_eventi.connessa
