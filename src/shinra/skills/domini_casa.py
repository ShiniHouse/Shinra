"""Serrature, media player, aspirapolvere e ventilatori.

Quattro domini che l'interfaccia elencava come comandabili e che nessun tool
sapeva toccare: si vedevano nella mappa dispositivi e non rispondevano a
niente. E' il tipo di difetto che erode la fiducia piu' di un errore
esplicito, perche' non ha un messaggio da leggere.

Stanno in un modulo solo, e non uno per dominio come suggerirebbe
ARCHITECTURE §4: condividono la stessa verifica, la stessa forma di
risposta e la stessa traduzione dei servizi di Home Assistant, e spezzarli
avrebbe prodotto quattro copie di quel codice piu' quattro file da tenere
allineati. Quando uno di questi domini crescera' davvero — il multiroom, per
dire — si stacchera' da solo.

**Le serrature non sono lampadine.** Il permesso `sicurezza.comanda` e' gia'
imposto dal client di Home Assistant (ADR 0004), quindi vale anche qui senza
che questo modulo debba ricordarsene. Ma sbloccare una porta merita due
protezioni in piu', ed entrambe sono qui sotto con il loro perche'.

Riferimento: issue #20, ADR 0004.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from shinra.domain.contesto import CANALE_ALEXA, canale_corrente, identita_e_ignota
from shinra.skills.entita import EntitaSconosciuta, nome_di, stati_noti, stato_di, verifica

logger = logging.getLogger("Shinra.DominiCasa")

# Quanto resta valida una richiesta di sblocco in attesa di conferma.
# Abbastanza perche' una persona risponda «si'», troppo poco perche' un «si'»
# detto piu' tardi, per altro, apra la porta di casa.
ATTESA_CONFERMA = 60.0

_sblocchi_in_attesa: Dict[str, float] = {}


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


async def _chiama(dominio: str, servizio: str, dati: Dict[str, Any]) -> Dict[str, Any]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().call_service(dominio, servizio, dati)


# --------------------------------------------------------------- serrature


async def comanda_serratura(entity_id: str, azione: str) -> Dict[str, Any]:
    """Blocca, sblocca o riferisce lo stato di una serratura.

    Tre protezioni, in ordine di solidita'.

    Il permesso `sicurezza.comanda` lo impone il client di Home Assistant su
    ogni chiamata: non e' aggirabile da qui, nemmeno scrivendo una routine.

    **Dalla voce non si sblocca.** L'ADR 0004 dichiara il limite che rende
    necessaria questa riga: il canale vocale non distingue chi parla.
    Chiunque si rivolga a un Echo agisce con l'identita' della sessione
    aperta, quindi un ospite — o qualcuno che parla da fuori una finestra —
    userebbe i permessi del padrone di casa. Finche' non arrivano i profili
    vocali (v0.4.0), da li' si puo' solo chiudere.

    **Lo sblocco chiede conferma**, e la conferma e' una seconda chiamata
    entro un minuto. Non un parametro `conferma=True` che il modello puo'
    riempire da solo: quello sarebbe teatro. Cosi' invece il modello deve
    davvero tornare dall'utente e ripresentarsi, e un singolo fraintendimento
    non apre una porta.
    """
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {"lock"}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)

    if azione in ("stato", "verifica"):
        valore = stato_di(entita, stati)
        leggibile = {"locked": "chiusa", "unlocked": "aperta", "jammed": "bloccata"}.get(valore, valore)
        return _riuscito(f"{nome} e' {leggibile}.", stato=valore)

    if azione in ("blocca", "chiudi", "lock"):
        _sblocchi_in_attesa.pop(entita, None)
        esito = await _chiama("lock", "lock", {"entity_id": entita})
        if esito.get("success"):
            return _riuscito(f"{nome} chiusa.")
        return _fallito(f"Non sono riuscito a chiudere {nome}.")

    if azione not in ("sblocca", "apri", "unlock"):
        return _fallito(f"Azione «{azione}» non prevista per una serratura.")

    canale = canale_corrente()
    if canale == CANALE_ALEXA and identita_e_ignota():
        # Il divieto era assoluto perche' il canale non sapeva mai chi
        # parlasse: negare a tutti era l'unica risposta onesta. Con i profili
        # vocali (issue #48) la domanda diventa rispondibile, e il divieto si
        # stringe attorno al caso che lo giustificava — non so chi sei.
        #
        # Chi so chi e' passa di qui e incontra due controlli veri: il
        # permesso `sicurezza.comanda`, imposto da `call_service` sul dominio
        # `lock`, e la conferma esplicita qui sotto.
        return _fallito(
            f"Da voce non apro {nome}: non so chi sta parlando. Se configuri i "
            "profili vocali di Alexa e associ la tua voce a un profilo dalle "
            "impostazioni, potro' farlo. Intanto puoi aprirla dalla dashboard."
        )

    adesso = time.monotonic()
    scade = _sblocchi_in_attesa.get(entita, 0.0)
    if scade < adesso:
        _sblocchi_in_attesa[entita] = adesso + ATTESA_CONFERMA
        return _fallito(
            f"Sto per aprire {nome}. Confermi? Ripeti la richiesta entro un minuto.",
            conferma_richiesta=True,
        )

    _sblocchi_in_attesa.pop(entita, None)
    esito = await _chiama("lock", "unlock", {"entity_id": entita})
    if esito.get("success"):
        logger.warning("Serratura aperta: %s (canale %s)", entita, canale or "non indicato")
        return _riuscito(f"{nome} aperta.")
    return _fallito(f"Non sono riuscito ad aprire {nome}.")


# ------------------------------------------------------------ media player

_SERVIZI_MEDIA = {
    "riproduci": "media_play",
    "play": "media_play",
    "pausa": "media_pause",
    "pause": "media_pause",
    "ferma": "media_stop",
    "stop": "media_stop",
    "successiva": "media_next_track",
    "precedente": "media_previous_track",
    "spegni": "turn_off",
    "accendi": "turn_on",
}


async def comanda_media(
    entity_id: str,
    azione: str,
    volume: Optional[int] = None,
    sorgente: Optional[str] = None,
) -> Dict[str, Any]:
    """Riproduzione, pausa, traccia, volume e sorgente di un media player."""
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {"media_player"}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)

    if azione in ("volume", "imposta_volume"):
        if volume is None:
            return _fallito("Serve un volume da 0 a 100.")
        # Home Assistant vuole 0.0-1.0. Il modello parla in percentuale
        # perche' e' cosi' che ne parlano le persone.
        livello = max(0, min(100, int(volume))) / 100
        esito = await _chiama("media_player", "volume_set", {"entity_id": entita, "volume_level": livello})
        return (
            _riuscito(f"Volume di {nome} al {int(livello * 100)} per cento.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito a cambiare il volume di {nome}.")
        )

    if azione in ("sorgente", "cambia_sorgente"):
        if not sorgente:
            return _fallito("Serve il nome della sorgente.")
        esito = await _chiama("media_player", "select_source", {"entity_id": entita, "source": sorgente})
        return (
            _riuscito(f"{nome} passa a {sorgente}.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito a cambiare sorgente su {nome}.")
        )

    servizio = _SERVIZI_MEDIA.get(azione)
    if not servizio:
        return _fallito(f"Azione «{azione}» non prevista per un media player.")

    esito = await _chiama("media_player", servizio, {"entity_id": entita})
    return (
        _riuscito(f"Fatto su {nome}: {azione}.")
        if esito.get("success")
        else _fallito(f"Non sono riuscito a eseguire «{azione}» su {nome}.")
    )


# ---------------------------------------------------------- aspirapolvere

_SERVIZI_ASPIRAPOLVERE = {
    "avvia": "start",
    "pulisci": "start",
    "start": "start",
    "ferma": "pause",
    "pausa": "pause",
    "rientra": "return_to_base",
    "base": "return_to_base",
    "torna": "return_to_base",
    "spegni": "stop",
    "stop": "stop",
}


async def comanda_aspirapolvere(entity_id: str, azione: str, stanza: Optional[str] = None) -> Dict[str, Any]:
    """Avvia, ferma, rimanda alla base o manda a pulire una stanza."""
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {"vacuum"}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)

    if stanza:
        # `send_command` con `app_segment_clean` e' la strada che funziona sui
        # Roborock; altri modelli espongono altro. Se il comando non passa lo
        # si dice, invece di far credere che il robot sia partito.
        esito = await _chiama(
            "vacuum",
            "send_command",
            {"entity_id": entita, "command": "app_segment_clean", "params": [stanza]},
        )
        return (
            _riuscito(f"{nome} sta pulendo {stanza}.")
            if esito.get("success")
            else _fallito(f"{nome} non accetta la pulizia per stanze da qui.")
        )

    servizio = _SERVIZI_ASPIRAPOLVERE.get(azione)
    if not servizio:
        return _fallito(f"Azione «{azione}» non prevista per un aspirapolvere.")

    esito = await _chiama("vacuum", servizio, {"entity_id": entita})
    return (
        _riuscito(f"Fatto su {nome}: {azione}.")
        if esito.get("success")
        else _fallito(f"Non sono riuscito a eseguire «{azione}» su {nome}.")
    )


# ------------------------------------------------------------ ventilatori


async def comanda_ventilatore(
    entity_id: str,
    azione: str,
    velocita: Optional[int] = None,
    oscillazione: Optional[bool] = None,
) -> Dict[str, Any]:
    """Accende, spegne, cambia velocita' e oscillazione di un ventilatore."""
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {"fan"}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)

    if azione in ("velocita", "imposta_velocita"):
        if velocita is None:
            return _fallito("Serve una velocita' da 0 a 100.")
        percentuale = max(0, min(100, int(velocita)))
        esito = await _chiama("fan", "set_percentage", {"entity_id": entita, "percentage": percentuale})
        return (
            _riuscito(f"{nome} al {percentuale} per cento.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito a cambiare velocita' a {nome}.")
        )

    if azione in ("oscilla", "oscillazione"):
        acceso = True if oscillazione is None else bool(oscillazione)
        esito = await _chiama("fan", "oscillate", {"entity_id": entita, "oscillating": acceso})
        return (
            _riuscito(f"Oscillazione di {nome} {'attivata' if acceso else 'disattivata'}.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito a cambiare l'oscillazione di {nome}.")
        )

    if azione in ("accendi", "on", "turn_on"):
        dati: Dict[str, Any] = {"entity_id": entita}
        if velocita is not None:
            dati["percentage"] = max(0, min(100, int(velocita)))
        esito = await _chiama("fan", "turn_on", dati)
        return (
            _riuscito(f"{nome} acceso.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito ad accendere {nome}.")
        )

    if azione in ("spegni", "off", "turn_off"):
        esito = await _chiama("fan", "turn_off", {"entity_id": entita})
        return (
            _riuscito(f"{nome} spento.")
            if esito.get("success")
            else _fallito(f"Non sono riuscito a spegnere {nome}.")
        )

    return _fallito(f"Azione «{azione}» non prevista per un ventilatore.")


def azzera_conferme() -> None:
    """Solo per i test."""
    _sblocchi_in_attesa.clear()
