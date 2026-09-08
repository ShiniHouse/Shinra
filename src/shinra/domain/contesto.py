"""Chi sta agendo adesso, e da dove.

Tre informazioni — un identificativo di correlazione, l'attore, il canale —
che viaggiano con la richiesta in corso e non toccano nulla: nessun file,
nessuna rete, nessun database. Sono un valore, ed e' per questo che stanno
in `domain/`.

Stavano dentro `services/registro.py`, che le usa per scrivere il registro
delle azioni. Ma il registro e' *un* consumatore, non il proprietario: nel
momento in cui il tool delle serrature ha avuto bisogno di sapere da quale
canale arriva la richiesta — perche' dalla voce non si apre una porta, ADR
0004 — `skills/` avrebbe dovuto importare `services/`, che le regole di
dipendenza vietano. Il test sull'architettura l'ha bocciato, e aveva
ragione: il problema non era l'import, era che un valore stava in un
servizio.

Riferimento: issue #20, ADR 0004, docs/ARCHITECTURE.md §3.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

# Canali noti. Elencarli qui evita che un confronto con una stringa scritta
# a mano fallisca in silenzio, lasciando passare cio' che doveva fermarsi.
CANALE_WEB = "web"
CANALE_ALEXA = "alexa"


@dataclass
class ContestoRichiesta:
    correlazione: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    attore: Optional[str] = None
    canale: str = ""


_contesto: ContextVar[Optional[ContestoRichiesta]] = ContextVar("contesto_richiesta", default=None)


def contesto() -> ContestoRichiesta:
    """Il contesto della richiesta in corso, creandone uno se manca.

    Manca, per esempio, in uno script eseguito a mano: le sue azioni vanno
    comunque registrate, con una correlazione tutta loro.
    """
    corrente = _contesto.get()
    if corrente is None:
        corrente = ContestoRichiesta()
        _contesto.set(corrente)
    return corrente


def contesto_se_c_e() -> Optional[ContestoRichiesta]:
    """Il contesto, se esiste — senza crearne uno.

    Serve al formattatore dei log, che gira su ogni riga anche fuori da una
    richiesta: con `contesto()` ne nascerebbe uno apposta, e ogni riga
    avrebbe una correlazione diversa e inutile.
    """
    return _contesto.get()


def apri_contesto(attore: Optional[str] = None, canale: str = "") -> ContestoRichiesta:
    nuovo = ContestoRichiesta(attore=attore, canale=canale)
    _contesto.set(nuovo)
    return nuovo


def imposta_attore(attore: Optional[str]) -> None:
    """L'identita' spesso si scopre a meta' strada.

    Alexa consegna l'identificativo dentro gli attributi di sessione, e
    l'agente risolve il profilo solo dopo aver ricevuto il testo: il
    contesto nasce anonimo e viene completato quando si sa chi ha parlato.
    """
    if attore:
        contesto().attore = attore


def canale_corrente() -> str:
    return contesto().canale or ""
