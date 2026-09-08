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
import sys
from pathlib import Path
from typing import Any

# Gli script si lanciano dalla copia di lavoro, dove il pacchetto puo' non
# essere installato: senza questo, `import shinra` fallirebbe.
RADICE = Path(__file__).resolve().parent.parent
SORGENTI = RADICE / "src"
if SORGENTI.is_dir() and str(SORGENTI) not in sys.path:
    sys.path.insert(0, str(SORGENTI))

VERDE, GIALLO, ROSSO, GRIGIO, FINE = "\033[32m", "\033[33m", "\033[31m", "\033[90m", "\033[0m"


def _riepilogo(letti: dict[str, list[dict[str, Any]]], sorgente: Path, destinazione: Path) -> int:
    print(f"\n{GRIGIO}Sorgente:{FINE} {sorgente}")
    print(f"{GRIGIO}Destinazione:{FINE} {destinazione}\n")
    for tabella, voci in letti.items():
        print(f"  {tabella:<16} {len(voci):>4} voci")
    totale = sum(len(v) for v in letti.values())
    print(f"  {'':<16} {'':->4}")
    print(f"  {'totale':<16} {totale:>4}\n")
    return totale


def migra(archivio: Path, prova: bool) -> int:
    from shinra.infra.db import importazione
    from shinra.infra.db import motore as modulo_motore
    from shinra.infra.db.depositi import DEPOSITI

    letti = importazione.leggi_tutto()
    _riepilogo(letti, importazione.DATA_DIR, archivio)

    if prova:
        print(f"{GIALLO}Prova: nulla e' stato scritto.{FINE}\n")
        return 0

    modulo_motore.reimposta(archivio)
    importazione.applica_migrazioni()

    occupate = [t for t, d in DEPOSITI.items() if d.conta() > 0]
    if occupate:
        print(f"{ROSSO}Il database contiene gia' dati in: {', '.join(occupate)}.{FINE}")
        print("Migrare sopra dati esistenti li duplicherebbe. Sposta o cancella")
        print(f"{archivio} e riprova.\n")
        return 2

    importazione.importa(letti)
    return _mostra_verifica(importazione.verifica(letti))


def verifica(archivio: Path) -> int:
    from shinra.infra.db import importazione
    from shinra.infra.db import motore as modulo_motore

    modulo_motore.reimposta(archivio)
    return _mostra_verifica(importazione.verifica(importazione.leggi_tutto()))


def _mostra_verifica(esito: dict[str, tuple[int, int, int]]) -> int:
    print(f"{GRIGIO}Verifica per conteggio:{FINE}\n")
    tutto_bene = True
    for tabella, (nel_file, distinti, nel_database) in esito.items():
        if nel_database == nel_file:
            print(f"  {VERDE}ok{FINE}      {tabella:<16} {nel_database:>4} / {nel_file}")
        elif nel_database == distinti:
            print(
                f"  {GIALLO}nota{FINE}    {tabella:<16} {nel_database:>4} / {nel_file}"
                f"  ({nel_file - distinti} identificativi ripetuti nel file)"
            )
        else:
            print(f"  {ROSSO}PERSI{FINE}   {tabella:<16} {nel_database:>4} / {nel_file}")
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

    from shinra.infra.db.motore import percorso_archivio

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
