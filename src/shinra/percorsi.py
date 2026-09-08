"""Dove sta il progetto, deciso una volta sola.

Nove moduli calcolavano la radice per conto proprio con `Path(__file__)` e
una catena di `.parent` lunga quanto la loro profondita': due per
`core/scheduler.py`, tre per `core/archivio/motore.py`. Ogni catena e' un
numero scritto a mano che dipende da dove sta il file, e nessuna dice quale
sia il numero giusto.

Il guaio e' che sbagliarlo non solleva niente. `DATA_DIR` finisce a puntare
una cartella che non esiste, `mkdir(parents=True)` la crea contenta, e
l'applicazione riparte con un database vuoto: nessun errore, solo la casa
che ha dimenticato tutto. Un errore visibile sarebbe stato meno pericoloso.

Questo modulo esiste perche' quel numero sia scritto in un punto solo, ed e'
la premessa dello spostamento sotto `src/shinra/` (issue #16): dopo, la
profondita' di ogni modulo cambia, e nove numeri da correggere a mano sono
nove occasioni di sbagliare in silenzio.

Riferimento: issue #16, ADR 0006.
"""

from __future__ import annotations

import os
from pathlib import Path

# Il file che dice «la radice del progetto e' qui». Serve a distinguere una
# copia di lavoro da un pacchetto installato in site-packages, dove i dati
# non stanno accanto al codice.
SEGNALE = "pyproject.toml"


def _radice() -> Path:
    """La cartella del progetto: quella che contiene `pyproject.toml`.

    `SHINRA_RADICE` ha la precedenza su tutto. Serve a chi installa il
    pacchetto sul serio — non in modalita' modificabile — e tiene i dati
    altrove: senza, l'unica alternativa sarebbe la cartella di lavoro, che
    dipende da dove e' stato lanciato il servizio ed e' esattamente il tipo
    di dipendenza nascosta che questo modulo toglie di mezzo.
    """
    scelta = os.getenv("SHINRA_RADICE")
    if scelta:
        return Path(scelta).expanduser().resolve()

    qui = Path(__file__).resolve()
    for candidata in qui.parents:
        if (candidata / SEGNALE).exists():
            return candidata

    # Installazione non modificabile: il codice sta in site-packages e sopra
    # non c'e' nessun progetto. Si lavora dove si e' stati avviati, e lo si
    # dice — non e' una situazione che questo progetto ha mai provato.
    return Path.cwd()


RADICE = _radice()

DATI = RADICE / "data"
ESEMPI = DATI / "examples"
LOG = DATI / "log"
CONFIGURAZIONE = RADICE / "config"
MIGRAZIONI = RADICE / "migrazioni"
WEB = RADICE / "web"
MODELLI_HTML = WEB / "templates"
STATICI = WEB / "static"
