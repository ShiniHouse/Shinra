#!/usr/bin/env python3
"""Salva la configurazione della casa, e la rimette dov'era.

    python scripts/salvataggio.py salva
    python scripts/salvataggio.py salva --in /mnt/chiavetta/shinra.json
    python scripts/salvataggio.py guarda --da data/salvataggi/shinra-2026....json
    python scripts/salvataggio.py ripristina --da ... --conferma

Cosa entra e cosa no lo decide `shinra.services.salvataggio`, che e' anche
l'unico posto in cui si dice cos'e' un segreto. I segreti non entrano mai:
ne' il token di Home Assistant, ne' i PIN.

`ripristina` **sostituisce** la configurazione, non la fonde. Per questo
senza `--conferma` non fa niente e si limita a mostrare cosa perderesti:
un salvataggio serve anche a non essere sorpresi da chi lo ripristina.

Riferimento: issue #35.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Gli script si lanciano dalla copia di lavoro, dove il pacchetto puo' non
# essere installato: senza questo, `import shinra` fallirebbe.
RADICE = Path(__file__).resolve().parent.parent
SORGENTI = RADICE / "src"
if SORGENTI.is_dir() and str(SORGENTI) not in sys.path:
    sys.path.insert(0, str(SORGENTI))

VERDE, GIALLO, ROSSO, GRIGIO, FINE = (
    "\033[32m",
    "\033[33m",
    "\033[31m",
    "\033[90m",
    "\033[0m",
)


def _salva(destinazione: Path | None) -> int:
    from shinra.services import salvataggio

    percorso = destinazione or (salvataggio.cartella_predefinita() / salvataggio.nome_predefinito())
    scritte = salvataggio.scrivi(percorso)

    print(f"\n{GRIGIO}Salvato in:{FINE} {percorso}\n")
    for nome, quante in scritte.items():
        print(f"  {nome:<18} {quante:>4} voci   {GRIGIO}{salvataggio.TABELLE[nome]}{FINE}")
    print(f"\n{GRIGIO}Fuori dall'archivio, apposta:{FINE}")
    for nome, perche in salvataggio.FUORI.items():
        print(f"  {nome:<18}        {GRIGIO}{perche}{FINE}")
    print(f"\n{GRIGIO}Nessun segreto: ne' token, ne' PIN.{FINE}")
    print(f"{VERDE}Fatto.{FINE}\n")
    return 0


def _guarda(origine: Path) -> int:
    from shinra.services import salvataggio

    archivio = salvataggio.leggi(origine)
    intestazione = archivio["shinra"]
    print(f"\n{GRIGIO}Archivio:{FINE} {origine}")
    print(f"{GRIGIO}Scritto il:{FINE} {intestazione.get('creato_il') or 'non dichiarato'}")
    print(f"{GRIGIO}Da Shinra:{FINE}  {intestazione.get('versione') or 'non dichiarata'}")
    print(f"{GRIGIO}Schema:{FINE}     {intestazione.get('schema')}\n")

    print(f"  {'tabella':<18} {'adesso':>8} {'archivio':>10}")
    for nome, quadro in salvataggio.anteprima(archivio).items():
        adesso, dopo = quadro["adesso"], quadro["nell_archivio"]
        colore = GIALLO if adesso and adesso != dopo else GRIGIO
        print(f"  {nome:<18} {colore}{adesso:>8}{FINE} {dopo:>10}")
    print(f"\n{GIALLO}Ripristinare sostituisce: la colonna «adesso» sparisce.{FINE}\n")
    return 0


def _ripristina(origine: Path, conferma: bool) -> int:
    from shinra.services import salvataggio

    archivio = salvataggio.leggi(origine)
    if not conferma:
        _guarda(origine)
        print(f"{ROSSO}Non ho toccato niente.{FINE} Rilancia con --conferma se e' quello che vuoi.\n")
        return 1

    scritte = salvataggio.ripristina(archivio)
    print(f"\n{GRIGIO}Ripristinato da:{FINE} {origine}\n")
    for nome, quante in scritte.items():
        print(f"  {nome:<18} {quante:>4} voci")
    print(f"\n{GIALLO}I PIN non sono nell'archivio e non sono tornati:{FINE}")
    print(f"  chi entrava col PIN lo reimposta con {GRIGIO}scripts/imposta_pin.py{FINE}.")
    print(f"\n{VERDE}Fatto.{FINE}\n")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Salvataggio e ripristino della configurazione.")
    comandi = p.add_subparsers(dest="comando", required=True)

    salva = comandi.add_parser("salva", help="scrive un archivio")
    salva.add_argument("--in", dest="destinazione", type=Path, default=None)

    guarda = comandi.add_parser("guarda", help="dice cosa contiene un archivio, senza toccare niente")
    guarda.add_argument("--da", dest="origine", type=Path, required=True)

    ripristina = comandi.add_parser("ripristina", help="rimette la casa come nell'archivio")
    ripristina.add_argument("--da", dest="origine", type=Path, required=True)
    ripristina.add_argument("--conferma", action="store_true", help="senza, non tocca niente")

    argomenti = p.parse_args()

    from shinra.services.salvataggio import ArchivioNonValido

    try:
        if argomenti.comando == "salva":
            return _salva(argomenti.destinazione)
        if argomenti.comando == "guarda":
            return _guarda(argomenti.origine)
        return _ripristina(argomenti.origine, argomenti.conferma)
    except ArchivioNonValido as errore:
        print(f"\n{ROSSO}Non posso leggerlo:{FINE} {errore}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
