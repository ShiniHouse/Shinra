"""Lettura e scrittura dei segreti fuori dal file di configurazione versionato.

Fino alla 0.1.0 il token di Home Assistant, il PIN amministratore e il segreto
di sessione vivevano in `config/config.yaml`, che era tracciato da git: il
primo `git commit -a` dopo una modifica dalle impostazioni li avrebbe
pubblicati su un repository pubblico.

Da qui in avanti i segreti stanno nell'ambiente o in `.env`, che non e'
versionato. La precedenza e':

    variabile d'ambiente  >  file .env  >  config.yaml (solo compatibilita')

L'ultimo gradino serve a non rompere le installazioni esistenti: il valore
viene letto, ma `migra_segreti_su_env()` lo sposta al primo avvio e lo
cancella dal file di configurazione.

Riferimento: docs/backlog/v0.1.0/07-sec-05-segreti-fuori-da-git.md
"""

from __future__ import annotations

import logging
import os
import secrets as _secrets
import stat
from pathlib import Path

logger = logging.getLogger("Shinra.Secrets")

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

# Percorso nella configurazione -> nome della variabile d'ambiente.
# `segreto` distingue cio' che non deve MAI finire in config.yaml da cio' che
# e' solo comodo poter impostare dall'ambiente.
CAMPI_DA_AMBIENTE: dict[tuple[str, str], tuple[str, bool]] = {
    ("home_assistant", "token"): ("SHINRA_HA_TOKEN", True),
    ("security", "admin_pin"): ("SHINRA_ADMIN_PIN", True),
    ("security", "session_secret"): ("SHINRA_SESSION_SECRET", True),
    ("home_assistant", "url"): ("SHINRA_HA_URL", False),
    ("llm", "ollama_url"): ("SHINRA_OLLAMA_URL", False),
    ("alexa", "skill_id"): ("SHINRA_ALEXA_SKILL_ID", False),
}

# I campi che non devono mai essere scritti in config.yaml.
CAMPI_SEGRETI: set[tuple[str, str]] = {
    percorso for percorso, (_, segreto) in CAMPI_DA_AMBIENTE.items() if segreto
}

# Valori storici che equivalgono a «non configurato».
SEGNAPOSTO = {
    "",
    "INSERISCI_QUI_IL_TUO_LONG_LIVED_ACCESS_TOKEN",
    "shinra-secret-key-salt",
}


def _analizza_env(testo: str) -> dict[str, str]:
    valori: dict[str, str] = {}
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, _, valore = riga.partition("=")
        valore = valore.strip()
        if len(valore) >= 2 and valore[0] == valore[-1] and valore[0] in "\"'":
            valore = valore[1:-1]
        valori[chiave.strip()] = valore
    return valori


def leggi_file_env() -> dict[str, str]:
    """Contenuto di .env. Assente o illeggibile equivale a vuoto."""
    try:
        if ENV_PATH.is_file():
            return _analizza_env(ENV_PATH.read_text(encoding="utf-8"))
    except OSError as e:
        logger.warning("Impossibile leggere %s: %s", ENV_PATH, e)
    return {}


def leggi(nome: str, default: str = "") -> str:
    """Valore di una variabile: prima l'ambiente reale, poi .env."""
    dall_ambiente = os.environ.get(nome)
    if dall_ambiente is not None and dall_ambiente != "":
        return dall_ambiente
    return leggi_file_env().get(nome, default)


def scrivi(valori: dict[str, str]) -> None:
    """Aggiorna .env conservando commenti, ordine e chiavi non toccate."""
    if not valori:
        return

    righe: list[str] = []
    if ENV_PATH.is_file():
        righe = ENV_PATH.read_text(encoding="utf-8").splitlines()

    da_scrivere = dict(valori)
    risultato: list[str] = []
    for riga in righe:
        spogliata = riga.strip()
        if spogliata and not spogliata.startswith("#") and "=" in spogliata:
            chiave = spogliata.split("=", 1)[0].strip()
            if chiave in da_scrivere:
                risultato.append(f"{chiave}={da_scrivere.pop(chiave)}")
                continue
        risultato.append(riga)

    if da_scrivere:
        if risultato and risultato[-1].strip():
            risultato.append("")
        risultato.append("# Aggiunte da Shinra")
        risultato.extend(f"{k}={v}" for k, v in da_scrivere.items())

    temporaneo = ENV_PATH.with_suffix(".env.tmp")
    temporaneo.write_text("\n".join(risultato).rstrip("\n") + "\n", encoding="utf-8")
    # I permessi vanno stretti PRIMA della sostituzione: fra la scrittura e il
    # chmod il file conterrebbe segreti leggibili da chiunque.
    try:
        temporaneo.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except OSError:
        pass
    temporaneo.replace(ENV_PATH)
    logger.info("Aggiornate %d variabili in %s", len(valori), ENV_PATH.name)


def genera_segreto_sessione() -> str:
    return _secrets.token_hex(32)


def e_segnaposto(valore: str | None) -> bool:
    """Vero se il valore equivale a «non configurato»."""
    return (valore or "").strip() in SEGNAPOSTO
