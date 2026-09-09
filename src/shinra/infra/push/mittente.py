"""Mandare una notifica a un telefono che non ha l'applicazione aperta.

Il giro e' questo: il browser si registra presso il **suo** servizio push
(Google per Chrome, Mozilla per Firefox, Apple per Safari) e ci consegna un
indirizzo e due chiavi. Da qui si cifra il messaggio con quelle chiavi e lo si
consegna a quell'indirizzo: il servizio push instrada una busta che non puo'
aprire.

E' il motivo per cui un promemoria di casa puo' passare da Google senza che
Google sappia cosa dice — e vale la pena che sia scritto, perche' «notifiche
push» suona come «mandiamo i nostri dati a Google» e non lo e'.

**La cifratura non e' scritta qui.** Si usa `pywebpush`, che implementa
l'RFC 8291. Non e' pigrizia: la cifratura di una busta push e' esattamente il
genere di codice in cui un errore sottile non si vede — la notifica non
arriva, oppure arriva leggibile a chi non deve — e riscriverla per non
aggiungere una dipendenza sarebbe un pessimo scambio.

Le chiavi VAPID identificano **questo** server presso il servizio push, e sono
sue: si generano una volta e restano. Cambiarle invalida tutte le
sottoscrizioni, perche' i browser hanno salvato la chiave pubblica di prima.

Riferimento: issue #29.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

logger = logging.getLogger("Shinra.Push")

# Gli stati con cui un servizio push dice «questo indirizzo non esiste piu'».
# Sono definitivi: la sottoscrizione va tolta, non ritentata. Tutto il resto
# — timeout, 500, rete assente — e' passeggero, e togliere un telefono per un
# problema di rete vorrebbe dire smettere di avvisare qualcuno senza dirglielo.
DEFINITIVI = frozenset({404, 410})

# Dopo quanti fallimenti di fila si molla anche senza uno stato definitivo.
# Un endpoint che non risponde da giorni non e' un problema di rete.
FALLIMENTI_MASSIMI = 10


@dataclass(frozen=True)
class ChiaviVapid:
    """L'identita' di questo server presso i servizi push."""

    privata: str
    pubblica: str
    contatto: str = "mailto:shinra@localhost"

    @property
    def valide(self) -> bool:
        return bool(self.privata and self.pubblica)


@dataclass(frozen=True)
class Esito:
    """Com'e' andata. `definitivo` significa: togli la sottoscrizione."""

    riuscito: bool
    stato: Optional[int] = None
    errore: str = ""

    @property
    def definitivo(self) -> bool:
        return self.stato in DEFINITIVI


def percorso_chiavi() -> Path:
    from shinra.percorsi import CONFIGURAZIONE

    return CONFIGURAZIONE / "vapid.json"


def genera_chiavi() -> ChiaviVapid:
    """Genera una coppia VAPID nuova.

    Chiamata una volta sola, al primo avvio con le notifiche attive. Non si
    rigenera mai da sola: cambiare le chiavi invalida in silenzio tutte le
    sottoscrizioni esistenti, e una casa che smette di avvisare senza dirlo
    e' peggio di una casa che non ha mai avvisato.
    """
    from py_vapid import Vapid01

    vapid = Vapid01()
    vapid.generate_keys()

    return ChiaviVapid(
        privata=_in_base64(vapid.private_key.private_numbers().private_value.to_bytes(32, "big")),
        pubblica=_pubblica_da(vapid),
    )


def _in_base64(grezzo: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(grezzo).decode("ascii").rstrip("=")


def _pubblica_da(vapid: Any) -> str:
    from cryptography.hazmat.primitives import serialization

    grezza = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _in_base64(grezza)


def carica_chiavi() -> Optional[ChiaviVapid]:
    """Le chiavi salvate, se ci sono."""
    percorso = percorso_chiavi()
    if not percorso.exists():
        return None
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.warning("Chiavi VAPID illeggibili (%s): le notifiche push restano spente.", e)
        return None

    chiavi = ChiaviVapid(
        privata=str(dati.get("privata") or ""),
        pubblica=str(dati.get("pubblica") or ""),
        contatto=str(dati.get("contatto") or "mailto:shinra@localhost"),
    )
    return chiavi if chiavi.valide else None


def salva_chiavi(chiavi: ChiaviVapid) -> None:
    percorso = percorso_chiavi()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(
        json.dumps(
            {"privata": chiavi.privata, "pubblica": chiavi.pubblica, "contatto": chiavi.contatto},
            indent=2,
        ),
        encoding="utf-8",
    )
    # La chiave privata e' una credenziale: se il file finisse dove non deve,
    # chiunque potrebbe mandare notifiche a nome di questa casa.
    try:
        percorso.chmod(0o600)
    except OSError:
        logger.warning("Non sono riuscito a restringere i permessi di %s.", percorso)


def chiavi() -> Optional[ChiaviVapid]:
    """Le chiavi di questo server, generandole al primo bisogno."""
    esistenti = carica_chiavi()
    if esistenti is not None:
        return esistenti

    try:
        nuove = genera_chiavi()
    except Exception as e:
        logger.warning("Non riesco a generare le chiavi VAPID (%s).", e)
        return None

    salva_chiavi(nuove)
    logger.info("Chiavi VAPID generate in %s.", percorso_chiavi())
    return nuove


def invia(sottoscrizione: Mapping[str, Any], carico: Mapping[str, Any]) -> Esito:
    """Consegna una notifica cifrata a un endpoint.

    Non solleva mai: chi chiama sta avvisando di qualcosa, e un guasto nel
    canale non deve diventare un guasto nell'evento che lo ha innescato.
    """
    le_chiavi = chiavi()
    if le_chiavi is None:
        return Esito(False, errore="Chiavi VAPID non disponibili.")

    endpoint = str(sottoscrizione.get("endpoint") or "")
    if not endpoint:
        return Esito(False, errore="Sottoscrizione senza endpoint.")

    try:
        from pywebpush import WebPushException, webpush

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {
                    "p256dh": str(sottoscrizione.get("p256dh") or ""),
                    "auth": str(sottoscrizione.get("auth") or ""),
                },
            },
            data=json.dumps(dict(carico), ensure_ascii=False),
            vapid_private_key=le_chiavi.privata,
            vapid_claims={"sub": le_chiavi.contatto},
            timeout=10,
        )
        return Esito(True, stato=201)

    except ImportError:
        logger.warning("pywebpush non installato: le notifiche push restano spente.")
        return Esito(False, errore="pywebpush non installato.")

    except WebPushException as e:  # type: ignore[misc]
        stato = getattr(getattr(e, "response", None), "status_code", None)
        return Esito(False, stato=stato, errore=str(e))

    except Exception as e:
        return Esito(False, errore=str(e))
