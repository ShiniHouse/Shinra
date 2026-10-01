#!/usr/bin/env python3
"""Genera docs/API.md dalle rotte vere dell'applicazione.

Un riferimento delle API scritto a mano invecchia il giorno dopo: qualcuno
aggiunge una rotta e non lo apre. Questo lo legge da `app.routes`, quindi
elenca **quello che il server risponde**, e un test (`test_documentazione_api`)
fallisce se il file nel repository non coincide con l'output di questo script.

    python scripts/genera_api.py            # riscrive docs/API.md
    python scripts/genera_api.py --controlla  # esce con 1 se e' vecchio

Per ogni rotta dice chi la puo' chiamare: nessuno (pubblica), chiunque abbia
una sessione, una persona con un permesso preciso, o l'amministratore. Lo
legge dalle dipendenze della rotta, non da un elenco scritto a parte.

Riferimento: issue #38.
"""

from __future__ import annotations

import inspect
import re
import sys

from shinra import percorsi

BASE = percorsi.RADICE
USCITA = BASE / "docs" / "API.md"

METODI = ("GET", "POST", "PUT", "PATCH", "DELETE")


def _dipendenze(dipendente) -> list:
    """Tutte le funzioni da cui dipende una rotta, anche annidate."""
    trovate = []
    for sotto in dipendente.dependencies:
        trovate.append(sotto.call)
        trovate.extend(_dipendenze(sotto))
    return trovate


def _chi(route) -> str:
    """Chi puo' chiamare la rotta, letto dalle sue dipendenze."""
    chiamate = _dipendenze(route.dependant)
    nomi = [getattr(c, "__name__", "") for c in chiamate]

    permessi = sorted({getattr(c, "permesso", "") for c in chiamate if getattr(c, "permesso", "")})
    if permessi:
        return "permesso `" + "`, `".join(permessi) + "`"
    if "richiedi_amministratore" in nomi:
        return "amministratore"
    if "richiedi_autenticazione" in nomi:
        return "sessione aperta"
    return "pubblica"


def _riassunto(route) -> str:
    """La prima frase della documentazione della funzione."""
    testo = inspect.getdoc(route.endpoint) or route.summary or ""
    prima = re.split(r"\n\s*\n", testo.strip())[0] if testo.strip() else ""
    prima = " ".join(prima.split())
    return prima.replace("|", "\\|")


def _gruppo(percorso: str) -> str:
    pezzi = [p for p in percorso.split("/") if p]
    if not pezzi:
        return "pagine"
    if pezzi[0] == "api" and len(pezzi) > 1:
        return pezzi[1]
    return pezzi[0]


def _appiattisci(rotte):
    """Le rotte vere, anche quelle dei router inclusi.

    Le versioni recenti di FastAPI non copiano piu' le rotte di un router in
    `app.routes`: ci mettono un involucro (`_IncludedRouter`) che punta al
    router originale. Si scende li' dentro. Se l'involucro cambiasse forma, il
    test sul numero minimo di rotte lo dice invece di produrre un file quasi
    vuoto.
    """
    for rotta in rotte:
        interno = getattr(rotta, "original_router", None)
        if interno is not None:
            yield from _appiattisci(interno.routes)
        else:
            yield rotta


def righe() -> list[tuple[str, str, str, str, str]]:
    """(gruppo, metodo, percorso, chi, riassunto) per ogni rotta, in ordine stabile."""
    from fastapi.routing import APIRoute
    from starlette.routing import WebSocketRoute

    from shinra.api.app import app

    trovate = []
    for route in _appiattisci(app.routes):
        if isinstance(route, APIRoute):
            for metodo in sorted(route.methods & set(METODI)):
                trovate.append((_gruppo(route.path), metodo, route.path, _chi(route), _riassunto(route)))
        elif isinstance(route, WebSocketRoute):
            trovate.append((_gruppo(route.path), "WS", route.path, "sessione aperta", _riassunto_ws(route)))
    return sorted(trovate, key=lambda r: (r[0], r[2], METODI.index(r[1]) if r[1] in METODI else 9))


def _riassunto_ws(route) -> str:
    testo = inspect.getdoc(route.endpoint) or ""
    prima = re.split(r"\n\s*\n", testo.strip())[0] if testo.strip() else ""
    return " ".join(prima.split()).replace("|", "\\|")


INTESTAZIONE = """# Riferimento delle API

> **Questo file e' generato.** Non si modifica a mano: lo riscrive
> `python scripts/genera_api.py` leggendo le rotte vere, e un test
> (`tests/unit/test_documentazione_api.py`) fallisce se resta indietro.
> Il testo di ogni riga e' la prima frase della documentazione della funzione
> che risponde: se una riga e' vuota o poco chiara, si corregge *li*.

Tutte le rotte stanno sotto `/api`, tranne le pagine, i file statici e il
canale degli eventi. Le risposte sono JSON.

## Chi puo' chiamare cosa

| Colonna «Chi» | Significato |
| :--- | :--- |
| pubblica | Nessuna credenziale. E' una scelta dichiarata: l'accesso stesso, lo stato del servizio, e l'endpoint Alexa, che si difende con la firma Amazon |
| sessione aperta | Qualunque persona entrata in casa (PIN, passkey o dispositivo fidato) |
| permesso `x` | Una sessione **il cui ruolo ha il permesso** `x` ([ADR 0004](adr/0004-identita-ruoli-e-permessi.md)). Senza, la risposta e' `403` con il nome del permesso che manca |
| amministratore | Solo il ruolo amministratore |

Senza sessione, le rotte protette rispondono `401`. L'autenticazione e' attiva
per difetto: una rotta e' pubblica solo se lo dice il codice.

## Come si autentica un client

1. `POST /api/auth/login` con `{"user_id": "...", "pin": "..."}`. Risponde con
   `{"success": true, "utente": {...}}` e imposta il cookie di sessione
   `shinra_sessione` (`HttpOnly`: non leggibile da JavaScript). Dopo cinque PIN
   errati in cinque minuti risponde `429`.
2. Il browser rimanda il cookie da solo. Il token **non** viene restituito nel
   corpo e non si accetta in un'intestazione: un client esterno tiene un cookie
   jar (`curl -c cookie.txt ...` al login, poi `curl -b cookie.txt ...`). Fino
   alla 0.5.x c'era anche l'intestazione `x-shinra-auth`: l'`HttpOnly` non
   serviva a niente se lo stesso token era leggibile da uno script.
3. La sessione dura trenta giorni. Una sessione scaduta risponde `401`; la
   dashboard lo dice e riporta all'accesso invece di ritentare.
4. `POST /api/auth/logout` la chiude.

I dettagli del flusso con le passkey e dei dispositivi fidati stanno nell'ADR
0004. Lo schema completo di richieste e risposte di ogni rotta lo serve
l'applicazione stessa, quando e' in funzione, su `/docs` (Swagger) e
`/openapi.json`.
"""


def genera() -> str:
    per_gruppo: dict[str, list] = {}
    for gruppo, metodo, percorso, chi, riassunto in righe():
        per_gruppo.setdefault(gruppo, []).append((metodo, percorso, chi, riassunto))

    pezzi = [INTESTAZIONE]
    totale = sum(len(v) for v in per_gruppo.values())
    pezzi.append(f"## Le rotte ({totale})\n")
    for gruppo in sorted(per_gruppo):
        pezzi.append(f"### `{gruppo}`\n")
        pezzi.append("| Metodo | Percorso | Chi | Cosa fa |")
        pezzi.append("| :--- | :--- | :--- | :--- |")
        for metodo, percorso, chi, riassunto in per_gruppo[gruppo]:
            pezzi.append(f"| {metodo} | `{percorso}` | {chi} | {riassunto or '—'} |")
        pezzi.append("")
    return "\n".join(pezzi).rstrip("\n") + "\n"


def main() -> int:
    nuovo = genera()
    if "--controlla" in sys.argv:
        attuale = USCITA.read_text(encoding="utf-8") if USCITA.exists() else ""
        if attuale != nuovo:
            print("docs/API.md e' vecchio: esegui  python scripts/genera_api.py", file=sys.stderr)
            return 1
        return 0
    USCITA.write_text(nuovo, encoding="utf-8", newline="\n")
    print(f"scritto {USCITA.relative_to(BASE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
