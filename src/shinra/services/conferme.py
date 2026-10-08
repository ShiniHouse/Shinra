"""Le conferme delle azioni sensibili (issue #192).

Il modello sceglie uno strumento; se l'azione e' di quelle che `domain/sensibilita.py`
chiama sensibili — aprire una serratura, disinserire l'allarme, alzare il garage —
non parte. Qui si ricorda cosa e' stato chiesto e a chi, e si aspetta che **la stessa
persona, sullo stesso canale**, dica di si'.

Quattro proprieta', ognuna con il suo perche':

 - **Una conferma e' di una persona.** Chi conferma deve essere chi ha chiesto: la conferma
   di Sam non apre la porta chiesta da Alessio. Per questo si indicizza per attore e canale,
   non per dispositivo come facevano le conferme dentro gli strumenti.
 - **Una conferma e' di un'azione sola.** Si ricorda l'azione esatta, con i suoi argomenti: il
   «si'» esegue quella, non qualcosa che il modello ha rimesso insieme nel frattempo. E si usa
   una volta. Una richiesta nuova sostituisce la precedente, e lo si scrive nel registro.
 - **Una conferma scade.** Tre minuti: il tempo di rispondere, non quello perche' un «si'»
   detto per altro apra la porta. Alla scadenza non parte niente.
 - **Non sa chi sei, non parte.** Una voce che nessun profilo riconosce, o un comando senza un
   canale a cui chiedere, non possono ricevere una conferma: l'azione viene rifiutata e lo dice.

Ogni richiesta, conferma, rifiuto, scadenza e annullamento finisce nel registro delle azioni,
con il nome dello strumento e il bersaglio — mai gli argomenti, che possono contenere il
codice dell'allarme.

**Dove si ferma il modello.** Il «si'» non lo scrive il modello: lo legge un intento
(`services/intenti/conferma.py`), che viene prima del modello e confronta chi parla con chi
aveva chiesto. Un piano o un agente (#190, #191) che incontra un'azione sensibile ottiene la
stessa risposta `conferma_richiesta` di un singolo strumento, e si sospende da solo.

Riferimento: issue #192.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from shinra.domain import sensibilita
from shinra.domain.contesto import contesto
from shinra.services import registro

logger = logging.getLogger("Shinra.Conferme")

DURATA_S = 180.0

# Chi agisce senza un'identita' verificata ma anche senza essere un'identita' ignota:
# l'autenticazione spenta, in casa. Una conferma gli appartiene lo stesso.
SENZA_PROFILO = "(senza profilo)"

Chiave = Tuple[str, str]


@dataclass
class Conferma:
    id: int
    profilo: str
    canale: str
    tool: str
    argomenti: Dict[str, Any]
    bersaglio: str
    scade: float
    timer: Optional[asyncio.TimerHandle] = field(default=None, repr=False)


_attese: Dict[Chiave, Conferma] = {}
_contatore = 0


def _risolvi_alias(nome: str) -> Optional[str]:
    from shinra.infra.data_store import data_store

    cercato = nome.strip().lower()
    for alias in data_store.get_aliases():
        voce = (alias.get("alias") or "").lower()
        if voce and (voce == cercato or voce in cercato or cercato in voce):
            return alias.get("entity_id")
    return None


def _chi() -> Optional[str]:
    """Chi sta chiedendo, o `None` se nessuno puo' dirsi tale."""
    ctx = contesto()
    if ctx.identita_ignota:
        return None
    return ctx.attore or SENZA_PROFILO


def _scrivi(azione: str, esito: str, c: Optional[Conferma] = None, tool: str = "", **extra: Any) -> None:
    dettagli: Dict[str, Any] = {"tool": c.tool if c else tool}
    if c:
        dettagli["bersaglio"] = c.bersaglio
    dettagli.update(extra)
    registro.registra(
        f"conferma.{azione}",
        esito=esito,
        dettagli=dettagli,
        attore=c.profilo if c and c.profilo != SENZA_PROFILO else None,
        canale=c.canale if c else None,
    )


def _togli(c: Conferma) -> None:
    if c.timer is not None:
        c.timer.cancel()
    if _attese.get((c.profilo, c.canale)) is c:
        del _attese[(c.profilo, c.canale)]


def _scaduta(c: Conferma) -> None:
    """Il tempo e' finito senza una risposta: non si esegue niente, e si scrive."""
    if _attese.get((c.profilo, c.canale)) is not c:
        return
    del _attese[(c.profilo, c.canale)]
    _scrivi("scaduta", registro.ESITO_OK, c)


def _frase(chiave: str, **valori: Any) -> str:
    from shinra.infra.lingue import schemi

    return schemi("").dice(chiave, **valori)


def _rifiuto(chiave: str, **extra: Any) -> Dict[str, Any]:
    messaggio = _frase(chiave)
    return {"success": False, "error": messaggio, "message": messaggio, "permesso_negato": False, **extra}


# --------------------------------------------------------------------- il varco


def filtra(tool: str, argomenti: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Il varco di `execute_tool`: `None` se l'azione puo' partire, altrimenti la risposta.

    Una risposta con `conferma_richiesta` vuol dire «sto aspettando una persona»; con
    `rifiutata`, che non partira' qualunque cosa si dica.
    """
    classe = sensibilita.classifica(tool, argomenti, _risolvi_alias)
    if classe == sensibilita.SICURA:
        return None

    if classe == sensibilita.VIETATA:
        _scrivi("vietata", registro.ESITO_NEGATO, tool=tool)
        return _rifiuto("conferma_vietata", rifiutata=True)

    ctx = contesto()
    chi = _chi()
    if chi is None:
        _scrivi(
            "senza_identita", registro.ESITO_NEGATO, tool=tool, bersaglio=sensibilita.bersaglio_di(argomenti)
        )
        return _rifiuto("conferma_senza_identita", rifiutata=True)
    if not ctx.canale:
        # Nessuno a cui chiedere: un compito dello scheduler, una chiamata senza interlocutore.
        _scrivi(
            "senza_canale", registro.ESITO_NEGATO, tool=tool, bersaglio=sensibilita.bersaglio_di(argomenti)
        )
        return _rifiuto("conferma_senza_canale", rifiutata=True)

    return _richiedi(chi, ctx.canale, tool, argomenti)


def _richiedi(chi: str, canale: str, tool: str, argomenti: Dict[str, Any]) -> Dict[str, Any]:
    global _contatore
    precedente = _attese.get((chi, canale))
    if precedente is not None:
        _togli(precedente)
        _scrivi("annullata", registro.ESITO_OK, precedente, motivo="sostituita da una richiesta nuova")

    _contatore += 1
    conferma = Conferma(
        id=_contatore,
        profilo=chi,
        canale=canale,
        tool=tool,
        argomenti=dict(argomenti),
        bersaglio=sensibilita.bersaglio_di(argomenti),
        scade=time.monotonic() + DURATA_S,
    )
    _attese[(chi, canale)] = conferma
    try:
        conferma.timer = asyncio.get_running_loop().call_later(DURATA_S, _scaduta, conferma)
    except RuntimeError:  # senza ciclo di eventi (un test sincrono): si scade alla prima domanda
        conferma.timer = None
    _scrivi("richiesta", registro.ESITO_OK, conferma, scade_tra_s=int(DURATA_S))

    messaggio = _frase("conferma_richiesta", azione=_descrizione(conferma), minuti=int(DURATA_S // 60))
    return {"success": False, "conferma_richiesta": True, "message": messaggio, "error": messaggio}


def _descrizione(c: Conferma) -> str:
    return f"{c.tool.replace('_', ' ')} {c.bersaglio}".strip()


# ------------------------------------------------------------- la risposta della persona


def in_attesa() -> Optional[Conferma]:
    """La conferma di chi sta parlando adesso, su questo canale — se c'e' ed e' viva."""
    chi = _chi()
    canale = contesto().canale
    if chi is None or not canale:
        return None
    c = _attese.get((chi, canale))
    if c is None:
        return None
    if c.scade <= time.monotonic():
        _togli(c)
        _scrivi("scaduta", registro.ESITO_OK, c)
        return None
    return c


async def rispondi(accettata: bool) -> Dict[str, Any]:
    """La persona ha detto si' o no. Esegue (una volta) o scarta.

    Ritorna `{"esito": ...}` con uno fra `nessuna`, `scaduta`, `rifiutata`, `eseguita`;
    per `eseguita` anche `risultato`, la risposta dello strumento.
    """
    chi = _chi()
    canale = contesto().canale
    c = _attese.get((chi, canale)) if chi is not None and canale else None
    if c is None:
        return {"esito": "nessuna"}
    if c.scade <= time.monotonic():
        _togli(c)
        _scrivi("scaduta", registro.ESITO_OK, c)
        return {"esito": "scaduta"}

    _togli(c)  # prima di eseguire: una conferma si usa una volta sola, anche se l'esecuzione fallisce
    if not accettata:
        _scrivi("rifiutata", registro.ESITO_OK, c)
        return {"esito": "rifiutata"}

    _scrivi("accettata", registro.ESITO_OK, c)
    from shinra.skills.registry import execute_tool

    risultato = await execute_tool(c.tool, c.argomenti, _confermata=True)
    return {"esito": "eseguita", "risultato": risultato, "tool": c.tool}


def azzera() -> None:
    """Solo per i test."""
    for c in list(_attese.values()):
        if c.timer is not None:
            c.timer.cancel()
    _attese.clear()
