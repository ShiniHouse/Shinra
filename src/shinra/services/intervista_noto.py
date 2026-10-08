# -*- coding: utf-8 -*-
"""Cosa la casa sa gia', prima di rifare una domanda (#209).

Un'intervista che chiede «chi vive qui?» a una casa con quattro profili e le
stanze gia' note e' la prima cosa che si nota parlandoci. Qui si guarda il
database **prima** di ogni domanda: se la risposta c'e', la domanda si salta e
si dice perche', cosi' chi risponde sa che la casa ha letto e non e' un buco.

La funzione che decide e' pura: riceve i dati, non li va a cercare. Chi la usa
(`dati_della_casa`) li legge dal database; i test le passano quelli che vogliono.
Le frasi che dice sono nella lingua di chi risponde (#207).
"""

import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from shinra.services.intervista_comune import dice

# Una casa con un solo profilo non ha ancora detto «chi vive qui»: serve
# almeno una seconda persona perche' l'elenco dica qualcosa di piu' di chi
# sta rispondendo.
MINIMO_PROFILI = 2
MINIMO_STANZE = 2


def _senza_accenti(testo: str) -> str:
    scomposto = unicodedata.normalize("NFD", testo.lower())
    return "".join(c for c in scomposto if unicodedata.category(c) != "Mn")


def _elenco(voci: Iterable[str], lingua: str = "") -> str:
    voci = list(voci)
    if len(voci) <= 1:
        return "".join(voci)
    return ", ".join(voci[:-1]) + dice(lingua, "elenco_e") + voci[-1]


def dati_della_casa(data_store: Any) -> Dict[str, Any]:
    """Legge dal database cio' che l'intervista puo' gia' conoscere.

    Il `data_store` lo passa chi chiama: cosi' un test che ne usa uno vuoto non
    legge, per sbaglio, la conoscenza vera della casa.
    """
    from shinra.services.user_manager import user_manager

    profili = [u.name for u in user_manager.get_users() if getattr(u, "name", "")]
    stanze = sorted({str(a.get("room") or "").strip() for a in data_store.get_aliases()} - {""})
    fatti = [f for f in data_store.get_knowledge() if f.get("enabled", True)]
    return {"profili": profili, "stanze": stanze, "fatti": fatti}


def cosa_si_sa(passo: Dict[str, Any], dati: Dict[str, Any], lingua: str = "") -> Optional[str]:
    """Una frase che dice cosa si sa gia', o `None` se la domanda va fatta."""
    fonte = passo.get("noto")
    if fonte == "profili":
        nomi: List[str] = list(dati.get("profili") or [])
        if len(nomi) >= MINIMO_PROFILI:
            return dice(lingua, "noto_profili", nomi=_elenco(nomi, lingua))
    elif fonte == "stanze":
        stanze: List[str] = list(dati.get("stanze") or [])
        if len(stanze) >= MINIMO_STANZE:
            return dice(lingua, "noto_stanze", nomi=_elenco(stanze, lingua))

    parole = [_senza_accenti(p) for p in passo.get("parole") or ()]
    if parole:
        for fatto in dati.get("fatti") or []:
            if fatto.get("category") != passo["category"]:
                continue
            testo = _senza_accenti(str(fatto.get("text") or ""))
            if any(p in testo for p in parole):
                return dice(lingua, "noto_fatto", fatto=fatto["text"])
    return None
