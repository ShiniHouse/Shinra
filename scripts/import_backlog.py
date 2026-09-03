#!/usr/bin/env python3
"""Importa il backlog di docs/backlog/ su GitHub come milestone, etichette e issue.

Richiede GitHub CLI autenticato:  gh auth status

Lo script e' idempotente: riconosce per titolo le issue gia' presenti e non le
duplica. Usare --dry-run per vedere cosa farebbe senza scrivere nulla.

    python scripts/import_backlog.py --dry-run
    python scripts/import_backlog.py
    python scripts/import_backlog.py --milestone v0.1.0
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
BACKLOG = BASE / "docs" / "backlog"

MILESTONE = {
    "v0.1.0": "Impianto chiuso — difetti bloccanti risolti, superficie di attacco chiusa, segreti fuori da git",
    "v0.2.0": "Fondamenta — scheduler persistente, database, memoria per sessione, layout a pacchetto, test",
    "v0.3.0": "Copertura — eventi Home Assistant in tempo reale e i domini oggi scoperti",
    "v0.4.0": "Proattivita' — motore di regole, notifiche push, voce interamente locale",
    "v0.5.0": "Prodotto — frontend modulare, backup, internazionalizzazione, distribuzione",
}

LABEL = {
    "tipo: difetto": ("d73a4a", "Qualcosa non funziona"),
    "tipo: attivita'": ("0e8a16", "Lavoro pianificato in roadmap"),
    "tipo: funzione": ("a2eeef", "Capacita' nuova"),
    "area: sicurezza": ("b60205", "Autenticazione, segreti, superficie di attacco"),
    "area: core": ("1d76db", "Agente, tool, motori"),
    "area: infra": ("5319e7", "Database, scheduler, packaging, CI"),
    "area: frontend": ("fbca04", "Interfaccia web e PWA"),
    "area: integrazioni": ("006b75", "Alexa, Home Assistant, canali"),
    "area: documentazione": ("c5def5", "Documenti e guide"),
    "gravita': critica": ("8B0000", "Blocca l'uso o espone la casa"),
    "gravita': alta": ("e99695", "Compromette una funzione principale"),
    "gravita': media": ("fef2c0", "Degrado o rischio contenuto"),
    "stato: da valutare": ("ededed", "Non ancora accettata in roadmap"),
    "buona prima issue": ("7057ff", "Adatta a chi si avvicina al progetto"),
}


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, check=check)


def parse(path: Path) -> dict:
    """Estrae l'intestazione YAML minimale e il corpo. Nessuna dipendenza esterna."""
    testo = path.read_text(encoding="utf-8")
    if not testo.startswith("---"):
        raise ValueError(f"{path.name}: manca l'intestazione")
    _, testa, corpo = testo.split("---", 2)

    meta: dict = {}
    for riga in testa.strip().splitlines():
        if ":" not in riga:
            continue
        chiave, valore = riga.split(":", 1)
        chiave, valore = chiave.strip(), valore.strip()
        if valore.startswith("["):
            meta[chiave] = [v.strip().strip('"') for v in valore[1:-1].split(",") if v.strip()]
        else:
            meta[chiave] = valore.strip('"')

    for obbligatorio in ("title", "milestone"):
        if obbligatorio not in meta:
            raise ValueError(f"{path.name}: manca il campo '{obbligatorio}'")

    meta["body"] = corpo.strip()
    meta["file"] = str(path.relative_to(BASE))
    return meta


def assicura_etichette(dry: bool) -> None:
    esistenti = {
        e["name"] for e in json.loads(run(["gh", "label", "list", "--json", "name", "--limit", "200"]).stdout)
    }
    for nome, (colore, descrizione) in LABEL.items():
        if nome in esistenti:
            continue
        print(f"  + etichetta  {nome}")
        if not dry:
            run(["gh", "label", "create", nome, "--color", colore, "--description", descrizione], check=False)


def assicura_milestone(dry: bool) -> None:
    res = run(["gh", "api", "repos/{owner}/{repo}/milestones?state=all", "--jq", ".[].title"], check=False)
    esistenti = set(res.stdout.split()) if res.returncode == 0 else set()
    for titolo, descrizione in MILESTONE.items():
        if titolo in esistenti:
            continue
        print(f"  + milestone  {titolo}")
        if not dry:
            run(
                [
                    "gh",
                    "api",
                    "repos/{owner}/{repo}/milestones",
                    "-f",
                    f"title={titolo}",
                    "-f",
                    f"description={descrizione}",
                ],
                check=False,
            )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="mostra cosa farebbe senza scrivere")
    p.add_argument("--milestone", help="importa solo questa milestone (es. v0.1.0)")
    args = p.parse_args()

    if run(["gh", "auth", "status"], check=False).returncode != 0:
        print("GitHub CLI non autenticato. Esegui prima:  gh auth login", file=sys.stderr)
        return 1

    if not BACKLOG.is_dir():
        print(f"Cartella non trovata: {BACKLOG}", file=sys.stderr)
        return 1

    print("Etichette e milestone")
    assicura_etichette(args.dry_run)
    assicura_milestone(args.dry_run)

    aperte = json.loads(
        run(["gh", "issue", "list", "--state", "all", "--limit", "500", "--json", "title"]).stdout
    )
    titoli_esistenti = {i["title"] for i in aperte}

    file = sorted(f for f in BACKLOG.rglob("*.md") if f.name != "README.md")
    creati = saltati = 0

    print("\nIssue")
    for percorso in file:
        try:
            meta = parse(percorso)
        except ValueError as e:
            print(f"  ! {e}", file=sys.stderr)
            continue

        if args.milestone and meta["milestone"] != args.milestone:
            continue
        if meta["title"] in titoli_esistenti:
            print(f"  = gia' presente  {meta['title']}")
            saltati += 1
            continue

        corpo = f"{meta['body']}\n\n---\n<sub>Importata da `{meta['file']}`</sub>"
        cmd = [
            "gh",
            "issue",
            "create",
            "--title",
            meta["title"],
            "--body",
            corpo,
            "--milestone",
            meta["milestone"],
        ]
        for etichetta in meta.get("labels", []):
            cmd += ["--label", etichetta]

        print(f"  + {meta['title']}")
        if not args.dry_run:
            res = run(cmd, check=False)
            if res.returncode != 0:
                print(f"    ! errore: {res.stderr.strip()}", file=sys.stderr)
                continue
        creati += 1

    modo = " (simulazione, nulla e' stato scritto)" if args.dry_run else ""
    print(f"\nCreate {creati}, gia' presenti {saltati}{modo}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
