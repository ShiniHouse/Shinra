"""Prima di comandare, verificare che la cosa esista.

L'`entity_id` che arriva a un tool viene dal modello, e il modello inventa.
Chiede `lock.porta_ingresso` perche' e' un nome plausibile, non perche'
l'abbia letto da qualche parte. Senza un controllo, quella richiesta parte
verso Home Assistant, che risponde 200 e non fa niente — e l'assistente
annuncia che la porta e' chiusa mentre e' spalancata.

Un errore chiaro qui vale piu' di dieci righe di prompt: «non conosco nessun
dispositivo che si chiami cosi'» e' una frase che il modello puo' riportare
all'utente, e che l'utente puo' capire.

Con la connessione agli eventi (issue #19) la verifica non costa niente: gli
stati sono gia' in memoria.

Riferimento: issue #20.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

logger = logging.getLogger("Shinra.Entita")


class EntitaSconosciuta(Exception):
    """Il dispositivo richiesto non esiste, o non e' del tipo giusto."""

    def __init__(self, messaggio: str, suggerimenti: Optional[list[str]] = None):
        self.suggerimenti = suggerimenti or []
        super().__init__(messaggio)


def _somiglianza(cercato: str, candidato: str) -> int:
    """Quante parole hanno in comune. Basta a proporre l'alternativa giusta."""
    parole = {p for p in cercato.replace(".", " ").replace("_", " ").split() if len(p) > 2}
    altre = {p for p in candidato.replace(".", " ").replace("_", " ").split() if len(p) > 2}
    return len(parole & altre)


async def stati_noti() -> list[dict[str, Any]]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().stati_correnti()


def risolvi(riferimento: str) -> str:
    """Da «lampadario salotto» a `light.salotto_main`, se c'e' un alias."""
    from shinra.infra.data_store import data_store

    return data_store.resolve_alias_or_entity((riferimento or "").strip())


async def verifica(
    riferimento: str,
    domini: Iterable[str],
    stati: Optional[list[dict[str, Any]]] = None,
) -> str:
    """L'`entity_id` reale, oppure un errore che si puo' riferire a voce.

    `domini` restringe al tipo giusto: chiedere di mettere in pausa una
    tapparella e' un errore che vale la pena dire, non da eseguire.

    Se la casa non risponde affatto — Home Assistant spento, nessuno stato in
    memoria — il comando passa senza verifica. E' voluto: un controllo che
    trasforma «non lo so» in «non esiste» impedirebbe di comandare la casa
    proprio nei momenti in cui e' gia' in difficolta'.
    """
    entita = risolvi(riferimento)
    ammessi = set(domini)

    elenco = stati if stati is not None else await stati_noti()
    if not elenco:
        logger.warning("Nessuno stato disponibile: %s non verificata.", entita)
        return entita

    conosciute = {s.get("entity_id", ""): s for s in elenco}

    if entita in conosciute:
        dominio = entita.split(".", 1)[0]
        if dominio not in ammessi:
            raise EntitaSconosciuta(
                f"«{entita}» e' un dispositivo di tipo {dominio}, e questa azione "
                f"vale solo per: {', '.join(sorted(ammessi))}."
            )
        return entita

    vicine = sorted(
        (i for i in conosciute if i.split(".", 1)[0] in ammessi),
        key=lambda i: -_somiglianza(entita, i),
    )
    suggerimenti = [i for i in vicine[:3] if _somiglianza(entita, i) > 0]

    messaggio = f"Non conosco nessun dispositivo chiamato «{riferimento}»."
    if suggerimenti:
        messaggio += " Forse intendevi: " + ", ".join(suggerimenti) + "."
    raise EntitaSconosciuta(messaggio, suggerimenti)


def stato_di(entity_id: str, stati: Iterable[dict[str, Any]]) -> str:
    for s in stati:
        if s.get("entity_id") == entity_id:
            return str(s.get("state", "sconosciuto"))
    return "sconosciuto"


def nome_di(entity_id: str, stati: Iterable[dict[str, Any]]) -> str:
    for s in stati:
        if s.get("entity_id") == entity_id:
            return str((s.get("attributes") or {}).get("friendly_name") or entity_id)
    return entity_id
