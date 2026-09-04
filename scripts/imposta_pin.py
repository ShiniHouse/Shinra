#!/usr/bin/env python3
"""Imposta o azzera il PIN di un profilo dalla riga di comando.

Serve quando non si riesce piu' a entrare: il PIN del primo avvio e' scorso
via dal log, oppure e' stato dimenticato. Senza questo strumento l'unico
rimedio sarebbe modificare users.json a mano, e il PIN va scritto cifrato:
un valore in chiaro li' dentro non funzionerebbe.

Da eseguire sul server, con l'ambiente virtuale del progetto:

    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py --elenco
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py alessio
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py alessio --pin 481920
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/imposta_pin.py alessio --azzera

Non richiede che il servizio sia fermo: al prossimo accesso vale il PIN nuovo.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.user_manager import user_manager
from server.sicurezza import verifica_pin


def elenca() -> int:
    utenti = user_manager.get_users()
    if not utenti:
        print("Nessun profilo configurato.", file=sys.stderr)
        return 1
    larghezza = max(len(u.id) for u in utenti)
    print(f"{'IDENTIFICATIVO'.ljust(larghezza)}  NOME                 RUOLO      PIN")
    for u in utenti:
        stato = "impostato" if u.pin else "assente"
        print(f"{u.id.ljust(larghezza)}  {u.name[:20]:20} {u.role:10} {stato}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("utente", nargs="?", help="identificativo del profilo (vedi --elenco)")
    p.add_argument("--elenco", action="store_true", help="elenca i profili e chi ha un PIN")
    p.add_argument("--pin", help="il PIN da impostare; se assente viene chiesto senza mostrarlo")
    p.add_argument("--genera", action="store_true", help="genera un PIN casuale di sei cifre")
    p.add_argument("--azzera", action="store_true", help="rimuove il PIN del profilo")
    args = p.parse_args()

    if args.elenco or not args.utente:
        return elenca()

    profilo = user_manager.get_user_by_id(args.utente)
    if not profilo:
        print(f"Profilo '{args.utente}' non trovato. Usa --elenco per vederli.", file=sys.stderr)
        return 1

    if args.azzera:
        user_manager.imposta_pin(profilo.id, None)
        print(f"PIN rimosso da {profilo.name}.")
        print("Attenzione: senza PIN quel profilo non puo' piu' accedere.")
        return 0

    if args.genera:
        pin = f"{secrets.randbelow(1_000_000):06d}"
        print(f"PIN generato per {profilo.name}: {pin}")
    elif args.pin:
        pin = args.pin.strip()
    else:
        pin = getpass.getpass(f"Nuovo PIN per {profilo.name}: ").strip()
        if pin != getpass.getpass("Ripetilo: ").strip():
            print("I due PIN non coincidono.", file=sys.stderr)
            return 1

    if len(pin) < 4 or not pin.isdigit():
        print("Il PIN deve essere di almeno quattro cifre.", file=sys.stderr)
        return 1

    user_manager.imposta_pin(profilo.id, pin)

    # Rilegge dal disco e verifica: senza questo controllo un errore di
    # scrittura si scoprirebbe solo davanti alla schermata di accesso.
    riletto = user_manager.get_user_by_id(profilo.id)
    if not riletto or not verifica_pin(pin, riletto.pin):
        print("Il PIN non risulta salvato correttamente.", file=sys.stderr)
        return 1

    print(f"PIN aggiornato per {profilo.name} e salvato cifrato.")
    print("Le sessioni gia' aperte restano valide fino alla scadenza:")
    print("  per chiuderle subito,  sudo systemctl restart shinra")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
