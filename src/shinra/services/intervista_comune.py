# -*- coding: utf-8 -*-
"""Cio' che l'intervista e i suoi turni condividono: le fasi e il «si'»/«no».

Stanno qui, e non nel motore, perche' i turni dell'alias (`intervista_alias`)
li usano senza poter importare il motore.
"""

import re

# Le due fasi di un passo. Fino alla #170 ce n'era una sola: si rispondeva e
# l'intervista salvava. Adesso in mezzo c'e' la conferma.
FASE_DOMANDA = "domanda"
FASE_CONFERMA = "conferma"

# Quante volte si accetta una correzione prima di salvare e proseguire. Senza
# un limite, chi risponde con una frase che il modello continua a masticare
# male resta fermo sullo stesso passo per sempre: ogni testo libero e' una
# correzione, e ogni correzione riapre la conferma.
LIMITE_CORREZIONI = 1

AFFERMAZIONI = frozenset(
    {
        "si",
        "sì",
        "s",
        "ok",
        "okay",
        "va bene",
        "vabene",
        "giusto",
        "esatto",
        "esattamente",
        "corretto",
        "perfetto",
        "certo",
        "confermo",
        "conferma",
        "yes",
        "y",
        "tutto giusto",
        "e giusto",
        "è giusto",
        "sì esatto",
        "si esatto",
    }
)

NEGAZIONI = frozenset(
    {
        "no",
        "n",
        "nope",
        "sbagliato",
        "niente",
        "annulla",
        "salta",
        "lascia perdere",
        "no grazie",
        "non e giusto",
        "non è giusto",
    }
)

SUGGERIMENTO_CONFERMA = (
    "Rispondi «sì» per salvare, «no» per saltare, oppure riscrivi la frase come la diresti tu."
)


def normalizza(testo: str) -> str:
    """Toglie punteggiatura e maiuscole, per leggere «Sì!» come «si».

    Si conservano le lettere accentate: in italiano «e» e «è» non sono la
    stessa parola, e «no» non deve diventare un «n» che vale come «n» secco.
    """
    solo_lettere = re.sub(r"[^a-zà-ÿ]+", " ", (testo or "").lower())
    return re.sub(r"\s+", " ", solo_lettere).strip()


def e_affermativa(testo: str) -> bool:
    return normalizza(testo) in AFFERMAZIONI


def e_negativa(testo: str) -> bool:
    return normalizza(testo) in NEGAZIONI
