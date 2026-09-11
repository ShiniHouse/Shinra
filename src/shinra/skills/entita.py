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


class EntitaAmbigua(EntitaSconosciuta):
    """Il riferimento vale per piu' dispositivi, e non si sa quale.

    Discende da `EntitaSconosciuta` di proposito: chi gia' cattura quella
    continua a funzionare e riferisce la frase all'utente, che e' esattamente
    il comportamento giusto. Prima non esisteva e non serviva, perche' un
    riferimento ambiguo non veniva dichiarato: se ne sceglieva uno a caso.
    """


def _somiglianza(cercato: str, candidato: str) -> int:
    """Quante parole hanno in comune. Basta a proporre l'alternativa giusta."""
    parole = {p for p in cercato.replace(".", " ").replace("_", " ").split() if len(p) > 2}
    altre = {p for p in candidato.replace(".", " ").replace("_", " ").split() if len(p) > 2}
    return len(parole & altre)


async def stati_noti() -> list[dict[str, Any]]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().stati_correnti()


def risolvi(riferimento: str, stanza: Optional[str] = None) -> str:
    """Da «lampadario salotto» a `light.salotto_main`, se c'e' un alias.

    La stanza, quando non viene passata, si legge dal contesto della
    richiesta: e' li' che il canale scrive da dove sta parlando chi parla
    (issue #33). Passa per il contesto e non come parametro perche' i tool
    che chiamano questa funzione sono una dozzina e nessuno di loro ha
    ragione di sapere che esistono i satelliti — e' la stessa strada gia'
    usata per l'attore e per il canale.

    Con una stanza, «accendi la luce» diventa la luce di quella stanza senza
    bisogno di nominarla.

    Solleva `EntitaAmbigua` quando il riferimento vale per piu' dispositivi e
    non c'e' una stanza che scelga. Prima non succedeva: se ne prendeva uno a
    caso, e chi ascoltava credeva di essere stato capito.
    """
    from shinra.domain import contesto, stanze
    from shinra.infra.data_store import data_store

    dove = contesto.stanza_corrente() if stanza is None else stanza
    esito = data_store.cerca_dispositivo((riferimento or "").strip(), dove)

    if esito.tipo == stanze.AMBIGUO:
        raise EntitaAmbigua(
            f"«{riferimento}» puo' essere piu' di una cosa: "
            f"{stanze.descrivi_alternative(esito.alternative)}. Quale?",
            [d.entity_id for d in esito.alternative],
        )

    return esito.entity_id if esito.certo else (riferimento or "").strip().lower()


async def verifica(
    riferimento: str,
    domini: Iterable[str],
    stati: Optional[list[dict[str, Any]]] = None,
    stanza: Optional[str] = None,
) -> str:
    """L'`entity_id` reale, oppure un errore che si puo' riferire a voce.

    `domini` restringe al tipo giusto: chiedere di mettere in pausa una
    tapparella e' un errore che vale la pena dire, non da eseguire.

    Se la casa non risponde affatto — Home Assistant spento, nessuno stato in
    memoria — il comando passa senza verifica. E' voluto: un controllo che
    trasforma «non lo so» in «non esiste» impedirebbe di comandare la casa
    proprio nei momenti in cui e' gia' in difficolta'.
    """
    entita = risolvi(riferimento, stanza)
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


def attributi_di(entity_id: str, stati: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Gli attributi dichiarati da Home Assistant per un'entita'.

    Servono a chi deve chiedere al dispositivo cosa sa fare prima di
    chiederglielo: le modalita' di un termostato, la maschera di capacita' di
    una tapparella. Un dizionario vuoto vuol dire «non lo so», e chi lo
    riceve deve provarci lo stesso invece di rifiutare.
    """
    for s in stati:
        if s.get("entity_id") == entity_id:
            return dict(s.get("attributes") or {})
    return {}
