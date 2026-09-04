"""Consegna degli eventi ai canali: come l'utente viene avvisato.

Lo scheduler pubblica «questo timer e' scaduto» e non sa nulla di come venga
consegnato. Qui vivono i canali, ognuno indipendente: se l'Echo e'
irraggiungibile la dashboard suona lo stesso, e viceversa.

Il canale su Echo collega finalmente `speak_on_alexa()`, che era definita in
`ha_client.py` e non veniva chiamata da nessuno — l'assistente non poteva
parlare spontaneamente in casa, poteva solo rispondere.

Le notifiche push (issue #29, v0.4.0) si aggiungeranno qui come un canale in
piu', senza toccare lo scheduler.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings
from core.eventi import PROMEMORIA_SCADUTO, TIMER_SCADUTO, Evento, bus

logger = logging.getLogger("Shinra.Consegna")


def _frase(evento: Evento) -> str:
    """Cosa viene detto ad alta voce."""
    nome = settings.assistant.name or "Shinra"
    if evento.tipo == TIMER_SCADUTO:
        etichetta = (evento.dati.get("etichetta") or "").strip()
        if etichetta and etichetta.lower() != "timer":
            return f"Il timer per {etichetta} e' scaduto."
        return "Il timer e' scaduto."
    if evento.tipo == PROMEMORIA_SCADUTO:
        testo = (evento.dati.get("testo") or "").strip()
        return f"Promemoria: {testo}." if testo else f"Hai un promemoria da {nome}."
    return ""


async def annuncia_su_echo(evento: Evento) -> None:
    """Pronuncia l'avviso su un dispositivo Echo, se ne e' configurato uno."""
    entita = (settings.home_assistant.alexa_media_player_entity or "").strip()
    if not entita:
        return  # nessun Echo configurato: non e' un errore

    frase = _frase(evento)
    if not frase:
        return

    from core.ha_client import client_home_assistant

    esito = await client_home_assistant().speak_on_alexa(frase, entita)
    if esito.get("success"):
        logger.info("Annunciato su %s: %s", entita, frase)
    else:
        logger.warning("Annuncio su %s non riuscito: %s", entita, esito.get("error"))


def registra_canali() -> None:
    """Collega i canali al bus. Chiamata una volta all'avvio."""
    for tipo in (TIMER_SCADUTO, PROMEMORIA_SCADUTO):
        bus.sottoscrivi(tipo, annuncia_su_echo)
    logger.info("Canali di consegna registrati.")


def descrivi(evento: Evento) -> dict[str, Any]:
    """L'evento nella forma che i client si aspettano."""
    return {**evento.come_json(), "frase": _frase(evento)}
