#!/usr/bin/env python3
"""Porta i dati di casa dai file JSON al database SQLite.

Regola numero uno: **i file JSON non vengono toccati.** Lo script scrive su
un database e lascia gli originali dove sono. Se qualcosa va storto, il modo
di tornare indietro e' non fare niente — i dati veri sono ancora li'.

    python scripts/migra_da_json.py --prova        mostra cosa farebbe
    python scripts/migra_da_json.py                migra su data/shinra.db
    python scripts/migra_da_json.py --verifica     confronta i conteggi

Al termine confronta, entita' per entita', quante voci c'erano nei file e
quante sono finite nel database. Se un solo numero non torna, lo dice e
restituisce un codice d'errore: e' il criterio di accettazione della issue
#12, non una cortesia.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

DATA_DIR = RADICE / "data"

# nome del file JSON -> nome della tabella
SORGENTI = {
    "users.json": "users",
    "knowledge.json": "knowledge",
    "device_aliases.json": "device_aliases",
    "modes.json": "modes",
    "sources.json": "sources",
    "timers.json": "timers",
    "reminders.json": "reminders",
}

VERDE, GIALLO, ROSSO, GRIGIO, FINE = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def leggi(percorso: Path) -> list[dict[str, Any]]:
    if not percorso.exists():
        return []
    with open(percorso, "r", encoding="utf-8") as f:
        contenuto = json.load(f)
    if not isinstance(contenuto, list):
        raise ValueError(f"{percorso.name} non contiene un elenco")
    return contenuto


def prepara_schema(archivio: Path) -> None:
    """Applica le migrazioni al database indicato.

    Non `create_all`: cosi' il database nasce gia' con il segno della
    revisione applicata, e i prossimi aggiornamenti di schema partono dal
    punto giusto invece di ritrovarsi tabelle che «esistono gia'».
    """
    from alembic import command
    from alembic.config import Config

    from core.archivio import motore as modulo_motore

    modulo_motore.reimposta(archivio)
    cfg = Config(str(RADICE / "alembic.ini"))
    cfg.set_main_option("script_location", str(RADICE / "migrazioni"))
    command.upgrade(cfg, "head")


def migra(archivio: Path, prova: bool) -> int:
    from core.archivio.depositi import DEPOSITI

    letti: dict[str, list[dict[str, Any]]] = {}
    for nome_file, tabella in SORGENTI.items():
        letti[tabella] = leggi(DATA_DIR / nome_file)

    totale = sum(len(v) for v in letti.values())
    print(f"\n{GRIGIO}Sorgente:{FINE} {DATA_DIR}")
    print(f"{GRIGIO}Destinazione:{FINE} {archivio}\n")

    for tabella, voci in letti.items():
        print(f"  {tabella:<16} {len(voci):>4} voci")
    print(f"  {'':<16} {'':->4}")
    print(f"  {'totale':<16} {totale:>4}\n")

    if prova:
        print(f"{GIALLO}Prova: nulla e' stato scritto.{FINE}\n")
        return 0

    if archivio.exists():
        prepara_schema(archivio)
        occupate = [t for t, d in DEPOSITI.items() if d.conta() > 0]
        if occupate:
            print(f"{ROSSO}Il database contiene gia' dati in: {', '.join(occupate)}.{FINE}")
            print("Migrare sopra dati esistenti li duplicherebbe. Sposta o cancella")
            print(f"{archivio} e riprova.\n")
            return 2
    else:
        prepara_schema(archivio)

    for tabella, voci in letti.items():
        if voci:
            DEPOSITI[tabella].sostituisci_tutto(voci)

    return verifica(archivio, letti)


def verifica(archivio: Path, letti: dict[str, list[dict[str, Any]]] | None = None) -> int:
    from core.archivio import motore as modulo_motore
    from core.archivio.depositi import DEPOSITI

    modulo_motore.reimposta(archivio)

    if letti is None:
        letti = {tab: leggi(DATA_DIR / nome) for nome, tab in SORGENTI.items()}

    print(f"{GRIGIO}Verifica per conteggio:{FINE}\n")
    tutto_bene = True
    for tabella, voci in letti.items():
        nel_database = DEPOSITI[tabella].conta()
        atteso = len(voci)
        # Un file puo' contenere due volte lo stesso identificativo: nel
        # database la chiave primaria ne tiene una sola. Non e' una perdita,
        # ma va detto, non nascosto.
        unici = len({v.get("id") for v in voci})
        if nel_database == atteso:
            print(f"  {VERDE}ok{FINE}      {tabella:<16} {nel_database:>4} / {atteso}")
        elif nel_database == unici:
            print(
                f"  {GIALLO}nota{FINE}    {tabella:<16} {nel_database:>4} / {atteso}"
                f"  ({atteso - unici} identificativi ripetuti nel file)"
            )
        else:
            print(f"  {ROSSO}PERSI{FINE}   {tabella:<16} {nel_database:>4} / {atteso}")
            tutto_bene = False

    if tutto_bene:
        print(f"\n{VERDE}Nessuna perdita.{FINE} I file JSON sono intatti: restano il tuo backup.")
        print("Verificato l'esito, si possono archiviare. Non prima.\n")
        return 0

    print(f"\n{ROSSO}Qualcosa non torna: il database non e' completo.{FINE}")
    print("I file JSON non sono stati toccati. Cancella il database e riprova.\n")
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Migra i dati di Shinra dai file JSON a SQLite.")
    p.add_argument("--prova", action="store_true", help="mostra cosa farebbe, senza scrivere")
    p.add_argument("--verifica", action="store_true", help="confronta i conteggi di un database gia' migrato")
    p.add_argument(
        "--archivio", type=Path, default=None, help="percorso del database (default: data/shinra.db)"
    )
    argomenti = p.parse_args()

    from core.archivio.motore import percorso_archivio

    archivio = argomenti.archivio or percorso_archivio()

    try:
        if argomenti.verifica:
            return verifica(archivio)
        return migra(archivio, argomenti.prova)
    except Exception as e:
        print(f"\n{ROSSO}Migrazione interrotta: {e}{FINE}")
        print("I file JSON non sono stati toccati.\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
