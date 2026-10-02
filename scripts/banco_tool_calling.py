#!/usr/bin/env python3
"""Il banco di prova del tool calling (issue #183).

La `0.6.0` poggia su una scommessa: che il modello locale scelga lo strumento
giusto e gli passi gli argomenti giusti. Questo script la misura, con le stesse
richieste, lo stesso prompt e lo stesso ciclo che usa l'agente in produzione, su
quello che hai davvero: il modello e la macchina di casa.

    python scripts/banco_tool_calling.py --prova
    python scripts/banco_tool_calling.py --modelli qwen2.5:3b --limite 10
    python scripts/banco_tool_calling.py --modelli qwen2.5:3b qwen2.5:7b \\
        --num-ctx produzione 4096 --ripetizioni 2 --macchina "i5-8500T, 16 GB, niente GPU"

Cosa riproduce dell'agente, e perche' conta:

- **il prompt di sistema** e il riassunto della casa (gli alias, le modalita');
- **gli strumenti solo se la frase li chiama** (`parole_azione`), e **solo al primo
  giro**: dopo aver chiamato uno strumento il modello rilegge il risultato senza
  strumenti. Una richiesta a piu' passaggi funziona se il modello chiama piu'
  strumenti *nella stessa risposta*;
- **`num_ctx` di produzione**: `1024` con la configurazione predefinita. E' il
  parametro che il banco varia di piu', perche' il prompt piu' gli schemi dei 36
  strumenti pesano molto di piu' (vedi `--prova`): se il contesto e' piu' piccolo del
  prompt, Ollama taglia, e il modello sceglie fra strumenti che non ha visto.

Non parla con Home Assistant: gli strumenti rispondono con i risultati finti di
`banco/mondo.yaml`. Un `entity_id` che il modello inventa si conta a parte.

Riferimento: issue #183, ADR 0008 (#184).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import yaml

from shinra import percorsi

BANCO = percorsi.RADICE / "banco"
MAX_GIRI = 4  # come `max_tool_iterations` dell'agente

# Gli strumenti che *comandano* qualcosa: per le frasi ambigue, chiamarne uno e' indovinare.
PREFISSI_COMANDO = ("control_device", "activate_", "comanda_")

# I criteri che proponiamo per dire «questo modello regge». Sono una proposta da
# discutere nell'ADR 0008, non una verita': i numeri veri li da' questo banco.
CRITERI = {
    "strumento_giusto": 85.0,
    "argomenti_giusti": 75.0,
    "inventate": 1,
    "cicli": 0,
    "mediana_secondi": 8.0,
}


# --------------------------------------------------------------- valutazione


@dataclass
class Chiamata:
    nome: str
    args: dict[str, Any]


def _norma(valore: Any) -> Any:
    if isinstance(valore, str):
        pulito = valore.strip().casefold()
        try:
            return float(pulito) if re.fullmatch(r"-?\d+(\.\d+)?", pulito) else pulito
        except ValueError:
            return pulito
    if isinstance(valore, bool):
        return valore
    if isinstance(valore, (int, float)):
        return float(valore)
    return valore


def combacia(atteso: Any, osservato: Any) -> bool:
    """Un argomento osservato soddisfa quello atteso?"""
    if isinstance(atteso, dict):
        if "presente" in atteso:
            return osservato not in (None, "")
        if "contiene" in atteso:
            return isinstance(osservato, str) and str(atteso["contiene"]).casefold() in osservato.casefold()
        if "una_di" in atteso:
            return any(combacia(a, osservato) for a in atteso["una_di"])
        return False
    return _norma(atteso) == _norma(osservato)


def _chiamata_soddisfa(attesa: dict[str, Any], c: Chiamata) -> bool:
    if attesa["tool"] != c.nome:
        return False
    return all(combacia(v, c.args.get(k)) for k, v in (attesa.get("args") or {}).items())


def valuta(
    voce: dict[str, Any], chiamate: list[Chiamata], entita: set[str], strumenti: set[str]
) -> dict[str, Any]:
    """Il verdetto su una richiesta: strumento giusto, argomenti giusti, invenzioni."""
    attesi = voce.get("attesi") or []
    categoria = voce["categoria"]
    nomi = [c.nome for c in chiamate]

    inventate = [
        c.args["entity_id"]
        for c in chiamate
        if isinstance(c.args.get("entity_id"), str) and c.args["entity_id"] not in entita
    ]
    inesistenti = [n for n in nomi if n not in strumenti]

    if categoria in ("ambigua", "sconosciuta"):
        ok_strumento = not any(n.startswith(PREFISSI_COMANDO) for n in nomi)
    elif not attesi:
        ok_strumento = not chiamate
    elif voce.get("ordine") == "libero":
        ok_strumento = sorted(nomi) == sorted(a["tool"] for a in attesi)
    else:
        ok_strumento = nomi == [a["tool"] for a in attesi]

    ok_argomenti = None
    if attesi and ok_strumento:
        liberi = list(chiamate)
        ok_argomenti = True
        for attesa in attesi:
            trovata = next((c for c in liberi if _chiamata_soddisfa(attesa, c)), None)
            if trovata is None:
                ok_argomenti = False
                break
            liberi.remove(trovata)

    return {
        "ok_strumento": ok_strumento,
        "ok_argomenti": ok_argomenti,
        "inventate": inventate,
        "inesistenti": inesistenti,
    }


# ------------------------------------------------------------------ il mondo


@dataclass
class Mondo:
    dati: dict[str, Any]
    entita: set[str] = field(default_factory=set)

    @classmethod
    def carica(cls, percorso: Path = BANCO / "mondo.yaml") -> Mondo:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        return cls(dati=dati, entita={a["entity_id"] for a in dati["alias"]})

    def riassunto_alias(self) -> str:
        return "\n".join(
            f"- '{a['alias']}' → `{a['entity_id']}` ({a.get('room') or 'Generale'})"
            for a in self.dati["alias"]
        )

    def riassunto_modalita(self) -> str:
        return "\n".join(
            f"- Modalità '{m['name']}' (frasi di attivazione: {', '.join(repr(f) for f in m['frasi'])}): {m['descrizione']}"
            for m in self.dati["modalita"]
        )

    def risposta(self, nome: str, strumenti: set[str]) -> dict[str, Any]:
        if nome not in strumenti:
            return {"success": False, "error": f"Tool '{nome}' non trovato nel registro."}
        return self.dati.get("risposte", {}).get(nome, {"success": True})


def prompt_di_sistema(mondo: Mondo) -> str:
    """Lo stesso prompt dell'agente, con la casa finta."""
    from shinra.config.prompt_templates import get_system_prompt
    from shinra.services.intenti.lingue import schemi
    from shinra.services.user_manager import UserProfile

    profilo = UserProfile(id="alessio", name="Alessio", role="admin", age_group="adult")
    return get_system_prompt(
        lingua=schemi("it"),
        home_context_summary=mondo.dati.get("riassunto_casa", ""),
        default_city=mondo.dati.get("citta", "Roma"),
        user_profile=profilo,
        device_aliases=mondo.riassunto_alias(),
        modes_summary=mondo.riassunto_modalita(),
    )


# ------------------------------------------------------------------- Ollama


def num_ctx_di_produzione() -> int:
    """Quello che il client usa davvero: dipende da `llm.max_tokens`."""
    from shinra.config.settings import settings

    massimo = settings.llm.max_tokens if getattr(settings.llm, "max_tokens", 0) else 150
    return 1024 if massimo <= 250 else 2048


def _strumenti_nativi(modello: str) -> bool:
    """Il client non passa gli strumenti ad alcune famiglie: il banco fa lo stesso."""
    from shinra.infra.llm import ollama

    famiglia = modello.split(":")[0].lower()
    return famiglia not in ollama._NON_TOOL_MODELS and not any(
        k in modello.lower() for k in ("gemma", "deepseek-r1", "phi")
    )


async def chiedi(
    cliente: httpx.AsyncClient,
    url: str,
    modello: str,
    messaggi: list[dict],
    strumenti: list | None,
    num_ctx: int,
    temperatura: float,
    num_predict: int,
) -> dict[str, Any]:
    from shinra.config.settings import settings

    payload: dict[str, Any] = {
        "model": modello,
        "messages": messaggi,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": temperatura, "num_ctx": num_ctx, "num_predict": num_predict, "top_p": 0.9},
    }
    if strumenti:
        payload["tools"] = strumenti
    risposta = await cliente.post(
        f"{url.rstrip('/')}/api/chat", json=payload, timeout=max(settings.llm.timeout_seconds, 180)
    )
    risposta.raise_for_status()
    return risposta.json()


def _chiamate_dal_messaggio(messaggio: dict[str, Any]) -> list[Chiamata]:
    trovate = []
    for c in messaggio.get("tool_calls") or []:
        funzione = c.get("function", {})
        args = funzione.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        trovate.append(Chiamata(str(funzione.get("name")), args if isinstance(args, dict) else {}))
    if not trovate:
        # Lo stesso ripiego dell'agente: uno strumento scritto come testo.
        testo = re.search(r"\[TOOL:\s*(\w+)\s*(\{.*?\})\]", messaggio.get("content") or "", flags=re.DOTALL)
        if testo:
            try:
                trovate.append(Chiamata(testo.group(1), json.loads(testo.group(2))))
            except ValueError:
                trovate.append(Chiamata(testo.group(1), {}))
    return trovate


async def esegui_voce(
    cliente: httpx.AsyncClient,
    url: str,
    modello: str,
    voce: dict[str, Any],
    mondo: Mondo,
    prompt: str,
    tutti_gli_strumenti: list[dict],
    strumenti: set[str],
    num_ctx: int,
    temperatura: float,
    parole_azione: tuple[str, ...],
    strumenti_sempre: bool,
) -> dict[str, Any]:
    """Una richiesta, col ciclo dell'agente. Ritorna i fatti misurati, non il verdetto."""
    frase = voce["frase"]
    servono = any(k in frase.lower() for k in parole_azione) and _strumenti_nativi(modello)
    messaggi = [{"role": "system", "content": prompt}, {"role": "user", "content": frase}]
    chiamate: list[Chiamata] = []
    esito: dict[str, Any] = {"giri": 0, "prompt_token": None, "troncato": False, "errore": "", "ciclo": False}
    inizio = time.monotonic()
    try:
        for giro in range(MAX_GIRI):
            usa = tutti_gli_strumenti if (servono and (giro == 0 or strumenti_sempre)) else None
            dati = await chiedi(cliente, url, modello, messaggi, usa, num_ctx, temperatura, 150)
            esito["giri"] += 1
            if esito["prompt_token"] is None:
                esito["prompt_token"] = dati.get("prompt_eval_count")
                # Se il prompt riempie tutto il contesto, Ollama ha tagliato: si vede qui.
                esito["troncato"] = bool(esito["prompt_token"] and esito["prompt_token"] >= num_ctx - 8)
            messaggio = dati.get("message", {})
            nuove = _chiamate_dal_messaggio(messaggio)
            if not nuove:
                break
            chiamate.extend(nuove)
            messaggi.append(
                messaggio
                if messaggio.get("tool_calls")
                else {"role": "assistant", "content": messaggio.get("content", "")}
            )
            for c in nuove:
                messaggi.append(
                    {
                        "role": "tool",
                        "name": c.nome,
                        "content": json.dumps(mondo.risposta(c.nome, strumenti), ensure_ascii=False),
                    }
                )
            if giro == MAX_GIRI - 1:
                esito["ciclo"] = True
    except (httpx.HTTPError, ValueError) as errore:
        esito["errore"] = f"{type(errore).__name__}: {errore}"
    esito["secondi"] = round(time.monotonic() - inizio, 2)
    esito["chiamate"] = [{"nome": c.nome, "args": c.args} for c in chiamate]
    return esito


# ----------------------------------------------------------------- il report


def _percento(parte: int, tutto: int) -> float:
    return round(100.0 * parte / tutto, 1) if tutto else 0.0


def riassumi(risultati: list[dict[str, Any]]) -> dict[str, Any]:
    """I numeri di una configurazione (modello + contesto) su tutte le sue richieste."""
    con_strumento = [r for r in risultati if r["voce"]["attesi"]]
    secondi = [r["secondi"] for r in risultati if not r["errore"]]
    con_argomenti = [r for r in risultati if r["ok_argomenti"] is not None]
    senza_strumento = [r for r in risultati if not r["voce"]["attesi"]]
    return {
        "richieste": len(risultati),
        "strumento_giusto": _percento(sum(r["ok_strumento"] for r in risultati), len(risultati)),
        "strumento_giusto_se_serve": _percento(
            sum(r["ok_strumento"] for r in con_strumento), len(con_strumento)
        ),
        "argomenti_giusti": _percento(
            sum(bool(r["ok_argomenti"]) for r in con_argomenti), len(con_strumento)
        ),
        "non_comanda_se_non_deve": _percento(
            sum(r["ok_strumento"] for r in senza_strumento), len(senza_strumento)
        ),
        "inventate": sum(len(r["inventate"]) for r in risultati),
        "inesistenti": sum(len(r["inesistenti"]) for r in risultati),
        "cicli": sum(r["ciclo"] for r in risultati),
        "errori": sum(bool(r["errore"]) for r in risultati),
        "troncati": sum(r["troncato"] for r in risultati),
        "prompt_token": next((r["prompt_token"] for r in risultati if r["prompt_token"]), None),
        "mediana_secondi": round(statistics.median(secondi), 2) if secondi else None,
        "p90_secondi": (
            round(sorted(secondi)[int(len(secondi) * 0.9) - 1], 2)
            if len(secondi) >= 10
            else (max(secondi) if secondi else None)
        ),
    }


def regge(r: dict[str, Any]) -> bool:
    return (
        r["strumento_giusto"] >= CRITERI["strumento_giusto"]
        and r["argomenti_giusti"] >= CRITERI["argomenti_giusti"]
        and r["inventate"] <= CRITERI["inventate"]
        and r["cicli"] <= CRITERI["cicli"]
        and r["mediana_secondi"] is not None
        and r["mediana_secondi"] <= CRITERI["mediana_secondi"]
    )


def per_categoria(risultati: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = {}
    for r in risultati:
        col = out.setdefault(r["voce"]["categoria"], [0, 0])
        col[0] += int(r["ok_strumento"] and r["ok_argomenti"] is not False)
        col[1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def markdown(configurazioni: dict[str, list[dict[str, Any]]], macchina: str, ripetizioni: int) -> str:
    righe = [
        f"# Banco di prova del tool calling — {date.today().isoformat()}",
        "",
        f"- **Macchina:** {macchina or 'non dichiarata'}",
        f"- **Ripetizioni per richiesta:** {ripetizioni}",
        f"- **Revisione:** `{_revisione()}`",
        "",
        "I criteri sono una **proposta** per l'ADR 0008, non una verita': "
        + ", ".join(
            f"{k} {'≥' if k.endswith('giusto') or k.endswith('giusti') else '≤'} {v}"
            for k, v in CRITERI.items()
        )
        + ".",
        "",
        "| Configurazione | Strumento giusto | Argomenti giusti | Inventate | Cicli | Troncati | Token prompt | Mediana s | p90 s | Regge |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    sommari = {nome: riassumi(r) for nome, r in configurazioni.items()}
    for nome, s in sommari.items():
        righe.append(
            f"| {nome} | {s['strumento_giusto']}% | {s['argomenti_giusti']}% | {s['inventate']} | {s['cicli']} | "
            f"{s['troncati']}/{s['richieste']} | {s['prompt_token'] or '—'} | {s['mediana_secondi']} | {s['p90_secondi']} | "
            f"{'si' if regge(s) else 'no'} |"
        )
    righe += ["", "## Per categoria (richieste riuscite / totali)", ""]
    categorie = sorted({c for r in configurazioni.values() for c in per_categoria(r)})
    righe.append("| Categoria | " + " | ".join(configurazioni) + " |")
    righe.append("| :--- | " + " | ".join("---:" for _ in configurazioni) + " |")
    for categoria in categorie:
        celle = []
        for r in configurazioni.values():
            ok, tot = per_categoria(r).get(categoria, (0, 0))
            celle.append(f"{ok}/{tot}")
        righe.append(f"| {categoria} | " + " | ".join(celle) + " |")
    for nome, r in configurazioni.items():
        sbagliate = [x for x in r if not x["ok_strumento"] or x["ok_argomenti"] is False]
        if not sbagliate:
            continue
        righe += ["", f"## Dove sbaglia: {nome}", ""]
        for x in sbagliate[:30]:
            visto = (
                ", ".join(f"{c['nome']}({json.dumps(c['args'], ensure_ascii=False)})" for c in x["chiamate"])
                or "nessuno strumento"
            )
            atteso = ", ".join(a["tool"] for a in x["voce"]["attesi"]) or "nessuno strumento"
            righe.append(
                f"- «{x['voce']['frase']}» — atteso {atteso}; visto {visto}"
                + (f" — **{x['errore']}**" if x["errore"] else "")
            )
    return "\n".join(righe) + "\n"


def _revisione() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607 (git e' nel PATH di chi sviluppa)
                capture_output=True,
                text=True,
                cwd=percorsi.RADICE,
                check=False,
            ).stdout.strip()
            or "?"
        )
    except OSError:
        return "?"


# ---------------------------------------------------------------------- uso


def carica_corpus(solo: str | None = None, limite: int | None = None) -> list[dict[str, Any]]:
    voci = yaml.safe_load((BANCO / "corpus.yaml").read_text(encoding="utf-8"))
    if solo:
        voci = [v for v in voci if v["categoria"] == solo]
    return voci[:limite] if limite else voci


async def principale(args: argparse.Namespace) -> int:
    # Il report ha frecce e lettere accentate: su un terminale che non e' in UTF-8 (Windows) si fermerebbe.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from shinra.config.settings import settings
    from shinra.services.intenti.lingue import schemi
    from shinra.skills.registry import TOOLS_SCHEMA

    mondo = Mondo.carica()
    prompt = prompt_di_sistema(mondo)
    strumenti = {s["function"]["name"] for s in TOOLS_SCHEMA}
    parole = schemi("it").parole_azione
    corpus = carica_corpus(args.solo, args.limite)

    token_prompt = len(prompt) // 4
    token_schemi = len(json.dumps(TOOLS_SCHEMA, ensure_ascii=False)) // 4
    produzione = num_ctx_di_produzione()
    print(f"Richieste: {len(corpus)} — strumenti: {len(strumenti)}")
    print(
        f"Prompt di sistema ~{token_prompt} token, schemi degli strumenti ~{token_schemi} token: ~{token_prompt + token_schemi} in tutto."
    )
    print(
        f"`num_ctx` di produzione: {produzione}. "
        + ("**Il prompt non ci sta: Ollama lo taglia.**" if token_prompt + token_schemi > produzione else "")
    )
    if args.prova:
        return 0

    contesti = [produzione if c == "produzione" else int(c) for c in args.num_ctx]
    configurazioni: dict[str, list[dict[str, Any]]] = {}
    async with httpx.AsyncClient() as cliente:
        for modello in args.modelli:
            for ctx in contesti:
                nome = f"{modello} @ {ctx}"
                print(f"\n=== {nome} ===")
                risultati = []
                for voce in corpus:
                    for _ in range(args.ripetizioni):
                        misura = await esegui_voce(
                            cliente,
                            args.url or settings.llm.ollama_url,
                            modello,
                            voce,
                            mondo,
                            prompt,
                            TOOLS_SCHEMA,
                            strumenti,
                            ctx,
                            args.temperatura,
                            parole,
                            args.strumenti_sempre,
                        )
                        verdetto = valuta(
                            voce,
                            [Chiamata(c["nome"], c["args"]) for c in misura["chiamate"]],
                            mondo.entita,
                            strumenti,
                        )
                        risultati.append({"voce": voce, **misura, **verdetto})
                        segno = (
                            "ok "
                            if verdetto["ok_strumento"] and verdetto["ok_argomenti"] is not False
                            else "NO "
                        )
                        print(
                            f"  {segno}{voce['id']:<28} {misura['secondi']:>6}s  {len(misura['chiamate'])} chiamate"
                            + (f"  ERRORE {misura['errore']}" if misura["errore"] else "")
                        )
                configurazioni[nome] = risultati
                scrivi(configurazioni, args, parziale=True)

    return scrivi(configurazioni, args)


def scrivi(
    configurazioni: dict[str, list[dict[str, Any]]], args: argparse.Namespace, parziale: bool = False
) -> int:
    """Scrive il report e i dati grezzi. Si chiama anche a meta' giro: un giro lungo
    interrotto non deve perdere cio' che e' gia' stato misurato."""
    testo = markdown(configurazioni, args.macchina, args.ripetizioni)
    cartella = BANCO / "risultati"
    cartella.mkdir(exist_ok=True)
    base = cartella / f"{date.today().isoformat()}-{args.etichetta}"
    base.with_suffix(".md").write_text(testo, encoding="utf-8", newline="\n")
    base.with_suffix(".json").write_text(
        # L'a capo finale: i ganci lo vogliono su ogni file, e un risultato committato senza fallirebbe in CI.
        json.dumps(
            {n: [dict(r) for r in rs] for n, rs in configurazioni.items()}, ensure_ascii=False, indent=1
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if not parziale:
        print("\n" + testo)
        print(f"Scritto {base.with_suffix('.md')}")
    return 0


def analizza() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelli", nargs="+", default=[], help="i modelli di Ollama da provare (es. qwen2.5:3b)")
    p.add_argument(
        "--num-ctx",
        nargs="+",
        default=["produzione"],
        help="`produzione` o un numero: la grandezza del contesto",
    )
    p.add_argument("--ripetizioni", type=int, default=1, help="quante volte si ripete ogni richiesta")
    p.add_argument("--temperatura", type=float, default=None, help="predefinita: quella della configurazione")
    p.add_argument("--solo", help="una sola categoria")
    p.add_argument("--limite", type=int, help="solo le prime N richieste: per provare che funziona")
    p.add_argument("--url", help="l'indirizzo di Ollama (predefinito: quello della configurazione)")
    p.add_argument("--macchina", default="", help="una riga che descrive la macchina, per il report")
    p.add_argument("--etichetta", default="banco", help="il nome del file dei risultati")
    p.add_argument(
        "--strumenti-sempre",
        action="store_true",
        help="passa gli strumenti a ogni giro (l'agente li passa solo al primo)",
    )
    p.add_argument(
        "--prova", action="store_true", help="stampa quanto pesa il prompt ed esce, senza chiamare Ollama"
    )
    args = p.parse_args()
    if not args.prova and not args.modelli:
        p.error("serve almeno un modello (--modelli) oppure --prova")
    if args.temperatura is None:
        from shinra.config.settings import settings

        args.temperatura = settings.llm.temperature
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(principale(analizza())))
