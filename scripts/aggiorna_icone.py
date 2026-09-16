"""Rigenera l'elenco dei nomi di icona validi per la versione di lucide fissata.

## Perche' esiste

Un nome di icona sbagliato **non da' nessun errore**: lucide non trova la
chiave, scrive un avviso nella console del browser e lascia il tag vuoto. Al
suo posto c'e' un buco. Nel sorgente il nome c'e', quindi nessuna guardia che
legge il sorgente puo' accorgersene — sono serviti due nomi sbagliati in una
giornata (`house` e `wand-sparkles`) per capirlo, e in entrambi i casi il
difetto e' stato visto guardando la schermata.

La versione di lucide e' **fissata** nella pagina, quindi esiste un elenco
esatto dei nomi validi: questo script lo estrae, e
`tests/unit/test_interfaccia.py` lo usa come oracolo.

## Quando rieseguirlo

Quando cambia la versione di lucide in `web/templates/index.html`. C'e' una
guardia che fallisce se l'elenco parla di una versione diversa da quella
fissata: un elenco che parla di un'altra versione e' peggio di nessun elenco.

## Uso

    python scripts/aggiorna_icone.py

Serve la rete: scarica il bundle da jsDelivr.
"""

from __future__ import annotations

import re
import sys
import urllib.request

from shinra import percorsi

# La radice si chiede, non si calcola: sbagliare un `.parent` non solleva
# niente e si scopre dal fatto che la casa ha dimenticato tutto (issue #16).
PAGINA = percorsi.MODELLI_HTML / "index.html"
ELENCO = percorsi.RADICE / "tests" / "dati" / "icone-lucide.txt"

# I nomi che devono esserci per forza: se mancano, l'estrazione e' andata
# storta e un elenco sbagliato e' peggio di nessun elenco.
ATTESI = ("Home", "ChevronDown", "Settings", "Zap", "Sparkles", "Mic", "Workflow")

# E questi non devono esserci: sono i due nomi che hanno prodotto un buco.
SBAGLIATI = ("House", "WandSparkles")


def versione_fissata() -> str:
    trovato = re.search(r"lucide@([\d.]+)/dist/umd/lucide\.min\.js", PAGINA.read_text(encoding="utf-8"))
    if not trovato:
        raise SystemExit("Non trovo la versione di lucide fissata nella pagina.")
    return trovato.group(1)


def nomi_dal_bundle(sorgente: str) -> list[str]:
    """Le chiavi dell'oggetto delle icone, in PascalCase.

    Sono le chiavi **cosi' come lucide le cerca**: a runtime il valore di
    `data-lucide` viene convertito in PascalCase e usato per pescare qui
    dentro. Tenere il PascalCase e convertire il nome scritto nella pagina —
    invece del contrario — e' la stessa cosa che fa il browser.
    """
    return sorted(set(re.findall(r"\b([A-Z][A-Za-z0-9]*):[a-zA-Z_$][\w$]*(?=[,}])", sorgente)))


def main() -> int:
    versione = versione_fissata()
    indirizzo = f"https://cdn.jsdelivr.net/npm/lucide@{versione}/dist/umd/lucide.min.js"
    print(f"Scarico {indirizzo}")

    with urllib.request.urlopen(indirizzo, timeout=60) as risposta:
        sorgente = risposta.read().decode("utf-8")

    nomi = nomi_dal_bundle(sorgente)

    mancanti = [n for n in ATTESI if n not in nomi]
    if mancanti or len(nomi) < 800:
        raise SystemExit(f"Estrazione sospetta: {len(nomi)} nomi, mancano {mancanti}.")
    presenti = [n for n in SBAGLIATI if n in nomi]
    if presenti:
        raise SystemExit(f"«{presenti}» risultano validi: l'estrazione non e' affidabile.")

    ELENCO.parent.mkdir(parents=True, exist_ok=True)
    ELENCO.write_text(
        "# I nomi delle icone di lucide, in PascalCase, uno per riga.\n"
        "#\n"
        "# NON si scrive a mano: si rigenera con `python scripts/aggiorna_icone.py`\n"
        "# quando cambia la versione fissata in `web/templates/index.html`.\n"
        "#\n"
        "# A runtime lucide converte il valore di `data-lucide` in PascalCase e lo\n"
        "# cerca qui: un nome che non c'e' non da' errore, lascia un buco.\n"
        "#\n"
        "# Riferimento: issue #139.\n"
        f"versione: {versione}\n" + "\n".join(nomi) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"{len(nomi)} nomi scritti in {ELENCO.relative_to(percorsi.RADICE)} (lucide {versione}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
