#!/usr/bin/env python3
"""Esporta il contenuto del database nei file JSON.

Dalla v0.2.0 l'archivio primario e' `data/shinra.db`. I file JSON restano
utili come formato di backup: si leggono con un editor, si copiano su una
chiavetta, si aprono fra dieci anni senza avere Shinra installato.

Per mettere al sicuro la **configurazione** c'e' ora `scripts/salvataggio.py`,
che scrive un archivio unico, dichiara di che versione e', e si rilegge da
solo: questo script resta per chi vuole i dati grezzi, tabella per tabella.
Ne' l'uno ne' l'altro scrivono segreti (issue #35).

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

# Gli script si lanciano dalla copia di lavoro, dove il pacchetto puo' non
# essere installato: senza questo, `import shinra` fallirebbe.
RADICE = Path(__file__).resolve().parent.parent
SORGENTI = RADICE / "src"
if SORGENTI.is_dir() and str(SORGENTI) not in sys.path:
    sys.path.insert(0, str(SORGENTI))

VERDE, GRIGIO, FINE = "\033[32m", "\033[90m", "\033[0m"


def esporta(destinazione: Path) -> dict[str, int]:
    from shinra.infra.db.depositi import DEPOSITI
    from shinra.infra.db.importazione import SORGENTI
    from shinra.services import salvataggio

    destinazione.mkdir(parents=True, exist_ok=True)
    scritti: dict[str, int] = {}
    for nome_file, tabella in SORGENTI.items():
        # Fino alla #35 qui finiva anche la colonna `pin`: l'impronta del PIN
        # di ogni persona di casa, in chiaro su disco, in una cartella che
        # nasce per essere copiata su una chiavetta. Sei cifre dietro una
        # funzione di hash si ritrovano in pochi secondi, quindi valevano
        # come i PIN stessi.
        #
        # Cosa sia un segreto lo decide `services/salvataggio.py`, in un
        # posto solo: qui glielo si chiede, invece di tenerne una seconda
        # copia che un giorno divergera'.
        voci = [salvataggio.riga_pubblica(tabella, riga) for riga in DEPOSITI[tabella].elenco()]
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
