"""Spezzare una frase in una cosa per pezzo, col codice e non col modello (#432, ADR 0013).

«Chiudi la tapparella e accendi la luce, poi dimmi che tempo fa» non e' una richiesta: sono tre. Un modello da tre miliardi di parametri le sbaglia piu' spesso
se gliele si da' insieme, e sceglie fra troppi strumenti; se invece il **codice** taglia la frase e ogni pezzo va al suo agente di dominio (ADR 0008), ognuno vede due o
tre strumenti. E' la strategia che il banco dei piani (`scripts/banco_piani.py`, #430) ha chiamato `scomposto`: 0 dispositivi inventati, e uguale o un poco meglio delle
altre. Qui e' la parte pura: nessuna rete, nessun modello, nessuna parola di una lingua (separatori, pronomi e nomi arrivano dal file della lingua, `agente.scomposizione`).

Le regole che i test difendono:

- **un pezzo senza un'azione non e' un'azione**: «vado a dormire» o «della camera» di «accendi le luci del bagno e della camera» si riattaccano al pezzo vicino, invece di
  diventare pezzi a se';
- **non si inventa niente**: senza parole d'azione riconoscibili la frase resta intera, e con una sola azione resta un pezzo solo;
- **«quella» prende il nome**: «accendi quella del corridoio» dopo «spegni la luce del salotto» diventa «accendi la luce del corridoio»; senza un nome prima, il pronome resta com'e';
- **c'e' un tetto**: oltre sei pezzi non si va.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Mapping, Sequence

MASSIMO_PEZZI = 6


@lru_cache(maxsize=16)
def _regex(modello: str) -> re.Pattern[str]:
    return re.compile(modello, re.IGNORECASE)


def _con_il_nome(pezzo: str, precedenti: Sequence[str], lessico: Mapping[str, Any]) -> str:
    """Il pronome («quella») prende il nome dell'ultimo dispositivo detto nei pezzi prima; senza un nome, il pezzo resta com'e'."""
    pronomi = _regex(str(lessico.get("pronomi") or r"(?!x)x"))
    nomi: Mapping[str, str] = lessico.get("nomi") or {}
    if not precedenti or not nomi or not pronomi.search(pezzo):
        return pezzo
    for prima in reversed(precedenti):
        trovati = [p for p in re.findall(r"[^\W\d_]+", prima.lower()) if p in nomi]
        if trovati:
            return pronomi.sub(nomi[trovati[-1]], pezzo, count=1)
    return pezzo


def spezza(frase: str, parole_azione: Sequence[str], lessico: Mapping[str, Any], massimo: int = MASSIMO_PEZZI) -> list[str]:
    """I pezzi di una frase, uno per cosa da fare. Con una sola azione, o nessuna riconoscibile, la frase intera.

    `parole_azione` sono le radici che dicono «qui c'e' qualcosa da fare» (`agente.parole_azione` della lingua) e `lessico` la sezione `agente.scomposizione`
    (`separatori`, `parole_in_piu`, `pronomi`, `nomi`).
    """
    testo = (frase or "").strip()
    separatore = lessico.get("separatori")
    if not testo or not separatore:
        return [testo] if testo else []
    parole = tuple(p.lower() for p in (*parole_azione, *(lessico.get("parole_in_piu") or ())))

    def ha_azione(pezzo: str) -> bool:
        return any(k in pezzo.lower() for k in parole)

    pezzi = [p.strip() for p in _regex(str(separatore)).split(testo) if p and p.strip()]
    risultato: list[str] = []
    in_attesa = ""  # i pezzi senza azione all'inizio («vado a dormire»): si attaccano al primo che ce l'ha
    for pezzo in pezzi:
        if ha_azione(pezzo):
            risultato.append(f"{in_attesa} {pezzo}".strip())
            in_attesa = ""
        elif risultato:
            risultato[-1] = f"{risultato[-1]} {lessico.get('unione', 'e')} {pezzo}"  # «... luci del bagno» + «della camera»
        else:
            in_attesa = f"{in_attesa} {pezzo}".strip()
    if in_attesa:
        if risultato:
            risultato[-1] = f"{risultato[-1]} {in_attesa}"
        else:
            risultato = [in_attesa]
    if not risultato:
        return [testo]
    risolti: list[str] = []
    for pezzo in risultato[:massimo]:
        risolti.append(_con_il_nome(pezzo, risolti, lessico))
    return risolti
