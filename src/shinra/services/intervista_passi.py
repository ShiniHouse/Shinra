# -*- coding: utf-8 -*-
"""I passi dell'intervista di apprendimento: una domanda, un'informazione.

Fino alla #209 ogni passo faceva tre domande in una («in quale citta', a che
piano, quante stanze»): chi risponde ne coglie una, e le altre due restano
ignote per sempre. Adesso una domanda ha un solo punto interrogativo, e un
test lo controlla sui testi.

**Il testo di ogni passo sta nel file della lingua** (#207): titolo, domanda,
suggerimento e le parole che dicono «la casa lo sa gia'» (`parole`). Qui resta
la struttura, uguale in ogni lingua: l'identificativo, la categoria e, per
due passi, la fonte che il database conosce davvero (`noto`: `profili`, `stanze`).

Se la casa sa gia' la risposta, la domanda non si rifa'. Cosa si sa lo decide
`intervista_noto`: le domande le sceglie il codice, il modello serve solo a
leggere la risposta libera.
"""

from typing import Any, Dict, List, Optional, Tuple

from shinra.services.intervista_comune import sezione

# (identificativo, categoria, fonte che il database conosce)
STRUTTURA: Tuple[Tuple[str, str, Optional[str]], ...] = (
    ("casa_citta", "casa", None),
    ("casa_piano", "casa", None),
    ("casa_stanze", "casa", "stanze"),
    ("famiglia_chi", "famiglia", "profili"),
    ("famiglia_stanze", "famiglia", None),
    ("mattina_ora", "abitudini", None),
    ("mattina_cosa", "abitudini", None),
    ("notte_ora", "abitudini", None),
    ("notte_cosa", "abitudini", None),
    ("relax", "abitudini", None),
    ("tecnico_wifi", "casa_tecnica", None),
    ("tecnico_contatore", "casa_tecnica", None),
    ("tecnico_contatto", "casa_tecnica", None),
)


def passi_per(lingua: str = "") -> List[Dict[str, Any]]:
    """I passi dell'intervista nella lingua indicata (vuota: quella dell'installazione)."""
    testi = sezione(lingua)["passi"]
    passi: List[Dict[str, Any]] = []
    for identificativo, categoria, noto in STRUTTURA:
        voce = testi[identificativo]
        passo: Dict[str, Any] = {
            "id": identificativo,
            "category": categoria,
            "title": voce["title"],
            "question": voce["question"],
            "hint": voce["hint"],
        }
        if voce.get("parole"):
            passo["parole"] = tuple(voce["parole"])
        if noto:
            passo["noto"] = noto
        passi.append(passo)
    return passi


# I passi in italiano: li usano i test e chi ha bisogno solo di identificativi e lunghezza.
INTERVIEW_STEPS: List[Dict[str, Any]] = passi_per("it")
