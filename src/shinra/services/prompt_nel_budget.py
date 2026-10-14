"""Far stare il prompt nel contesto del modello: la finestra della storia si adatta al budget (#257, #244).

Prima la storia era un numero fisso (dieci scambi) e, quando il prompt non ci stava, Ollama tagliava **l'inizio in silenzio**:
spariva per primo il prompt di sistema. Adesso la storia grezza e' **cio' che resta del budget** dopo sistema, strumenti,
ricordi e domanda: con un contesto largo cresce, con una richiesta che porta molti strumenti si restringe da sola. Si taglia
nell'ordine dichiarato in `domain/budget.py` — prima la storia dal messaggio piu' vecchio, poi i ricordi meno pertinenti —
**mai** il sistema, gli strumenti scelti e la domanda, e ogni taglio lascia una riga nel log.

Misurato il 2026-10-13 (qwen2.5:3b): piu' storia grezza non e' sempre meglio — con una sola risposta inventata fra i
messaggi il modello non chiama piu' lo strumento (0 su 3, contro 3 su 3 a storia pulita). Tagliare la storia non e' quindi
solo un obbligo del contesto: e' spesso un vantaggio.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from shinra.domain import budget

logger = logging.getLogger("Shinra")


@dataclass
class Adattato:
    messaggi: List[Dict[str, Any]]
    conoscenza: str
    misura: budget.Misura
    taglio: budget.Taglio


def _comincia_da_chi_parla(storia: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una storia tagliata non deve iniziare a meta' di uno scambio: si parte dal primo messaggio della persona."""
    for i, m in enumerate(storia):
        if m.get("role") == "user":
            return storia[i:]
    return []


def adatta(
    messaggi: List[Dict[str, Any]],
    schemi: List[Dict[str, Any]],
    conoscenza: str,
    num_ctx: int,
    risposta: int,
) -> Adattato:
    """Restituisce i messaggi (ed eventualmente i ricordi) ridotti fino a stare nel contesto.

    `messaggi` e' come lo riceve il modello: il sistema per primo, poi la storia, poi la domanda (con il contesto della
    richiesta, ricordi compresi). Se ci sta, torna uguale. Se non ci sta anche senza storia e senza ricordi, torna cio' che
    si e' potuto togliere e `taglio.insufficiente` e' vero: chi chiama deve dirlo, non tagliare di nascosto.
    """
    sistema = str(messaggi[0].get("content", "")) if messaggi else ""
    ultimo = str(messaggi[-1].get("content", "")) if len(messaggi) > 1 else ""
    storia: List[Dict[str, Any]] = messaggi[1:-1] if len(messaggi) > 2 else []
    strumenti = json.dumps(schemi, ensure_ascii=False) if schemi else ""
    domanda = ultimo.replace(conoscenza, "") if conoscenza else ultimo

    misurato = budget.misura(
        num_ctx,
        risposta,
        sistema=sistema,
        strumenti=strumenti,
        ricordi=conoscenza or "",
        storia=storia,
        domanda=domanda,
    )
    if not misurato.sfora:
        return Adattato(messaggi, conoscenza, misurato, budget.Taglio())

    righe = conoscenza.split("\n") if conoscenza else []
    parte, ricordi_rimasti, taglio = budget.riduci(misurato, storia, righe)
    storia_rimasta = _comincia_da_chi_parla([dict(m) for m in parte])
    taglio.storia_tolta = len(storia) - len(storia_rimasta)

    nuova_conoscenza = "\n".join(ricordi_rimasti) if taglio.ricordi_tolti else conoscenza
    nuovo_ultimo = dict(messaggi[-1])
    if taglio.ricordi_tolti and conoscenza:
        nuovo_ultimo["content"] = ultimo.replace(conoscenza, nuova_conoscenza)
    nuovi = [messaggi[0], *storia_rimasta, nuovo_ultimo] if len(messaggi) > 1 else list(messaggi)

    finale = budget.misura(
        num_ctx,
        risposta,
        sistema=sistema,
        strumenti=strumenti,
        ricordi=nuova_conoscenza or "",
        storia=storia_rimasta,
        domanda=domanda,
    )
    if finale.sfora > 0:
        # Nemmeno senza storia e senza ricordi ci sta: tagliare non servirebbe a niente e si perderebbe il filo della
        # conversazione («spegnila» dopo «accendi la luce»). Si lascia com'e' e lo si dice: e' il caso di un contesto troppo
        # piccolo per il prompt, e la cura e' allargare `llm.num_ctx`, non buttare la storia.
        logger.warning(
            "[Shinra] Il prompt non ci sta nel contesto nemmeno senza storia (%s token, disponibili %s): lo lascio com'e'. "
            "Con `llm.num_ctx` piu' largo la storia si adatta da sola.",
            finale.totale,
            finale.disponibile,
        )
        insufficiente = budget.Taglio(insufficiente=True, motivi=["il prompt e' piu' largo del contesto"])
        return Adattato(messaggi, conoscenza, misurato, insufficiente)

    logger.warning(
        "[Shinra] Il prompt non ci stava nel contesto (%s token, disponibili %s): %s. Ora: %s",
        misurato.totale,
        misurato.disponibile,
        "; ".join(taglio.motivi) or "niente da tagliare",
        finale.come_riga(),
    )
    return Adattato(nuovi, nuova_conoscenza, finale, taglio)
