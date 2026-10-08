# -*- coding: utf-8 -*-
"""Cio' che l'intervista e i suoi turni condividono: le fasi, il «si'»/«no» e le frasi nella lingua giusta.

Stanno qui, e non nel motore, perche' i turni dell'alias (`intervista_alias`) li usano senza poter importare il motore.

**Nessuna frase e' nel codice** (#207): stanno nella sezione `intervista` del file della lingua, e chi risponde le riceve
nella propria. `lingua` e' il codice della lingua del profilo; vuoto vuol dire «quella dell'installazione».
"""

import re
from typing import Any, Mapping

from shinra.infra.lingue import schemi

# Le due fasi di un passo. Fino alla #170 ce n'era una sola: si rispondeva e
# l'intervista salvava. Adesso in mezzo c'e' la conferma.
FASE_DOMANDA = "domanda"
FASE_CONFERMA = "conferma"

# Quante volte si accetta una correzione prima di salvare e proseguire. Senza
# un limite, chi risponde con una frase che il modello continua a masticare
# male resta fermo sullo stesso passo per sempre: ogni testo libero e' una
# correzione, e ogni correzione riapre la conferma.
LIMITE_CORREZIONI = 1


def sezione(lingua: str = "") -> Mapping[str, Any]:
    """La sezione `intervista` della lingua: passi, frasi, parole di si'/no, prompt."""
    return schemi(lingua or None).intervista


def dice(lingua: str, chiave: str, **valori: Any) -> str:
    """Una frase dell'intervista, con i valori al loro posto."""
    return sezione(lingua)["testi"][chiave].format_map(valori)


def normalizza(testo: str) -> str:
    """Toglie punteggiatura e maiuscole, per leggere «Sì!» come «si».

    Si conservano le lettere accentate: in italiano «e» e «è» non sono la
    stessa parola, e «no» non deve diventare un «n» che vale come «n» secco.
    """
    solo_lettere = re.sub(r"[^a-zà-ÿ]+", " ", (testo or "").lower())
    return re.sub(r"\s+", " ", solo_lettere).strip()


def _parole(lingua: str, chiave: str) -> frozenset:
    return frozenset(normalizza(p) for p in sezione(lingua)[chiave])


def e_affermativa(testo: str, lingua: str = "") -> bool:
    return normalizza(testo) in _parole(lingua, "afferma")


def e_negativa(testo: str, lingua: str = "") -> bool:
    return normalizza(testo) in _parole(lingua, "nega")


def vuole_saltare(testo: str, lingua: str = "") -> bool:
    return normalizza(testo) in _parole(lingua, "salta")
