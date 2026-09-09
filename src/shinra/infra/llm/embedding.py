"""Gli embedding, calcolati da Ollama e quindi in casa.

E' il punto che rende questa funzione compatibile con la promessa della fase:
**nessun testo di casa lascia la rete locale.** Un servizio di embedding nel
cloud sarebbe piu' veloce e migliore, e vorrebbe dire mandare a qualcun altro
ogni cosa che la casa sa — il nome del gatto, dove si nasconde la chiave di
scorta, a che ora esce di casa un bambino. Non e' uno scambio accettabile per
una latenza migliore.

Ollama espone due endpoint a seconda della versione: `/api/embed` (nuovo,
accetta piu' testi in una volta) e `/api/embeddings` (vecchio, uno alla
volta). Si prova il primo e si ripiega sul secondo, perche' chi ha installato
Shinra un anno fa non deve aggiornare Ollama per avere questa funzione.

Riferimento: issue #32.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

logger = logging.getLogger("Shinra.Embedding")

# Il modello predefinito. `nomic-embed-text` e' piccolo (274 MB), gira su
# hardware modesto ed e' il piu' diffuso per questo uso. Se non c'e', il
# recupero resta testuale invece di rompersi.
MODELLO_PREDEFINITO = "nomic-embed-text"


def modello() -> str:
    """Il modello di embedding configurato.

    Si legge per esteso (`settings.llm.modello_embedding`) e non con un
    `getattr`: il guardiano della issue #26 cerca proprio quella stringa nel
    codice, e un'opzione che nessuna riga nomina e' un'opzione che finisce
    nel pannello senza fare niente. Era gia' successo con le tariffe
    dell'energia.
    """
    from shinra.config.settings import settings

    return (settings.llm.modello_embedding or MODELLO_PREDEFINITO).strip()


async def calcola(testi: Sequence[str]) -> list[Optional[list[float]]]:
    """Il vettore di ogni testo, o `None` per quelli che non si sono potuti
    calcolare.

    Non solleva mai e non restituisce una lista piu' corta di quella
    ricevuta: chi chiama sta indicizzando la conoscenza di una casa, e un
    modello mancante non deve diventare un guasto — deve diventare un
    recupero solo testuale, che e' peggio ma funziona.
    """
    if not testi:
        return []

    nuovo = await _prova_api_embed(list(testi))
    if nuovo is not None:
        return nuovo

    return [await _prova_api_embeddings(t) for t in testi]


async def _prova_api_embed(testi: list[str]) -> Optional[list[Optional[list[float]]]]:
    """`/api/embed`: una chiamata sola per tutti i testi."""
    corpo = await _chiedi("/api/embed", {"model": modello(), "input": testi})
    if not corpo:
        return None

    grezzi = corpo.get("embeddings")
    if not isinstance(grezzi, list) or len(grezzi) != len(testi):
        return None

    return [_vettore(g) for g in grezzi]


async def _prova_api_embeddings(testo: str) -> Optional[list[float]]:
    """`/api/embeddings`: uno alla volta, per le versioni piu' vecchie."""
    corpo = await _chiedi("/api/embeddings", {"model": modello(), "prompt": testo})
    if not corpo:
        return None
    return _vettore(corpo.get("embedding"))


def _vettore(grezzo: Any) -> Optional[list[float]]:
    if not isinstance(grezzo, list) or not grezzo:
        return None
    try:
        return [float(x) for x in grezzo]
    except (TypeError, ValueError):
        return None


async def _chiedi(percorso: str, corpo: dict[str, Any]) -> Optional[dict[str, Any]]:
    import httpx

    from shinra.config.settings import settings

    base = (settings.llm.ollama_url or "").rstrip("/")
    if not base:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            risposta = await client.post(f"{base}{percorso}", json=corpo)
            if risposta.status_code == 200:
                return dict(risposta.json())
            logger.debug("%s ha risposto %s", percorso, risposta.status_code)
            return None
    except Exception as e:
        logger.debug("%s non raggiungibile: %s", percorso, e)
        return None


async def disponibile() -> bool:
    """Se il modello di embedding c'e' davvero.

    Serve a dire all'interfaccia perche' il recupero e' solo testuale,
    invece di lasciar credere che sia semantico e non funzioni bene.
    """
    vettori = await calcola(["prova"])
    return bool(vettori and vettori[0])
