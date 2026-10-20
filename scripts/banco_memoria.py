#!/usr/bin/env python3
"""Il banco della memoria: misura se ricordare meglio e' vero (#269).

Come il banco del tool calling (#183): un corpus (`banco/memoria/corpus.yaml`), un comando, numeri salvati. Misura il
recupero dei ricordi di `shinra.domain.recupero`:

- **recall@k**: quante volte i ricordi che servono sono fra i primi k trovati;
- **MRR**: quanto in alto compare il primo ricordo giusto (1 = sempre in cima);
- **silenzio**: nelle domande senza risposta, quante volte non esce niente (il rumore nel prompt e' un difetto).

Senza opzioni usa **solo il testo**, senza rete: e' quello che gira in CI. Con `--embedding` calcola i vettori con il modello
di Ollama configurato, e confronta. Con `--perfetto` usa un finto modello che mette ogni domanda esattamente sui suoi
ricordi: serve a provare il banco, non la memoria.

    python scripts/banco_memoria.py
    python scripts/banco_memoria.py --embedding --etichetta server
    python scripts/banco_memoria.py --perfetto
    python scripts/banco_memoria.py --embedding --soglie --etichetta server-soglie --salva
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional, Sequence

import yaml

from shinra import percorsi
from shinra.domain import recupero

BANCO = percorsi.RADICE / "banco" / "memoria"

Vettore = Sequence[float]

# Un «adesso» fisso: la misura deve dare lo stesso numero oggi e fra un mese.
ADESSO = 1_800_000_000.0


def carica(percorso: Path = BANCO / "corpus.yaml") -> dict[str, Any]:
    return yaml.safe_load(percorso.read_text(encoding="utf-8"))


def vettori_perfetti(corpus: dict[str, Any]) -> tuple[dict[str, Vettore], dict[str, Vettore]]:
    """Un modello finto perfetto: ogni ricordo ha il suo asse, ogni domanda punta ai ricordi che le servono."""
    ids = [r["id"] for r in corpus["ricordi"]]
    ricordi = {i: [1.0 if j == k else 0.0 for j in range(len(ids))] for k, i in enumerate(ids)}
    domande: dict[str, Vettore] = {}
    for d in corpus["domande"]:
        if d["attesi"]:
            domande[d["id"]] = [1.0 if i in d["attesi"] else 0.0 for i in ids]
        else:
            # Nessuna risposta: un vettore che non somiglia a nessun ricordo.
            domande[d["id"]] = [0.0] * len(ids)
    return ricordi, domande


async def vettori_con_ollama(corpus: dict[str, Any]) -> tuple[dict[str, Vettore], dict[str, Vettore]]:
    from shinra.infra.llm import embedding

    testi = [r["testo"] for r in corpus["ricordi"]] + [d["domanda"] for d in corpus["domande"]]
    calcolati = await embedding.calcola(testi)
    if not calcolati or any(v is None for v in calcolati):
        raise RuntimeError("Ollama non ha calcolato i vettori: e' acceso e ha il modello degli embedding?")
    n = len(corpus["ricordi"])
    ricordi = {r["id"]: calcolati[i] for i, r in enumerate(corpus["ricordi"])}
    domande = {d["id"]: calcolati[n + i] for i, d in enumerate(corpus["domande"])}
    return ricordi, domande  # type: ignore[return-value]


def misura(
    corpus: dict[str, Any],
    vettori: Optional[tuple[dict[str, Vettore], dict[str, Vettore]]] = None,
    massimo: int = recupero.MASSIMO_FATTI,
    pesi: recupero.Pesi = recupero.Pesi(),
    soglia: float = recupero.SOGLIA_PUNTEGGIO,
) -> dict[str, Any]:
    """Esegue ogni domanda del corpus e riassume i numeri. Non chiama niente: i vettori, se ci sono, arrivano gia' fatti.

    Un ricordo del corpus puo' dichiarare la sua storia: `importanza` (1-5), `usi` e `giorni_fa` (da quanti giorni e' nato o
    e' servito l'ultima volta). Con i pesi a zero la storia non conta: e' il recupero di oggi.
    """
    v_ricordi, v_domande = vettori if vettori else ({}, {})
    adesso = ADESSO
    fatti = [
        recupero.Fatto(
            r["id"],
            r["testo"],
            vettore=v_ricordi.get(r["id"]),
            importanza=int(r.get("importanza", 3)),
            usi=int(r.get("usi", 0)),
            ultimo=None if r.get("giorni_fa") is None else adesso - float(r["giorni_fa"]) * 86400.0,
        )
        for r in corpus["ricordi"]
    ]

    dettagli = []
    for d in corpus["domande"]:
        trovati = recupero.cerca(
            d["domanda"],
            fatti,
            v_domande.get(d["id"]),
            massimo=massimo,
            soglia=soglia,
            pesi=pesi,
            adesso=adesso,
        )
        ids = [t.fatto.identificativo for t in trovati]
        attesi = d["attesi"]
        if attesi:
            posizioni = [ids.index(a) + 1 for a in attesi if a in ids]
            primo = min(posizioni) if posizioni else None
            dettagli.append(
                {
                    "id": d["id"],
                    "tipo": d["tipo"],
                    "domanda": d["domanda"],
                    "attesi": attesi,
                    "trovati": ids,
                    "recall_1": len(set(attesi) & set(ids[:1])) / len(attesi),
                    "recall_3": len(set(attesi) & set(ids[:3])) / len(attesi),
                    "recall_k": len(set(attesi) & set(ids)) / len(attesi),
                    "rr": 1.0 / primo if primo else 0.0,
                }
            )
        else:
            dettagli.append(
                {
                    "id": d["id"],
                    "tipo": d["tipo"],
                    "domanda": d["domanda"],
                    "attesi": [],
                    "trovati": ids,
                    "silenzio": not ids,
                }
            )

    con_risposta = [x for x in dettagli if x["attesi"]]
    senza = [x for x in dettagli if not x["attesi"]]

    def media(righe: list[dict[str, Any]], chiave: str) -> float:
        return round(sum(x[chiave] for x in righe) / len(righe), 3) if righe else 0.0

    per_tipo: dict[str, dict[str, float]] = {}
    for tipo in sorted({x["tipo"] for x in con_risposta}):
        righe = [x for x in con_risposta if x["tipo"] == tipo]
        per_tipo[tipo] = {
            "domande": len(righe),
            "recall_3": media(righe, "recall_3"),
            "mrr": media(righe, "rr"),
        }

    return {
        "con_vettori": bool(v_ricordi),
        "ricordi": len(fatti),
        "domande_con_risposta": len(con_risposta),
        "domande_senza_risposta": len(senza),
        "recall_1": media(con_risposta, "recall_1"),
        "recall_3": media(con_risposta, "recall_3"),
        "recall_k": media(con_risposta, "recall_k"),
        "mrr": media(con_risposta, "rr"),
        "silenzio": round(sum(1 for x in senza if x["silenzio"]) / len(senza), 3) if senza else 1.0,
        "per_tipo": per_tipo,
        "dettagli": dettagli,
    }


PESI_DI_PROVA = {"importanza": 0.1, "recenza": 0.1, "uso": 0.1}


def ablazione(
    corpus: dict[str, Any],
    vettori: Optional[tuple[dict[str, Vettore], dict[str, Vettore]]] = None,
    peso: float = 0.1,
) -> dict[str, dict[str, float]]:
    """Cosa porta ciascun fattore della storia: i numeri senza storia, con un fattore alla volta, con tutti."""
    prove = {
        "nessuno (oggi)": recupero.Pesi(),
        "solo importanza": recupero.Pesi(importanza=peso),
        "solo recenza": recupero.Pesi(recenza=peso),
        "solo uso": recupero.Pesi(uso=peso),
        "tutti e tre": recupero.Pesi(importanza=peso, recenza=peso, uso=peso),
    }
    fuori = {}
    for nome, pesi in prove.items():
        m = misura(corpus, vettori, pesi=pesi)
        fuori[nome] = {"recall_3": m["recall_3"], "mrr": m["mrr"], "silenzio": m["silenzio"]}
    return fuori


SOGLIE_DI_PROVA = (0.28, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65)


def scansione_soglie(
    corpus: dict[str, Any],
    vettori: Optional[tuple[dict[str, Vettore], dict[str, Vettore]]] = None,
    soglie: Sequence[float] = SOGLIE_DI_PROVA,
) -> dict[float, dict[str, float]]:
    """Come cambiano recupero e silenzio al variare della soglia di punteggio.

    Con i vettori di un modello vero il coseno fra due frasi qualunque e' raramente vicino a zero: una soglia scelta sul solo
    testo (0.28) lascia passare ricordi che non c'entrano, e le domande senza risposta non restano mai in silenzio. Questa
    tabella dice dove sta il punto in cui il rumore scende senza perdere i ricordi giusti.
    """
    fuori = {}
    for soglia in soglie:
        m = misura(corpus, vettori, soglia=soglia)
        fuori[soglia] = {
            "recall_3": m["recall_3"],
            "recall_k": m["recall_k"],
            "mrr": m["mrr"],
            "silenzio": m["silenzio"],
        }
    return fuori


def rapporto_soglie(s: dict[float, dict[str, float]]) -> str:
    righe = [
        "## Soglia di punteggio",
        "",
        "| Soglia | recall@3 | recall@8 | MRR | Silenzio |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for soglia, v in s.items():
        oggi = " (oggi)" if abs(soglia - recupero.SOGLIA_PUNTEGGIO) < 1e-9 else ""
        righe.append(
            f"| {soglia:.2f}{oggi} | {v['recall_3']:.0%} | {v['recall_k']:.0%} | {v['mrr']:.2f} | {v['silenzio']:.0%} |"
        )
    return "\n".join(righe) + "\n"


def rapporto_ablazione(a: dict[str, dict[str, float]], peso: float) -> str:
    righe = [
        f"## Ablazione della storia (peso {peso:g} per fattore)",
        "",
        "| Pesi | recall@3 | MRR | Silenzio |",
        "| :--- | ---: | ---: | ---: |",
    ]
    base = a["nessuno (oggi)"]
    for nome, v in a.items():
        delta = "" if nome.startswith("nessuno") else f" ({v['mrr'] - base['mrr']:+.2f})"
        righe.append(f"| {nome} | {v['recall_3']:.0%} | {v['mrr']:.2f}{delta} | {v['silenzio']:.0%} |")
    return "\n".join(righe) + "\n"


def rapporto(r: dict[str, Any], etichetta: str) -> str:
    righe = [
        f"# Banco della memoria — {etichetta}",
        "",
        f"Data: {date.today().isoformat()} · {'testo + vettori' if r['con_vettori'] else 'solo testo'} · "
        f"{r['ricordi']} ricordi, {r['domande_con_risposta']} domande con risposta, "
        f"{r['domande_senza_risposta']} senza.",
        "",
        "| Misura | Valore |",
        "| :--- | ---: |",
        f"| recall@1 | {r['recall_1']:.0%} |",
        f"| recall@3 | {r['recall_3']:.0%} |",
        f"| recall@{recupero.MASSIMO_FATTI} | {r['recall_k']:.0%} |",
        f"| MRR | {r['mrr']:.2f} |",
        f"| Silenzio (senza risposta, non esce niente) | {r['silenzio']:.0%} |",
        "",
        "| Tipo | Domande | recall@3 | MRR |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for tipo, v in r["per_tipo"].items():
        righe.append(f"| {tipo} | {v['domande']} | {v['recall_3']:.0%} | {v['mrr']:.2f} |")
    sbagliate = [x for x in r["dettagli"] if x["attesi"] and x["recall_k"] < 1]
    rumorose = [x for x in r["dettagli"] if not x["attesi"] and not x["silenzio"]]
    if sbagliate:
        righe += ["", "## Ricordi mancati", ""]
        righe += [
            f"- `{x['id']}` «{x['domanda']}»: attesi {x['attesi']}, trovati {x['trovati']}" for x in sbagliate
        ]
    if rumorose:
        righe += ["", "## Rumore (non c'era nulla da trovare)", ""]
        righe += [f"- `{x['id']}` «{x['domanda']}»: trovati {x['trovati']}" for x in rumorose]
    return "\n".join(righe) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--embedding", action="store_true", help="calcola i vettori con Ollama (serve acceso)")
    p.add_argument(
        "--perfetto", action="store_true", help="vettori di un finto modello perfetto (prova il banco)"
    )
    p.add_argument("--etichetta", default="solo-testo", help="nome del giro, usato nel file dei risultati")
    p.add_argument("--salva", action="store_true", help="scrive il rapporto in banco/memoria/risultati/")
    p.add_argument(
        "--ablazione", action="store_true", help="misura cosa porta ogni fattore della storia (#246)"
    )
    p.add_argument("--peso", type=float, default=0.1, help="il peso di ogni fattore nell'ablazione")
    p.add_argument(
        "--soglie",
        action="store_true",
        help="misura come cambiano recupero e silenzio al variare della soglia",
    )
    args = p.parse_args()

    corpus = carica()
    vettori = None
    if args.perfetto:
        vettori = vettori_perfetti(corpus)
        args.etichetta = "perfetto" if args.etichetta == "solo-testo" else args.etichetta
    elif args.embedding:
        try:
            vettori = asyncio.run(vettori_con_ollama(corpus))
        except RuntimeError as errore:
            print(errore, file=sys.stderr)
            return 1
        args.etichetta = "vettori" if args.etichetta == "solo-testo" else args.etichetta

    r = misura(corpus, vettori)
    testo = rapporto(r, args.etichetta)
    if args.ablazione:
        testo += "\n" + rapporto_ablazione(ablazione(corpus, vettori, args.peso), args.peso)
    if args.soglie:
        testo += "\n" + rapporto_soglie(scansione_soglie(corpus, vettori))
    print(testo)
    if args.salva:
        cartella = BANCO / "risultati"
        cartella.mkdir(exist_ok=True)
        nome = f"{date.today().isoformat()}-{args.etichetta}"
        (cartella / f"{nome}.md").write_text(testo, encoding="utf-8", newline="\n")
        (cartella / f"{nome}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"Salvato in banco/memoria/risultati/{nome}.*")
    return 0


if __name__ == "__main__":
    sys.exit(main())
