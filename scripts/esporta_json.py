#!/usr/bin/env python3
"""Esporta il contenuto del database nei file JSON.

Dalla v0.2.0 l'archivio primario e' `data/shinra.db`. I file JSON restano
utili come formato di backup: si leggono con un editor, si copiano su una
chiavetta, si aprono fra dieci anni senza avere Shinra installato.

    python scripts/esporta_json.py                  scrive in data/esportazione/
    python scripts/esporta_json.py --in data/       sovrascrive i file originali

Per difetto scrive in una cartella nuova e **non** tocca i file JSON di
`data/`, che sono ancora la copia di sicurezza pre-migrazione: sovrascriverli
per sbaglio significherebbe perdere quella.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

VERDE, GRIGIO, FINE = "\033[32m", "\033[90m", "\033[0m"


def esporta(destinazione: Path) -> dict[str, int]:
    from core.archivio.depositi import DEPOSITI
    from core.archivio.importazione import SORGENTI

    destinazione.mkdir(parents=True, exist_ok=True)
    scritti: dict[str, int] = {}
    for nome_file, tabella in SORGENTI.items():
        voci = DEPOSITI[tabella].elenco()
        percorso = destinazione / nome_file
        # Scrittura atomica: se il processo muore a meta', il file buono di
        # prima e' ancora intero. E' il difetto che ha portato al database,
        # e non ha senso ripeterlo proprio nel backup.
        temporaneo = percorso.with_suffix(".json.tmp")
        temporaneo.write_text(json.dumps(voci, indent=2, ensure_ascii=False), encoding="utf-8")
        temporaneo.replace(percorso)
        scritti[nome_file] = len(voci)
    return scritti


def main() -> int:
    p = argparse.ArgumentParser(description="Esporta il database di Shinra in file JSON.")
    p.add_argument(
        "--in",
        dest="destinazione",
        type=Path,
        default=RADICE / "data" / "esportazione",
        help="cartella di destinazione (default: data/esportazione/)",
    )
    argomenti = p.parse_args()

    scritti = esporta(argomenti.destinazione)
    print(f"\n{GRIGIO}Esportato in:{FINE} {argomenti.destinazione}\n")
    for nome, quante in scritti.items():
        print(f"  {nome:<22} {quante:>4} voci")
    print(f"\n{VERDE}Fatto.{FINE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
