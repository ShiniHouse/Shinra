"""Il passaggio dei dati dai file JSON al database, una volta sola.

Sta qui e non dentro lo script perche' lo usano in due: `scripts/migra_da_json.py`,
quando lo lanci a mano, e l'avvio del servizio, che lo esegue da se' se trova
un database vuoto accanto a file JSON pieni. Duplicarlo avrebbe voluto dire
due comportamenti che divergono al primo ritocco.

**I file JSON non vengono mai toccati.** Ne' modificati ne' cancellati ne'
rinominati: restano il modo di tornare indietro.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core import percorsi

logger = logging.getLogger("Shinra.Archivio")

DATA_DIR = percorsi.DATI

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
    base = cartella or DATA_DIR
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
    command.upgrade(cfg, "head")


def crea_vuoto(percorso: Path) -> None:
    """Apre un archivio nuovo al percorso indicato e ci applica le migrazioni.

    E' l'unico modo previsto di far nascere un database: `create_all` darebbe
    le stesse tabelle ma senza il segno della revisione applicata, e il primo
    `alembic upgrade` andrebbe a sbattere su tabelle gia' esistenti.
    """
    from core.archivio import motore

    motore.reimposta(percorso)
    applica_migrazioni()


def archivio_vuoto() -> bool:
    from core.archivio.depositi import DEPOSITI

    return all(d.conta() == 0 for d in DEPOSITI.values())


def importa(letti: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    from core.archivio.depositi import DEPOSITI

    scritti: dict[str, int] = {}
    for tabella, voci in letti.items():
        if voci:
            DEPOSITI[tabella].sostituisci_tutto(voci)
        scritti[tabella] = DEPOSITI[tabella].conta()
    return scritti


def verifica(letti: dict[str, list[dict[str, Any]]]) -> dict[str, tuple[int, int, int]]:
    """Per ogni tabella: quante voci nel file, quante distinte, quante nel database.

    Le voci distinte servono a distinguere una perdita da un file che
    conteneva due volte lo stesso identificativo — nel database la chiave
    primaria ne tiene una sola. Non e' una perdita, ma va detto.
    """
    from core.archivio.depositi import DEPOSITI

    esito: dict[str, tuple[int, int, int]] = {}
    for tabella, voci in letti.items():
        esito[tabella] = (len(voci), len({v.get("id") for v in voci}), DEPOSITI[tabella].conta())
    return esito


def importa_se_vuoto() -> dict[str, int]:
    """Chiamata all'avvio: migra i JSON solo se il database non ha ancora niente.

    E' la condizione che rende l'operazione ripetibile senza danno. Un
    database gia' popolato non viene toccato, quindi riavviare il servizio
    non riporta indietro dati che nel frattempo sono stati cancellati.
    """
    if not archivio_vuoto():
        return {}

    letti = leggi_tutto()
    if not any(letti.values()):
        return {}

    scritti = importa(letti)
    totale = sum(scritti.values())
    logger.info(
        "Dati importati dai file JSON: %d voci (%s). Gli originali restano in %s.",
        totale,
        ", ".join(f"{t}={n}" for t, n in scritti.items() if n),
        DATA_DIR,
    )
    return scritti
