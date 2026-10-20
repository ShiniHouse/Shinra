"""Un'abitudine detta a parole diventa una routine, letta dal codice e non indovinata dal modello (#210).

«La sera chiudo le tapparelle e accendo la luce del corridoio»: due azioni, ognuna con un verbo e un oggetto. Un modello da tre
miliardi di parametri sa leggerla male (ne ha tirato fuori frasi come «le serrature siano chiuse» invece di una routine) e puo'
inventare dispositivi; il codice no. Questo modulo spezza la frase, riconosce i verbi e confronta gli oggetti con i dispositivi
**veri** della casa. Cio' che non riconosce non lo inventa: lo lascia come riferimento ignoto, e chi controlla la routine
(`intervista_routine.controlla_routine`) lo scarta dicendo quale.

Le regole che i test difendono:

- **un oggetto ambiguo non si indovina**: «la luce» con cinque luci in casa non accende tutto. Piu' dispositivi valgono solo se la
  frase e' al plurale («le tapparelle», «tutte le luci»), e quel plurale lo dice il file della lingua;
- **il verbo decide il tipo di dispositivo**: «chiudo» e «apro» valgono per tapparelle e tende, «accendo» e «spengo» per il
  resto; una luce non si «chiude»;
- **un verbo senza oggetto non fa niente**, e un oggetto senza verbo eredita quello della parte di frase prima («accendo la luce del
  corridoio e della cucina»).

Puro: nessuna rete, nessun database, nessuna parola di una lingua (arrivano dal file della lingua, `intervista.abitudine`).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Sequence

MASSIMO_PER_FRASE = 12


def _parole(testo: str) -> list[str]:
    return re.findall(r"[^\W_]+", (testo or "").casefold(), flags=re.UNICODE)


def _stessa(a: str, b: str) -> bool:
    """Due parole sono la stessa se differiscono solo per la fine («tapparelle» / «tapparella», «luci» / «luce»)."""
    comune = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        comune += 1
    return comune >= max(3, min(len(a), len(b)) - 1)


def _significative(parole: Sequence[str], vuote: frozenset[str]) -> list[str]:
    return [p for p in parole if p not in vuote and len(p) > 1]


def _comando(verbo: str, dominio: str) -> Optional[str]:
    """Il comando per questo verbo su questo tipo di dispositivo, o `None` se non ha senso («chiudo la luce»)."""
    if verbo in ("open_cover", "close_cover"):
        return verbo if dominio == "cover" else None
    if dominio == "cover":
        return None  # accendere/spegnere una tapparella non e' un comando che conosciamo
    return verbo


def routine_dalla_frase(
    frase: str,
    entita: Mapping[str, str],
    alias: Sequence[Mapping[str, Any]],
    lessico: Mapping[str, Any],
    nome: str = "",
) -> Optional[dict[str, Any]]:
    """La routine che questa frase descrive, o `None` se non descrive nessuna azione.

    `entita` e' `entity_id -> nome`; `alias` sono i nomi che la casa ha dato ai dispositivi. `lessico` e' la sezione
    `intervista.abitudine` della lingua: `verbi` (forma -> comando), `separatori` (espressione regolare), `vuote` (parole che
    non dicono quale dispositivo) e `plurali` (le parole che dicono «piu' di uno»).
    """
    verbi: Mapping[str, str] = lessico["verbi"]
    vuote = frozenset(str(p).casefold() for p in lessico["vuote"]) | frozenset(verbi)
    plurali = frozenset(str(p).casefold() for p in lessico["plurali"])
    separatore = re.compile(str(lessico["separatori"]), re.IGNORECASE)

    nomi: dict[str, set[str]] = {}
    for entity_id, friendly in entita.items():
        nomi[entity_id] = set(_significative(_parole(friendly), vuote))
    for a in alias:
        reale = str(a.get("entity_id") or "")
        if reale in nomi:
            nomi[reale] |= set(_significative(_parole(str(a.get("alias") or "")), vuote))

    azioni: list[dict[str, Any]] = []
    visti: set[tuple[str, str]] = set()
    ultimo_verbo: Optional[str] = None

    for parte in separatore.split(frase or ""):
        parole = _parole(parte)
        verbo = next((verbi[p] for p in parole if p in verbi), None)
        verbo = verbo or ultimo_verbo
        if verbo is None:
            continue
        oggetto = _significative([p for p in parole if p not in verbi], vuote)
        if not oggetto:
            continue
        ultimo_verbo = verbo
        plurale = any(p in plurali for p in parole)

        trovati = [
            e
            for e, n in nomi.items()
            if all(any(_stessa(v, x) for x in n) for v in oggetto)
            and _comando(verbo, e.split(".")[0]) is not None
        ]
        if not trovati:
            azioni.append({"type": "ha_device", "entity_id": " ".join(oggetto), "action": verbo})
            continue
        if len(trovati) > 1 and not plurale:
            # «la luce» con piu' luci in casa: non si accende a caso. Il riferimento resta ambiguo e viene scartato.
            azioni.append({"type": "ha_device", "entity_id": " ".join(oggetto), "action": verbo})
            continue
        for e in trovati:
            chiave = (e, str(_comando(verbo, e.split(".")[0])))
            if chiave in visti or len(azioni) >= MASSIMO_PER_FRASE:
                continue
            visti.add(chiave)
            azioni.append({"type": "ha_device", "entity_id": e, "action": _comando(verbo, e.split(".")[0])})

    if not azioni:
        return None
    return {
        "name": (nome or " ".join(_parole(frase)[:4])).strip().capitalize() or "Routine",
        "description": " ".join((frase or "").split())[:200],
        "trigger_phrases": [],
        "actions": azioni,
    }
