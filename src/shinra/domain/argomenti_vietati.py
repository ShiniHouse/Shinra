"""Filtro sugli argomenti vietati a un profilo.

`restricted_topics` esisteva in `UserProfile` da sempre e non era applicato da
nessuna riga: il profilo «bambino» cambiava soltanto il tono delle risposte,
non cio' a cui poteva accedere.

Cosa **non** e' questo filtro: un controllo parentale. Confronta parole, quindi
si aggira riformulando, e chiunque puo' cambiare profilo dal menu finche' i
ruoli veri non arrivano (issue #19 della v0.2.0). E' un limite dichiarato, non
una svista: serve a evitare che un argomento indesiderato compaia per caso, non
a fermare chi lo cerca apposta.
"""

from __future__ import annotations

import logging
import re
from typing import Iterable, Optional

logger = logging.getLogger("Shinra.Argomenti")

RISPOSTA_PREDEFINITA = "Di questo preferisco non parlare. Se ti serve, chiedilo a un adulto di casa."


def _termini(argomenti: Optional[Iterable[str]]) -> list[str]:
    return [t.strip().lower() for t in (argomenti or []) if t and t.strip()]


def argomento_vietato(testo: str, argomenti_vietati: Optional[Iterable[str]]) -> Optional[str]:
    """Restituisce il termine vietato trovato nel testo, o None.

    Il confronto e' su parole intere: senza, «armadio» corrisponderebbe a
    «armi» e la cameretta diventerebbe un argomento proibito.
    """
    termini = _termini(argomenti_vietati)
    if not termini or not testo:
        return None

    minuscolo = testo.lower()
    for termine in termini:
        if re.search(rf"(?<!\w){re.escape(termine)}(?!\w)", minuscolo):
            return termine
    return None


def consenti(testo: str, profilo) -> Optional[str]:
    """Verifica la richiesta di un utente. Restituisce il termine vietato, o None."""
    if profilo is None:
        return None
    trovato = argomento_vietato(testo, getattr(profilo, "restricted_topics", None))
    if trovato:
        logger.info(
            "Richiesta rifiutata per %s: argomento vietato '%s'",
            getattr(profilo, "name", "?"),
            trovato,
        )
    return trovato
