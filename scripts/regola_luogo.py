#!/usr/bin/env python3
"""Crea una regola «quando arrivo / parto da un luogo, accendi una lampada» e dice se puo' scattare (VERIFICA-0.8.0, prova F3).

Va eseguito da una macchina che raggiunge Shinra (il server stesso, o il tuo PC), senza dipendenze oltre a Python. Il PIN lo
digiti tu quando lo chiede: non si scrive nel comando e non resta nella cronologia della shell.

    python scripts/regola_luogo.py --luogo "Casa al mare" --persona person.alessio --lampada light.cucina

Il resto e' facoltativo:

    --url http://192.168.1.10:8000   dove risponde Shinra (predefinito: http://localhost:8000)
    --utente alessio                 il profilo con cui entri (se ne hai piu' di uno)
    --evento partenza                invece di «arrivo»
    --rifiuto lock.ingresso          prova anche che una serratura su un luogo venga RIFIUTATA (deve dare errore 400)

Dopo averla creata guarda il campo «avviso» che stampa: se dice qualcosa (zona mancante in Home Assistant, persona sconosciuta)
la regola non puo' scattare finche' non lo sistemi. Poi esci dalla zona e rientra, e cerca nel registro `regola.eseguita`.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Optional


class Client:
    def __init__(self, base: str) -> None:
        if not base.startswith(("http://", "https://")):
            raise SystemExit("--url deve cominciare con http:// o https://")
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def chiedi(self, metodo: str, percorso: str, corpo: Optional[dict[str, Any]] = None) -> tuple[int, Any]:
        dati = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        richiesta = urllib.request.Request(  # noqa: S310 - lo schema e' controllato nel costruttore
            self.base + percorso, data=dati, method=metodo, headers={"Content-Type": "application/json"}
        )
        try:
            with self.opener.open(richiesta, timeout=15) as risposta:
                return risposta.status, json.loads(risposta.read() or b"null")
        except urllib.error.HTTPError as errore:
            try:
                return errore.code, json.loads(errore.read() or b"null")
            except ValueError:
                return errore.code, None


def trigger(luogo_id: str, evento: str, persona: str) -> dict[str, Any]:
    return {"tipo": "luogo", "luogo_id": luogo_id, "evento": evento, "entity_id": persona}


def azione(entita: str) -> dict[str, Any]:
    return {"tipo": "dispositivo", "entity_id": entita, "servizio": "turn_on"}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--utente", default=None, help="identificativo del profilo con cui entrare")
    ap.add_argument("--luogo", required=True, help="il nome di un luogo gia' registrato in Shinra")
    ap.add_argument(
        "--persona", required=True, help="l'entita' della persona in Home Assistant, es. person.alessio"
    )
    ap.add_argument(
        "--lampada", required=True, help="la luce da accendere, es. light.cucina (niente serrature o allarmi)"
    )
    ap.add_argument("--evento", choices=("arrivo", "partenza"), default="arrivo")
    ap.add_argument(
        "--rifiuto", default=None, metavar="LOCK", help="prova anche che questa serratura sia rifiutata"
    )
    args = ap.parse_args(argv)

    client = Client(args.url)
    pin = getpass.getpass("PIN: ")
    stato, risposta = client.chiedi("POST", "/api/auth/login", {"pin": pin, "user_id": args.utente})
    pin = ""
    if stato != 200:
        print(f"Accesso non riuscito ({stato}): {(risposta or {}).get('detail', '')}", file=sys.stderr)
        return 1

    stato, risposta = client.chiedi("GET", "/api/luoghi")
    nomi = {str(x["nome"]).casefold(): x for x in (risposta or {}).get("luoghi", [])} if stato == 200 else {}
    luogo = nomi.get(args.luogo.casefold())
    if luogo is None:
        print(
            f"Nessun luogo «{args.luogo}». Registrati: {', '.join(x['nome'] for x in nomi.values()) or 'nessuno'}",
            file=sys.stderr,
        )
        return 1

    regola = {
        "nome": f"{'Arrivo a' if args.evento == 'arrivo' else 'Partenza da'} {luogo['nome']} (prova)",
        "trigger": trigger(luogo["id"], args.evento, args.persona),
        "azioni": [azione(args.lampada)],
        "attiva": True,
    }
    stato, risposta = client.chiedi("POST", "/api/regole", regola)
    if stato != 200:
        print(
            f"La regola non e' stata creata ({stato}): {(risposta or {}).get('detail', risposta)}",
            file=sys.stderr,
        )
        return 1
    creata = risposta["regola"]
    print(f"Creata: {creata['id']} — {creata.get('nome')}")

    stato, risposta = client.chiedi("GET", "/api/regole")
    voce = next((r for r in (risposta or {}).get("regole", []) if r.get("id") == creata["id"]), None)
    if voce is not None:
        print(f"Descrizione: {voce.get('descrizione')}")
        print("Avviso: " + (voce.get("avviso") or "nessuno, puo' scattare"))

    if args.rifiuto:
        stato, risposta = client.chiedi(
            "POST",
            "/api/regole",
            {
                **regola,
                "nome": "Serratura al luogo (deve essere rifiutata)",
                "azioni": [azione(args.rifiuto)],
            },
        )
        if stato == 400:
            print(f"Serratura rifiutata come deve: {(risposta or {}).get('detail')}")
        else:
            print(
                f"ATTENZIONE: la serratura NON e' stata rifiutata (risposta {stato}). Cancella quella regola e segnalalo.",
                file=sys.stderr,
            )
            return 2

    print(
        "\nOra esci dalla zona e rientra; poi cerca nel registro una riga `regola.eseguita` con il motivo del luogo."
    )
    print(f"Per togliere la regola di prova: DELETE /api/regole/{creata['id']} (o dalla scheda Automazioni).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
