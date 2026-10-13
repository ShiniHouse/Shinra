#!/usr/bin/env python3
"""Quanto costa cercare fra N ricordi: la misura che serve all'ADR sulla ricerca vettoriale (#248).

Misura il tempo di **una richiesta di recupero** (`shinra.domain.recupero.cerca`, Python puro: il percorso di oggi) a
100, 1.000, 5.000 e 20.000 ricordi con vettori della stessa dimensione del modello configurato (768 per
`nomic-embed-text`). I vettori sono casuali: il tempo del coseno non dipende dal significato, quindi non serve Ollama.
Con `numpy` installato misura anche l'alternativa, e dice se questa build di Python puo' caricare estensioni di SQLite
(cio' che `sqlite-vec` richiede).

Non decide niente: stampa numeri, con la macchina e la data, da incollare nell'ADR. Va lanciato **sulla macchina di casa**
per valere come misura del server.

    python scripts/banco_vettori.py
    python scripts/banco_vettori.py --macchina "i5-8500T, 16 GB" --salva
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sqlite3
import statistics
import time
from datetime import date

from shinra import percorsi
from shinra.domain import recupero

DIMENSIONE = 768
GRANDEZZE = (100, 1_000, 5_000, 20_000)
RIPETIZIONI = 5


def fatti_casuali(n: int, dimensione: int, seme: int = 7) -> list[recupero.Fatto]:
    caso = random.Random(seme)  # noqa: S311 - vettori finti: non serve un generatore sicuro
    return [
        recupero.Fatto(
            f"k{i}",
            f"Il fatto numero {i} riguarda qualcosa di casa",
            vettore=[caso.uniform(-1, 1) for _ in range(dimensione)],
        )
        for i in range(n)
    ]


def tempo_python(fatti: list[recupero.Fatto], domanda: list[float]) -> float:
    prove = []
    for _ in range(RIPETIZIONI):
        inizio = time.perf_counter()
        recupero.cerca("dove si trova la caldaia", fatti, domanda)
        prove.append(time.perf_counter() - inizio)
    return statistics.median(prove)


def tempo_lettura_json(fatti: list[recupero.Fatto]) -> float:
    """Quanto costa rileggere i vettori dal database, dove stanno come JSON: oggi succede a ogni richiesta."""
    salvati = [json.dumps(list(f.vettore or [])) for f in fatti]
    prove = []
    for _ in range(RIPETIZIONI):
        inizio = time.perf_counter()
        for s in salvati:
            json.loads(s)
        prove.append(time.perf_counter() - inizio)
    return statistics.median(prove)


def tempo_numpy(fatti: list[recupero.Fatto], domanda: list[float]) -> float | None:
    try:
        import numpy as np
    except ImportError:
        return None
    matrice = np.array([f.vettore for f in fatti], dtype=np.float32)
    norme = np.linalg.norm(matrice, axis=1)
    prove = []
    for _ in range(RIPETIZIONI):
        inizio = time.perf_counter()
        q = np.array(domanda, dtype=np.float32)
        punteggi = (matrice @ q) / (norme * np.linalg.norm(q) + 1e-9)
        np.argsort(-punteggi)[: recupero.MASSIMO_FATTI]
        prove.append(time.perf_counter() - inizio)
    return statistics.median(prove)


def estensioni_sqlite() -> str:
    conn = sqlite3.connect(":memory:")
    ha = hasattr(conn, "enable_load_extension")
    if not ha:
        return f"NO: questa build di Python non ha enable_load_extension (SQLite {sqlite3.sqlite_version})"
    try:
        conn.enable_load_extension(True)
        conn.enable_load_extension(False)
        return f"si': enable_load_extension disponibile (SQLite {sqlite3.sqlite_version}); sqlite-vec da provare a parte"
    except sqlite3.NotSupportedError as errore:
        return f"NO: {errore}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--macchina", default=platform.processor() or platform.machine(), help="descrizione della macchina"
    )
    p.add_argument("--dimensione", type=int, default=DIMENSIONE)
    p.add_argument("--salva", action="store_true", help="scrive il rapporto in banco/memoria/risultati/")
    args = p.parse_args()

    caso = random.Random(1)  # noqa: S311 - vettori finti
    domanda = [caso.uniform(-1, 1) for _ in range(args.dimensione)]
    righe = [
        f"# Ricerca vettoriale — {args.macchina}",
        "",
        f"Data: {date.today().isoformat()} · Python {platform.python_version()} su {platform.system()} {platform.machine()} · "
        f"vettori da {args.dimensione} numeri, mediana di {RIPETIZIONI} richieste.",
        "",
        "| Ricordi | Coseno, Python puro (oggi) | Lettura JSON dei vettori (oggi) | numpy |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for n in GRANDEZZE:
        fatti = fatti_casuali(n, args.dimensione)
        py = tempo_python(fatti, domanda)
        js = tempo_lettura_json(fatti)
        np_ = tempo_numpy(fatti, domanda)
        righe.append(
            f"| {n:,} | {py * 1000:,.1f} ms | {js * 1000:,.1f} ms | "
            f"{'non installato' if np_ is None else f'{np_ * 1000:,.1f} ms'} |"
        )
    righe += ["", f"Estensioni di SQLite: {estensioni_sqlite()}", ""]
    testo = "\n".join(righe)
    print(testo)
    if args.salva:
        cartella = percorsi.RADICE / "banco" / "memoria" / "risultati"
        cartella.mkdir(parents=True, exist_ok=True)
        nome = f"{date.today().isoformat()}-ricerca-vettoriale.md"
        (cartella / nome).write_text(testo, encoding="utf-8", newline="\n")
        print(f"Salvato in banco/memoria/risultati/{nome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
