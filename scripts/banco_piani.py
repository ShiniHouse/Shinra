#!/usr/bin/env python3
"""Il banco dei piani e dei compiti a piu' passi (issue #430, ADR 0013).

La `0.9.0` si fonda su una scommessa che nessuno ha ancora misurato: che il modello locale, messo davanti a una richiesta che chiede
piu' cose («serata film: chiudi le tapparelle, spegni la luce, accendi quella del corridoio»), riesca a farle tutte. E che piu' agenti
o un piano scritto in anticipo aiutino. Piu' agenti non vuol dire piu' intelligenza: con lo stesso modello piccolo, tre chiamate costano
tre volte il tempo e possono sbagliare tre volte. Questo banco dice dove aiutano e dove no.

Tre strategie sulle stesse richieste (`banco/piani/corpus.yaml`) e lo stesso verdetto del banco del tool calling:

- `solo`    il ciclo di produzione: un modello, gli strumenti al primo giro, fino a quattro giri;
- `agenti`  il router sceglie i domini (ADR 0008) e il modello vede solo i loro strumenti;
- `piano`   **scrivi il piano, poi eseguilo**: il modello produce in una sola risposta un piano strutturato (JSON), il codice lo
            **valida** (strumento esistente, dispositivo vero, tetto di passi) e solo allora lo esegue. E' la forma che la #191 vorrebbe
            costruire: se non batte il ciclo di produzione, non vale la pena di costruirla cosi'.

- `scomposto`  il **codice** (non il modello) spezza la frase in pezzi, uno per cosa da fare; ogni pezzo va al suo agente di dominio (il router
            sceglie, il modello vede solo 2-3 strumenti), e il risultato passa dal validatore. Il modello non pianifica: fa una cosa piccola per volta.

Un caso conta piu' degli altri: `con_dipendenza` («se domani piove chiudi la tapparella») chiede di **leggere prima e decidere dopo**.
Un piano scritto tutto in anticipo non puo' farlo; il ciclo che rilegge il risultato forse si'.

    python scripts/banco_piani.py --prova
    python scripts/banco_piani.py --modelli qwen2.5:3b --strategie solo piano --limite 6
    python scripts/banco_piani.py --modelli qwen2.5:3b --ripetizioni 2 --macchina "i5-8500T, 16 GB, niente GPU"

Non parla con Home Assistant: gli strumenti rispondono con i risultati finti di `banco/mondo.yaml`.

Riferimento: issue #430, ADR 0013, #191.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import statistics
import sys
import time
from datetime import date
from typing import Any

import httpx
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # accanto a `banco_tool_calling.py`
import banco_tool_calling as bt

from shinra.domain import piani, scomposizione
from shinra.infra.lingue import schemi as lingue

BANCO_PIANI = bt.BANCO / "piani"
MAX_PASSI = 8  # il tetto dell'ADR 0013: un modello che continua ad aggiungere passi si ferma qui
STRATEGIE = ("solo", "agenti", "piano", "scomposto")

ISTRUZIONI_PIANIFICATORE = """Sei il pianificatore di una casa intelligente. Ricevi UNA richiesta e rispondi SOLO con un oggetto JSON, senza altro testo:

{"passi": [{"strumento": "<nome>", "argomenti": {"<parametro>": <valore>}}], "chiedi": null}

Regole:
- un passo per ogni cosa da fare, nell'ordine giusto; usa SOLO gli strumenti dell'elenco e SOLO i dispositivi dell'elenco;
- se la richiesta e' ambigua (non si capisce quale dispositivo) o parla di qualcosa che non c'e' in casa, non inventare: metti "passi": [] e in "chiedi" una domanda breve;
- se un passo dipende dal risultato di un altro (es. «se piove...»), pianifica SOLO il passo che serve a saperlo (leggere lo stato o il meteo): il resto si decide dopo;
- al massimo {massimo} passi."""


# ------------------------------------------------------------------ il piano: lettura e validazione (puro, senza rete)


def leggi_piano(testo: str) -> dict[str, Any] | None:
    """L'oggetto JSON del piano dalla risposta del modello, o `None` se non c'e' niente di leggibile.

    Il modello a volte lo avvolge in una recinzione di codice o ci aggiunge una frase: si cerca il primo oggetto JSON completo.
    """
    pulito = re.sub(r"```(?:json)?", "", testo or "").strip()
    inizio = pulito.find("{")
    while inizio != -1:
        profondita = 0
        for fine in range(inizio, len(pulito)):
            if pulito[fine] == "{":
                profondita += 1
            elif pulito[fine] == "}":
                profondita -= 1
                if profondita == 0:
                    try:
                        dati = json.loads(pulito[inizio : fine + 1])
                    except ValueError:
                        break
                    if isinstance(dati, dict) and isinstance(dati.get("passi"), list):
                        return dati
                    break
        inizio = pulito.find("{", inizio + 1)
    return None


def schemi_per_nome(schemi: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {s["function"]["name"]: s["function"] for s in schemi}


MOTIVI = {
    piani.NON_E_UN_OGGETTO: lambda s: f"passo {s.numero}: non e' un oggetto",
    piani.STRUMENTO_INESISTENTE: lambda s: f"passo {s.numero}: lo strumento «{s.dettaglio}» non esiste",
    piani.ARGOMENTI_NON_VALIDI: lambda s: f"passo {s.numero}: gli argomenti non sono un oggetto",
    piani.DISPOSITIVO_INESISTENTE: lambda s: f"passo {s.numero}: il dispositivo «{s.dettaglio}» non c'e' in casa",
    piani.OBBLIGATORIO_MANCANTE: lambda s: (
        f"passo {s.numero}: a «{s.dettaglio.split(':')[0]}» manca il parametro obbligatorio «{s.dettaglio.split(':')[-1]}»"
    ),
    piani.OLTRE_IL_TETTO: lambda s: f"oltre il tetto di {s.dettaglio} passi: dal {s.numero} in poi non si esegue",
}


def valida_piano(
    piano: dict[str, Any],
    strumenti: set[str],
    mondo: bt.Mondo,
    massimo: int = MAX_PASSI,
    schemi: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[bt.Chiamata], list[str]]:
    """Il controllo del codice vero (`shinra.domain.piani`) sul piano di un modello, con gli scarti detti a parole per il report.

    Senza `schemi` non si controllano i parametri obbligatori (la validazione di prima): serve ai test e ai confronti.
    """
    funzioni = {n: (schemi or {}).get(n, {}) for n in strumenti}
    accettati, scarti = piani.valida_passi(
        piano.get("passi"), funzioni, set(mondo.entita) | mondo.nomi, massimo=massimo
    )
    return [bt.Chiamata(p.nome, p.argomenti) for p in accettati], [MOTIVI[s.codice](s) for s in scarti]


def catalogo_compatto(schemi: list[dict[str, Any]]) -> str:
    """Gli strumenti, una riga ciascuno: `nome(parametro*, altro)`. Il `*` segna i parametri obbligatori. Costa poche centinaia di token."""
    righe = []
    for s in schemi:
        f = s["function"]
        parametri = (f.get("parameters") or {}).get("properties") or {}
        obbligatori = set((f.get("parameters") or {}).get("required") or [])
        elenco = ", ".join(p + ("*" if p in obbligatori else "") for p in parametri)
        righe.append(f"- {f['name']}({elenco})")
    return "\n".join(righe)


def prompt_pianificatore(mondo: bt.Mondo, schemi: list[dict[str, Any]], massimo: int = MAX_PASSI) -> str:
    return (
        ISTRUZIONI_PIANIFICATORE.replace("{massimo}", str(massimo))
        + "\n\nStrumenti (parametro* = obbligatorio):\n"
        + catalogo_compatto(schemi)
        + "\n\nDispositivi (usa l'entity_id):\n"
        + mondo.riassunto_alias()
    )


# ------------------------------------------------------------------ la strategia «piano»


async def chiedi_il_piano(
    cliente: httpx.AsyncClient,
    url: str,
    modello: str,
    prompt: str,
    frase: str,
    num_ctx: int,
    temperatura: float,
) -> dict[str, Any]:
    payload = {
        "model": modello,
        "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": frase}],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": temperatura, "num_ctx": num_ctx, "num_predict": 500, "top_p": 0.9},
    }
    risposta = await cliente.post(f"{url.rstrip('/')}/api/chat", json=payload, timeout=bt.TEMPI.richiesta)
    risposta.raise_for_status()
    return risposta.json()


async def esegui_piano(
    cliente: httpx.AsyncClient,
    url: str,
    modello: str,
    voce: dict[str, Any],
    mondo: bt.Mondo,
    schemi: list[dict[str, Any]],
    strumenti: set[str],
    num_ctx: int,
    temperatura: float,
) -> dict[str, Any]:
    """Una richiesta con «piano, poi esecuzione». Ritorna i fatti misurati, nella stessa forma di `esegui_voce`."""
    esito: dict[str, Any] = {"giri": 1, "errore": "", "piano_leggibile": False, "scarti": [], "chiede": None}
    inizio = time.monotonic()
    prompt = prompt_pianificatore(mondo, schemi)
    esito["prompt_token"] = len(prompt) // 4
    chiamate: list[bt.Chiamata] = []
    try:
        dati = await chiedi_il_piano(cliente, url, modello, prompt, voce["frase"], num_ctx, temperatura)
        piano = leggi_piano((dati.get("message") or {}).get("content", ""))
        if piano is not None:
            esito["piano_leggibile"] = True
            esito["chiede"] = piano.get("chiedi")
            chiamate, esito["scarti"] = valida_piano(piano, strumenti, mondo, schemi=schemi_per_nome(schemi))
    except (httpx.HTTPError, ValueError) as errore:
        esito["errore"] = f"{type(errore).__name__}: {errore}"
    esito["secondi"] = round(time.monotonic() - inizio, 2)
    esito["chiamate"] = [{"nome": c.nome, "args": c.args} for c in chiamate]
    if esito["errore"].startswith("ReadTimeout"):
        await asyncio.sleep(bt.TEMPI.dopo_timeout)
    return esito


# ------------------------------------------------------------------ la strategia «scomposto»

# Lo spezzatore e' del codice vero: `shinra.domain.scomposizione` (separatori, pronomi e nomi stanno nel file della lingua, `agente.scomposizione`).


async def esegui_scomposto(
    cliente: httpx.AsyncClient,
    url: str,
    modello: str,
    voce: dict[str, Any],
    mondo: bt.Mondo,
    prompt: str,
    schemi_tutti: list[dict[str, Any]],
    strumenti: set[str],
    num_ctx: int,
    temperatura: float,
    parole: tuple[str, ...],
) -> dict[str, Any]:
    """Una richiesta spezzata dal codice: ogni pezzo passa dal ciclo con il router per dominio, i risultati si uniscono e si validano."""
    esito: dict[str, Any] = {"giri": 0, "errore": "", "pezzi": [], "scarti": []}
    inizio = time.monotonic()
    pezzi = scomposizione.spezza(voce["frase"], parole, lingue("it").scomposizione)
    esito["pezzi"] = pezzi
    chiamate: list[bt.Chiamata] = []
    for pezzo in pezzi:
        parziale = await bt.esegui_voce(
            cliente,
            url,
            modello,
            {**voce, "frase": pezzo},
            mondo,
            prompt,
            schemi_tutti,
            strumenti,
            num_ctx,
            temperatura,
            parole,
            False,
            agenti=True,
            contesto=bt.contesto_di_richiesta(mondo),
        )
        esito["giri"] += parziale.get("giri", 0)
        if parziale.get("errore") and not esito["errore"]:
            esito["errore"] = parziale["errore"]
        chiamate.extend(bt.Chiamata(c["nome"], c["args"]) for c in parziale.get("chiamate", []))
    # Lo stesso validatore del piano: strumento esistente, dispositivo vero, tetto di passi. E niente doppioni fra pezzi.
    visti: set[str] = set()
    uniche = []
    for c in chiamate:
        chiave = json.dumps([c.nome, c.args], sort_keys=True, ensure_ascii=False)
        if chiave not in visti:
            visti.add(chiave)
            uniche.append(c)
    accettate, esito["scarti"] = valida_piano(
        {"passi": [{"strumento": c.nome, "argomenti": c.args} for c in uniche]},
        strumenti,
        mondo,
        schemi=schemi_per_nome(schemi_tutti),
    )
    esito["secondi"] = round(time.monotonic() - inizio, 2)
    esito["chiamate"] = [{"nome": c.nome, "args": c.args} for c in accettate]
    return esito


# ------------------------------------------------------------------ verdetto e report


def verdetto(
    voce: dict[str, Any], esito: dict[str, Any], mondo: bt.Mondo, strumenti: set[str]
) -> dict[str, Any]:
    """Una richiesta e' riuscita se gli strumenti sono quelli giusti, gli argomenti anche, e non c'e' niente di inventato."""
    chiamate = [bt.Chiamata(c["nome"], c["args"]) for c in esito.get("chiamate", [])]
    v = bt.valuta(voce, chiamate, mondo.entita | mondo.nomi, strumenti, mondo.alias)
    v["riuscita"] = bool(
        not esito.get("errore")
        and v["ok_strumento"]
        and v["ok_argomenti"] is not False
        and not v["inventate"]
        and not v["inesistenti"]
    )
    return v


def riepilogo(righe: list[dict[str, Any]]) -> dict[str, Any]:
    """I numeri di una strategia su un insieme di richieste: riuscite, tempo, piani illeggibili, passi scartati."""
    n = len(righe)
    secondi = [r["esito"]["secondi"] for r in righe if "secondi" in r["esito"]]
    return {
        "richieste": n,
        "riuscite": sum(1 for r in righe if r["verdetto"]["riuscita"]),
        "errori": sum(1 for r in righe if r["esito"].get("errore")),
        "inventate": sum(len(r["verdetto"]["inventate"]) for r in righe),
        "piani_illeggibili": sum(
            1 for r in righe if "piano_leggibile" in r["esito"] and not r["esito"]["piano_leggibile"]
        ),
        "passi_scartati": sum(len(r["esito"].get("scarti") or []) for r in righe),
        "mediana_secondi": round(statistics.median(secondi), 1) if secondi else None,
    }


def percentuale(parte: int, tutto: int) -> str:
    return f"{100 * parte / tutto:.0f}%" if tutto else "—"


def markdown(intestazione: dict[str, Any], risultati: list[dict[str, Any]]) -> str:
    strategie = [s for s in STRATEGIE if any(r["strategia"] == s for r in risultati)]
    categorie = sorted(
        {r["voce"]["categoria"] for r in risultati}, key=lambda c: (c in ("ambigua", "sconosciuta"), c)
    )
    out = [f"# Banco dei piani — {intestazione['data']}", ""]
    out.append(
        f"Modello: `{intestazione['modello']}` — macchina: {intestazione['macchina']} — `num_ctx` {intestazione['num_ctx']}."
    )
    out.append(
        f"Richieste: {intestazione['richieste']} richieste, {intestazione['ripetizioni']} ripetizioni."
    )
    out += ["", "## Richieste riuscite, per categoria", "", "| Categoria | " + " | ".join(strategie) + " |"]
    out.append("| :-- | " + " | ".join("--:" for _ in strategie) + " |")
    for c in categorie:
        celle = []
        for s in strategie:
            r = [x for x in risultati if x["strategia"] == s and x["voce"]["categoria"] == c]
            ok = sum(1 for x in r if x["verdetto"]["riuscita"])
            celle.append(f"{ok}/{len(r)} ({percentuale(ok, len(r))})")
        out.append(f"| {c} | " + " | ".join(celle) + " |")
    tot = {s: riepilogo([x for x in risultati if x["strategia"] == s]) for s in strategie}
    out.append(
        "| **tutte** | "
        + " | ".join(
            f"**{tot[s]['riuscite']}/{tot[s]['richieste']} ({percentuale(tot[s]['riuscite'], tot[s]['richieste'])})**"
            for s in strategie
        )
        + " |"
    )
    out += [
        "",
        "## Costo e difetti",
        "",
        "| | " + " | ".join(strategie) + " |",
        "| :-- | " + " | ".join("--:" for _ in strategie) + " |",
    ]
    for etichetta, chiave in (
        ("Mediana (s)", "mediana_secondi"),
        ("Dispositivi inventati", "inventate"),
        ("Piani illeggibili", "piani_illeggibili"),
        ("Passi scartati dal codice", "passi_scartati"),
        ("Errori di rete/modello", "errori"),
    ):
        out.append(
            f"| {etichetta} | "
            + " | ".join(str(tot[s][chiave]) if tot[s][chiave] is not None else "—" for s in strategie)
            + " |"
        )
    out += ["", "## Dove sbaglia", ""]
    for riga in risultati:
        if not riga["verdetto"]["riuscita"]:
            visti = ", ".join(c["nome"] for c in riga["esito"].get("chiamate", [])) or "nessuno strumento"
            out.append(f"- `{riga['strategia']}` · {riga['voce']['id']}: «{riga['voce']['frase']}» → {visti}")
    return "\n".join(out) + "\n"


def carica_corpus(solo: str | None = None, limite: int | None = None) -> list[dict[str, Any]]:
    voci = yaml.safe_load((BANCO_PIANI / "corpus.yaml").read_text(encoding="utf-8"))
    if solo:
        voci = [v for v in voci if v["categoria"] == solo]
    return voci[:limite] if limite else voci


# ------------------------------------------------------------------ il giro


async def principale(args: argparse.Namespace) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from shinra.infra.lingue import schemi as lingue
    from shinra.skills.registry import TOOLS_SCHEMA

    mondo = bt.Mondo.carica()
    strumenti = {s["function"]["name"] for s in TOOLS_SCHEMA}
    corpus = carica_corpus(args.solo, args.limite)
    prompt_p = prompt_pianificatore(mondo, TOOLS_SCHEMA)
    print(
        f"Richieste: {len(corpus)} — strumenti: {len(strumenti)} — prompt del pianificatore ~{len(prompt_p) // 4} token"
    )
    if args.prova:
        print(
            "Solo la prova: il corpus e' leggibile e il prompt si costruisce. Nessuna richiesta al modello."
        )
        return 0

    modello = args.modelli[0]
    num_ctx = args.num_ctx
    prompt = bt.prompt_di_sistema(mondo)
    parole = lingue("it").parole_azione
    risultati: list[dict[str, Any]] = []
    async with httpx.AsyncClient() as cliente:
        if not await bt.aspetta_ollama(cliente, args.url, 15):
            print(f"Ollama non risponde su {args.url}", file=sys.stderr)
            return 1
        print(f"Scaldo il modello {modello} (num_ctx {num_ctx})...")
        await bt.scalda(cliente, args.url, modello, num_ctx)
        for giro in range(args.ripetizioni):
            for voce in corpus:
                for strategia in args.strategie:
                    if strategia == "scomposto":
                        esito = await esegui_scomposto(
                            cliente,
                            args.url,
                            modello,
                            voce,
                            mondo,
                            prompt,
                            TOOLS_SCHEMA,
                            strumenti,
                            num_ctx,
                            args.temperatura,
                            parole,
                        )
                    elif strategia == "piano":
                        esito = await esegui_piano(
                            cliente,
                            args.url,
                            modello,
                            voce,
                            mondo,
                            TOOLS_SCHEMA,
                            strumenti,
                            num_ctx,
                            args.temperatura,
                        )
                    else:
                        esito = await bt.esegui_voce(
                            cliente,
                            args.url,
                            modello,
                            voce,
                            mondo,
                            prompt,
                            TOOLS_SCHEMA,
                            strumenti,
                            num_ctx,
                            args.temperatura,
                            parole,
                            False,
                            agenti=(strategia == "agenti"),
                            contesto=bt.contesto_di_richiesta(mondo),
                        )
                    v = verdetto(voce, esito, mondo, strumenti)
                    risultati.append(
                        {"giro": giro, "strategia": strategia, "voce": voce, "esito": esito, "verdetto": v}
                    )
                    segno = "ok " if v["riuscita"] else "NO "
                    print(f"  {segno}{strategia:6} {voce['id']:24} {esito.get('secondi', '?'):>6}s")

    intestazione = {
        "data": date.today().isoformat(),
        "modello": modello,
        "macchina": args.macchina,
        "num_ctx": num_ctx,
        "richieste": len(corpus),
        "ripetizioni": args.ripetizioni,
    }
    testo = markdown(intestazione, risultati)
    print("\n" + testo)
    if not args.senza_file:
        cartella = BANCO_PIANI / "risultati"
        cartella.mkdir(parents=True, exist_ok=True)
        base = f"{intestazione['data']}-{re.sub(r'[^a-z0-9]+', '-', args.macchina.lower()).strip('-') or 'macchina'}"
        (cartella / f"{base}.md").write_text(testo, encoding="utf-8", newline="\n")
        (cartella / f"{base}.json").write_text(
            json.dumps({"intestazione": intestazione, "risultati": risultati}, ensure_ascii=False, indent=1)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Scritto in {cartella / base}.md e .json")
    return 0


def analizza() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:11434")
    p.add_argument("--modelli", nargs="+", default=["qwen2.5:3b"])
    p.add_argument("--strategie", nargs="+", choices=STRATEGIE, default=list(STRATEGIE))
    p.add_argument("--num-ctx", dest="num_ctx", type=int, default=4096)
    p.add_argument("--temperatura", type=float, default=0.1)
    p.add_argument("--ripetizioni", type=int, default=1)
    p.add_argument("--limite", type=int, default=None, help="solo le prime N richieste")
    p.add_argument("--solo", default=None, help="solo una categoria")
    p.add_argument("--macchina", default="portatile")
    p.add_argument(
        "--senza-file", action="store_true", help="non scrivere i risultati in banco/piani/risultati"
    )
    p.add_argument(
        "--prova", action="store_true", help="solo il controllo del corpus e del prompt, senza il modello"
    )
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(principale(analizza())))
