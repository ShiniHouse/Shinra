"""Lo schema del database e il seme di una casa nuova.

Due compiti, e basta:

 - **portare lo schema all'ultima revisione** (`applica_migrazioni`), all'avvio e quando serve
   far nascere un database (`crea_vuoto`);
 - **seminare una casa nuova** (`semina_se_vuoto`): se il database non ha ancora niente, ci
   mette i dati di esempio di `data/examples/`, cosi' una installazione nuova ha almeno un
   profilo amministratore e qualche fonte di notizie.

Il passaggio dai file JSON al database — che qui stava, e che l'avvio eseguiva da solo —
e' finito con la v0.5: il database esiste dalla 0.2.0 e le case che avevano ancora file JSON
si sono migrate. Per chi parte da una versione anteprima 0.1 serve la 0.5.x, che sa ancora farlo.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from shinra import percorsi

logger = logging.getLogger("Shinra.Archivio")

# nome del file JSON -> nome della tabella
SORGENTI: dict[str, str] = {
    "users.json": "users",
    "knowledge.json": "knowledge",
    "device_aliases.json": "device_aliases",
    "modes.json": "modes",
    "sources.json": "sources",
    "timers.json": "timers",
    "reminders.json": "reminders",
}


def leggi(percorso: Path) -> list[dict[str, Any]]:
    if not percorso.exists():
        return []
    with open(percorso, "r", encoding="utf-8") as f:
        contenuto = json.load(f)
    if not isinstance(contenuto, list):
        raise ValueError(f"{percorso.name} non contiene un elenco")
    return contenuto


def leggi_tutto(cartella: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    base = cartella or percorsi.ESEMPI
    return {tabella: leggi(base / nome) for nome, tabella in SORGENTI.items()}


def applica_migrazioni() -> None:
    """Porta lo schema all'ultima revisione.

    Lo fa anche `scripts/deploy.sh` prima del riavvio; farlo pure all'avvio
    serve a chi non passa da li' — la macchina di sviluppo, un'installazione
    nuova — e non costa nulla quando lo schema e' gia' aggiornato.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(percorsi.RADICE / "alembic.ini"))
    cfg.set_main_option("script_location", str(percorsi.MIGRAZIONI))
    # Qui siamo dentro l'applicazione, che il logging se l'e' gia'
    # configurato. Senza questa riga alembic lo sostituisce con il proprio —
    # radice a WARNING e logger esistenti spenti — e da quel momento l'hub
    # non racconta piu' niente nel journal.
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")


def crea_vuoto(percorso: Path) -> None:
    """Apre un archivio nuovo al percorso indicato e ci applica le migrazioni.

    E' l'unico modo previsto di far nascere un database: `create_all` darebbe
    le stesse tabelle ma senza il segno della revisione applicata, e il primo
    `alembic upgrade` andrebbe a sbattere su tabelle gia' esistenti.
    """
    from shinra.infra.db import motore

    motore.reimposta(percorso)
    applica_migrazioni()


def archivio_vuoto() -> bool:
    from shinra.infra.db.depositi import DEPOSITI

    return all(d.conta() == 0 for d in DEPOSITI.values())


def importa(letti: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    from shinra.infra.db.depositi import DEPOSITI

    scritti: dict[str, int] = {}
    for tabella, voci in letti.items():
        if voci:
            DEPOSITI[tabella].sostituisci_tutto(voci)
        scritti[tabella] = DEPOSITI[tabella].conta()
    return scritti


def semina_se_vuoto() -> dict[str, int]:
    """Chiamata all'avvio: mette i dati di esempio solo se il database non ha ancora niente.

    E' la condizione che rende l'operazione ripetibile senza danno. Un
    database gia' popolato non viene toccato, quindi riavviare il servizio
    non riporta indietro dati che nel frattempo sono stati cancellati.
    """
    if not archivio_vuoto():
        return {}

    letti = leggi_tutto(percorsi.ESEMPI)
    if not any(letti.values()):
        return {}

    scritti = importa(letti)
    totale = sum(scritti.values())
    logger.info(
        "Casa nuova: seminate %d voci dai dati di esempio (%s).",
        totale,
        ", ".join(f"{t}={n}" for t, n in scritti.items() if n),
    )
    return scritti
