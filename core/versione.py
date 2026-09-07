"""Che versione di Shinra sta girando davvero.

Serve piu' di quanto sembri. Un server di casa si aggiorna ogni tanto, si
riavvia da solo, e a distanza di settimane non c'e' modo di ricordare se
quella macchina ha preso l'ultimo aggiornamento o si e' fermata due mesi fa.
La domanda «a che versione siamo?» merita una risposta guardando la pagina,
non entrando in SSH.

**Una sola fonte per il numero**: `pyproject.toml`, letto dai metadati del
pacchetto installato. Scriverlo anche altrove significa, prima o poi,
scriverlo diverso.

**E la revisione accanto**, perche' il numero da solo mente: fra un tag e il
successivo passano decine di commit, e un server aggiornato su `main` mostra
la versione del tag precedente pur avendo tutt'altro codice.
"""

from __future__ import annotations

import logging
import subprocess
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger("Shinra.Versione")

RADICE = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def numero() -> str:
    """Il numero di versione dichiarato nel progetto."""
    try:
        from importlib.metadata import version

        return version("shinra")
    except Exception:
        # Pacchetto non installato — succede eseguendo dai sorgenti. Si legge
        # il file, senza dipendere da una libreria per un valore che e' una
        # riga di testo.
        try:
            for riga in (RADICE / "pyproject.toml").read_text(encoding="utf-8").splitlines():
                if riga.strip().startswith("version"):
                    return riga.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
        return "sconosciuta"


@lru_cache(maxsize=1)
def revisione() -> dict[str, str]:
    """Commit, ramo e tag esatto, se il codice viene da un repository git.

    Letta una volta sola: durante l'esecuzione non cambia, e chiamare `git`
    a ogni richiesta sarebbe un processo nuovo per un valore fermo.
    """

    def chiedi(*argomenti: str) -> str:
        try:
            # Gli argomenti sono costanti scritte qui sotto, non arrivano da
            # fuori: nessun input dell'utente entra in questa chiamata.
            esito = subprocess.run(  # noqa: S603
                ["git", "-C", str(RADICE), *argomenti],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return esito.stdout.strip() if esito.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    return {
        "commit": chiedi("rev-parse", "--short", "HEAD"),
        # Sul server il codice sta su un commit staccato, quindi il ramo
        # spesso non c'e': non e' un errore, e' come deve essere.
        "ramo": chiedi("rev-parse", "--abbrev-ref", "HEAD"),
        "tag": chiedi("describe", "--tags", "--exact-match"),
    }


def descrizione() -> str:
    """Cosa mostrare a chi guarda: corta, e onesta.

    Se il commit corrisponde esattamente a un tag, il numero basta. Se no si
    aggiunge il commit, perche' dire «0.1.0» su una macchina che ha trenta
    commit in piu' sarebbe falso.
    """
    rev = revisione()
    if rev.get("tag"):
        return rev["tag"]
    if rev.get("commit"):
        return f"{numero()}+{rev['commit']}"
    return numero()


def dettaglio() -> dict[str, str]:
    """Tutto quello che serve a capire cosa sta girando."""
    rev = revisione()
    return {
        "versione": numero(),
        "descrizione": descrizione(),
        "commit": rev.get("commit", ""),
        "ramo": rev.get("ramo", ""),
        "tag": rev.get("tag", ""),
    }
