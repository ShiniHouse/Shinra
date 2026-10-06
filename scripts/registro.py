#!/usr/bin/env python3
"""Legge il registro delle azioni dal server, senza passare dalla dashboard.

Il registro dice **chi ha fatto cosa in casa, e com'e' andata**: una regola che e' scattata (o non e' scattata, e
perche'), uno strumento chiamato dal modello, una conferma chiesta e data. Esiste come API per gli amministratori, ma
la dashboard non lo mostra: per sapere se una cosa e' successa davvero, e' il modo piu' rapido.

Da eseguire sul server, con l'ambiente virtuale del progetto. Non scrive niente e non richiede di fermare il servizio:

    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py                       # le ultime due ore
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --ore 24 --azione regola
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --azione conferma --ore 1
    sudo /opt/Shinra/.venv/bin/python /opt/Shinra/scripts/registro.py --esito errore

`--azione` cerca una **parte** del nome (`regola` trova `regola.eseguita` e `regola.saltata`). Le voci escono dalla piu'
vecchia alla piu' recente, cosi' si legge come e' andata la storia.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

# Gli script si lanciano dalla copia di lavoro, dove il pacchetto puo' non essere installato: senza questo,
# `import shinra` fallirebbe. E' l'unico punto che calcola un percorso da solo; il resto lo chiede a `shinra.percorsi`.
_SORGENTI = Path(__file__).resolve().parent.parent / "src"
if _SORGENTI.is_dir():
    sys.path.insert(0, str(_SORGENTI))


def _in_ora_locale(momento: str) -> str:
    try:
        return datetime.fromisoformat(momento).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return momento


def riga(voce: dict[str, Any]) -> str:
    """Una voce in una riga: quando, cosa, esito, chi e da dove, e i dettagli in forma compatta."""
    chi = " ".join(
        parte
        for parte in (
            f"attore={voce['attore']}" if voce.get("attore") else "",
            f"canale={voce['canale']}" if voce.get("canale") else "",
        )
        if parte
    )
    dettagli = json.dumps(voce.get("dettagli") or {}, ensure_ascii=False, separators=(",", ":"))
    pezzi = [
        _in_ora_locale(voce["momento"]),
        f"{voce['azione']:<22}",
        f"{voce.get('esito') or '':<10}",
        chi,
        dettagli,
    ]
    return "  ".join(p for p in pezzi if p.strip())


def leggi(ore: int, azione: Optional[str], esito: Optional[str], limite: int) -> list[dict[str, Any]]:
    from shinra.services import registro

    dal = datetime.now(timezone.utc) - timedelta(hours=ore)
    # Il filtro sul nome e' per sottostringa: il servizio filtra per uguaglianza, quindi si filtra qui sopra.
    voci = registro.voci(limite=1000, esito=esito, dal=dal)
    if azione:
        voci = [v for v in voci if azione in v["azione"]]
    return list(reversed(voci[:limite]))


def main(argv: Optional[Iterable[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ore", type=int, default=2, help="quante ore indietro guardare (predefinito 2)")
    p.add_argument("--azione", help="una parte del nome dell'azione (es. regola, conferma, tool.)")
    p.add_argument("--esito", help="solo questo esito (es. ok, errore, saltata)")
    p.add_argument(
        "--limite", type=int, default=50, help="al massimo quante voci (le piu' recenti, predefinito 50)"
    )
    args = p.parse_args(list(argv) if argv is not None else None)

    # I percorsi dei dati sono relativi alla copia di lavoro, come per il servizio. Si torna dov'eravamo: chi
    # importa questo modulo (i test) non deve ritrovarsi con la cartella di lavoro cambiata.
    from shinra import percorsi

    prima = os.getcwd()
    os.chdir(percorsi.RADICE)
    try:
        voci = leggi(args.ore, args.azione, args.esito, args.limite)
    finally:
        os.chdir(prima)
    if not voci:
        print("Nessuna voce nel registro per questi filtri.", file=sys.stderr)
        return 1
    for voce in voci:
        print(riga(voce))
    return 0


if __name__ == "__main__":
    sys.exit(main())
