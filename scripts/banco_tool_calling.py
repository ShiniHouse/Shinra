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
import os
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

# Sotto questa quota di richieste con risposta, la riga del report non si puo' giudicare: «non valutabile».
# Un timeout o un guasto di Ollama sono dati mancanti, non risposte sbagliate.
QUOTA_RISPOSTE = 0.9


@dataclass
class Tempi:
    """Le attese del banco, in secondi. Si cambiano da riga di comando (e nei test).

    Il primo giro sull'i5-8500T ha insegnato tre cose (`banco/risultati/2026-10-02-i5-8500t-ANALISI.md`):
    180 secondi sono pochi per una CPU senza GPU; dopo un timeout **Ollama continua a lavorare** per
    altri 40-70 secondi e la richiesta successiva aspetta in coda, quindi serve una pausa; e Ollama,
    ucciso dal kernel, riparte da solo in pochi secondi, quindi un `ConnectError` si aspetta.
    """

    richiesta: float = 600.0
    dopo_timeout: float = 90.0
    attesa_riavvio: float = 120.0
    sonda: float = 3.0
    scalda: float = 900.0


TEMPI = Tempi()


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


def _con_alias_risolti(chiamate: list[Chiamata], alias: dict[str, str]) -> list[Chiamata]:
    """Gli strumenti risolvono «tapparella salotto» in `cover.salotto`: il confronto deve farlo come loro."""
    risolte = []
    for c in chiamate:
        riferimento = c.args.get("entity_id")
        if isinstance(riferimento, str) and riferimento.strip().casefold() in alias:
            c = Chiamata(c.nome, {**c.args, "entity_id": alias[riferimento.strip().casefold()]})
        risolte.append(c)
    return risolte


def valuta(
    voce: dict[str, Any],
    chiamate: list[Chiamata],
    entita: set[str],
    strumenti: set[str],
    alias: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Il verdetto su una richiesta: strumento giusto, argomenti giusti, invenzioni."""
    attesi = voce.get("attesi") or []
    categoria = voce["categoria"]
    nomi = [c.nome for c in chiamate]

    # `entita` contiene gli identificativi veri **e i nomi degli alias**: gli strumenti accettano
    # «tapparella camera» come «cover.camera» (lo risolvono), quindi un alias valido non e' un'invenzione.
    inventate = [
        c.args["entity_id"]
        for c in chiamate
        if isinstance(c.args.get("entity_id"), str)
        and c.args["entity_id"] not in entita
        and c.args["entity_id"].strip().casefold() not in entita
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
        liberi = _con_alias_risolti(chiamate, alias or {})
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
    # I nomi degli alias, in minuscolo: sono un modo valido di indicare un dispositivo.
    nomi: set[str] = field(default_factory=set)
    # Dal nome dell'alias, in minuscolo, all'identificativo vero.
    alias: dict[str, str] = field(default_factory=dict)

    @classmethod
    def carica(cls, percorso: Path = BANCO / "mondo.yaml") -> Mondo:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        return cls(
            dati=dati,
            entita={a["entity_id"] for a in dati["alias"]},
            nomi={a["alias"].strip().casefold() for a in dati["alias"]},
            alias={a["alias"].strip().casefold(): a["entity_id"] for a in dati["alias"]},
        )

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
        default_city=mondo.dati.get("citta", "Roma"),
        user_profile=profilo,
        device_aliases=mondo.riassunto_alias(),
        modes_summary=mondo.riassunto_modalita(),
    )


def contesto_di_richiesta(mondo: Mondo) -> str:
    """Cio' che l'agente mette davanti alla frase a ogni richiesta: l'ora e lo stato della casa.

    Il banco lo rifa a ogni richiesta, come l'agente: con l'ora vera. Prima il prompt era costruito una volta
    sola e il suo prefisso restava identico per ore, cosi' la cache di Ollama rendeva il banco piu' veloce
    della produzione, dove l'ora cambiava ogni minuto.
    """
    from shinra.config.prompt_templates import get_contesto_della_richiesta
    from shinra.services.intenti.lingue import schemi

    return get_contesto_della_richiesta(
        lingua=schemi("it"), home_context_summary=mondo.dati.get("riassunto_casa", "")
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
    payload: dict[str, Any] = {
        "model": modello,
        "messages": messaggi,
        "stream": False,
        "keep_alive": "30m",
        "options": {"temperature": temperatura, "num_ctx": num_ctx, "num_predict": num_predict, "top_p": 0.9},
    }
    if strumenti:
        payload["tools"] = strumenti
    risposta = await cliente.post(f"{url.rstrip('/')}/api/chat", json=payload, timeout=TEMPI.richiesta)
    risposta.raise_for_status()
    return risposta.json()


# Gli errori di rete che, con Ollama, vogliono dire «si sta riavviando» e non «e' sbagliato»: il servizio e'
# stato ucciso (di solito per memoria) e systemd lo rialza in pochi secondi.
ERRORI_DI_RETE = (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError)
ERRORI_DI_RETE_NOMI = tuple(e.__name__ for e in ERRORI_DI_RETE)


async def aspetta_ollama(cliente: httpx.AsyncClient, url: str, secondi: float) -> bool:
    """Aspetta che Ollama risponda a «ci sei?». Ritorna `False` se non torna entro `secondi`."""
    fine = time.monotonic() + secondi
    while True:
        try:
            risposta = await cliente.get(f"{url.rstrip('/')}/api/tags", timeout=10)
            if risposta.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        if time.monotonic() >= fine:
            return False
        await asyncio.sleep(TEMPI.sonda)


async def chiedi_resiliente(cliente: httpx.AsyncClient, url: str, *args: Any) -> dict[str, Any]:
    """Come `chiedi`, ma se Ollama cade in mezzo aspetta che torni e riprova una volta.

    Nel primo giro 244 richieste sono state scartate in quattro secondi con `ConnectError`, mentre
    Ollama si riavviava: due configurazioni del report non misuravano niente.
    """
    try:
        return await chiedi(cliente, url, *args)
    except ERRORI_DI_RETE:
        if not await aspetta_ollama(cliente, url, TEMPI.attesa_riavvio):
            raise
        return await chiedi(cliente, url, *args)


async def scalda(cliente: httpx.AsyncClient, url: str, modello: str, num_ctx: int) -> str:
    """Una richiesta minima che carica il modello con il contesto della prova.

    Il caricamento (decine di secondi, anche piu' di cento) non deve finire nella statistica della
    prima richiesta. Ritorna una stringa vuota, o l'errore.
    """
    payload = {
        "model": modello,
        "messages": [{"role": "user", "content": "ciao"}],
        "stream": False,
        "keep_alive": "30m",
        "options": {"num_ctx": num_ctx, "num_predict": 1},
    }
    try:
        risposta = await cliente.post(f"{url.rstrip('/')}/api/chat", json=payload, timeout=TEMPI.scalda)
        risposta.raise_for_status()
        return ""
    except httpx.HTTPError as errore:
        return f"{type(errore).__name__}: {errore}"


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
    agenti: bool = False,
    contesto: str = "",
) -> dict[str, Any]:
    """Una richiesta, col ciclo dell'agente. Ritorna i fatti misurati, non il verdetto.

    Con `agenti` il router sceglie i domini (ADR 0008) e il modello vede solo i loro strumenti, come fa
    `services/agent.py`; se non riconosce niente, non vede nessuno strumento.
    """
    frase = voce["frase"]
    servono = any(k in frase.lower() for k in parole_azione) and _strumenti_nativi(modello)
    visti = tutti_gli_strumenti
    scelti: list[str] = []
    if agenti and servono:
        from shinra.services import agenti as servizio_agenti
        from shinra.services.intenti.lingue import schemi

        scelti = servizio_agenti.scegli(frase, schemi("it"))
        visti = servizio_agenti.schemi_di(scelti)
    domanda = f"{contesto}\n\n{frase}" if contesto else frase
    messaggi = [{"role": "system", "content": prompt}, {"role": "user", "content": domanda}]
    chiamate: list[Chiamata] = []
    esito: dict[str, Any] = {"giri": 0, "prompt_token": None, "troncato": False, "errore": "", "ciclo": False}
    if agenti:
        esito["agenti"] = scelti
    inizio = time.monotonic()
    try:
        for giro in range(MAX_GIRI):
            usa = visti if (servono and (giro == 0 or strumenti_sempre)) else None
            dati = await chiedi_resiliente(cliente, url, modello, messaggi, usa, num_ctx, temperatura, 150)
            esito["giri"] += 1
            if esito["prompt_token"] is None:
                letti = dati.get("prompt_eval_count")
                esito["prompt_token"] = letti
                # Quanto dovrebbe pesare il prompt intero (4 caratteri per token: una stima per difetto).
                atteso = (
                    len(prompt) + len(domanda) + (len(json.dumps(usa, ensure_ascii=False)) if usa else 0)
                ) // 4
                esito["prompt_atteso"] = atteso
                # Ollama ha tagliato in due casi: il prompt riempie il contesto, oppure — e lo si vede solo cosi' —
                # ne ha letto molto meno del dovuto. Con `num_ctx` 1024 il prompt da ~5.460 token ne risultava di 514,
                # lontano dal limite: il vecchio controllo diceva «0 troncati su 114».
                esito["troncato"] = bool(letti and (letti >= num_ctx - 8 or letti < 0.7 * atteso))
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
    if esito["errore"].startswith("ReadTimeout"):
        # Rinunciare non ferma Ollama: continua per altri 40-70 secondi e la richiesta dopo aspetta in coda
        # (e scade a sua volta). Si aspetta che finisca. Il tempo della pausa non entra nei `secondi`.
        await asyncio.sleep(TEMPI.dopo_timeout)
    return esito


# ----------------------------------------------------------------- il report


def _percento(parte: int, tutto: int) -> float:
    return round(100.0 * parte / tutto, 1) if tutto else 0.0


def riassumi(risultati: list[dict[str, Any]]) -> dict[str, Any]:
    """I numeri di una configurazione (modello + contesto) su tutte le sue richieste.

    Le percentuali sono calcolate **sulle richieste che hanno avuto una risposta**: un timeout o un
    guasto di Ollama sono un dato mancante, non uno strumento sbagliato. Quante risposte sono arrivate
    sta in `risposte`, e se sono troppo poche la riga e' «non valutabile».
    """
    valide = [r for r in risultati if not r["errore"]]
    con_strumento = [r for r in valide if r["voce"]["attesi"]]
    secondi = [r["secondi"] for r in valide]
    con_argomenti = [r for r in valide if r["ok_argomenti"] is not None]
    senza_strumento = [r for r in valide if not r["voce"]["attesi"]]
    tipi_errore: dict[str, int] = {}
    for r in risultati:
        if r["errore"]:
            tipo = r["errore"].split(":")[0]
            tipi_errore[tipo] = tipi_errore.get(tipo, 0) + 1
    return {
        "richieste": len(risultati),
        "risposte": len(valide),
        "valutabile": bool(valide) and len(valide) >= QUOTA_RISPOSTE * len(risultati),
        "tipi_errore": tipi_errore,
        "strumento_giusto": _percento(sum(r["ok_strumento"] for r in valide), len(valide)),
        "strumento_giusto_se_serve": _percento(
            sum(r["ok_strumento"] for r in con_strumento), len(con_strumento)
        ),
        "argomenti_giusti": _percento(
            sum(bool(r["ok_argomenti"]) for r in con_argomenti), len(con_strumento)
        ),
        "non_comanda_se_non_deve": _percento(
            sum(r["ok_strumento"] for r in senza_strumento), len(senza_strumento)
        ),
        "inventate": sum(len(r["inventate"]) for r in valide),
        "inesistenti": sum(len(r["inesistenti"]) for r in valide),
        "cicli": sum(r["ciclo"] for r in valide),
        "errori": sum(bool(r["errore"]) for r in risultati),
        "troncati": sum(r["troncato"] for r in valide),
        "prompt_token": next((r["prompt_token"] for r in valide if r["prompt_token"]), None),
        "mediana_secondi": round(statistics.median(secondi), 2) if secondi else None,
        "p90_secondi": (
            round(sorted(secondi)[int(len(secondi) * 0.9) - 1], 2)
            if len(secondi) >= 10
            else (max(secondi) if secondi else None)
        ),
    }


def regge(r: dict[str, Any]) -> bool:
    return (
        r.get("valutabile", True)
        and r["strumento_giusto"] >= CRITERI["strumento_giusto"]
        and r["argomenti_giusti"] >= CRITERI["argomenti_giusti"]
        and r["inventate"] <= CRITERI["inventate"]
        and r["cicli"] <= CRITERI["cicli"]
        and r["mediana_secondi"] is not None
        and r["mediana_secondi"] <= CRITERI["mediana_secondi"]
    )


def per_categoria(risultati: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    """Per categoria: (riuscite, con risposta). Le richieste senza risposta non contano ne' come riuscite ne' come fallite."""
    out: dict[str, list[int]] = {}
    for r in risultati:
        col = out.setdefault(r["voce"]["categoria"], [0, 0])
        if r["errore"]:
            continue
        col[0] += int(r["ok_strumento"] and r["ok_argomenti"] is not False)
        col[1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def markdown(
    configurazioni: dict[str, list[dict[str, Any]]],
    macchina: str,
    ripetizioni: int,
    stato: dict[str, str] | None = None,
) -> str:
    righe = [
        f"# Banco di prova del tool calling — {date.today().isoformat()}",
        "",
        f"- **Macchina:** {macchina or 'non dichiarata'}",
        f"- **Ripetizioni per richiesta:** {ripetizioni}",
        f"- **Revisione:** `{_revisione()}`",
    ]
    if stato:
        righe += ["", "## Stato della macchina e limiti del servizio (all'inizio del giro)", ""]
        righe += [f"- **{voce}:** {valore}" for voce, valore in stato.items()]
    righe += [
        "",
        "I criteri sono una **proposta** per l'ADR 0008, non una verita': "
        + ", ".join(
            f"{k} {'≥' if k.endswith('giusto') or k.endswith('giusti') else '≤'} {v}"
            for k, v in CRITERI.items()
        )
        + ".",
        "",
        "Le percentuali sono sulle richieste **che hanno avuto una risposta**: un timeout o un guasto di Ollama "
        "sono un dato mancante, non uno strumento sbagliato. Con meno del "
        f"{int(QUOTA_RISPOSTE * 100)}% di risposte la riga e' **n.v.** (non valutabile).",
        "",
        "| Configurazione | Risposte | Strumento giusto | Argomenti giusti | Inventate | Cicli | Troncati | Token prompt | Mediana s | p90 s | Regge |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |",
    ]
    sommari = {nome: riassumi(r) for nome, r in configurazioni.items()}
    for nome, s in sommari.items():
        if s["risposte"] == 0:
            righe.append(f"| {nome} | 0/{s['richieste']} | — | — | — | — | — | — | — | — | n.v. |")
            continue
        giudizio = ("si" if regge(s) else "no") if s["valutabile"] else "n.v."
        righe.append(
            f"| {nome} | {s['risposte']}/{s['richieste']} | {s['strumento_giusto']}% | {s['argomenti_giusti']}% | "
            f"{s['inventate']} | {s['cicli']} | {s['troncati']}/{s['risposte']} | {s['prompt_token'] or '—'} | "
            f"{s['mediana_secondi']} | {s['p90_secondi']} | {giudizio} |"
        )
    righe += ["", "## Per categoria (riuscite / con risposta)", ""]
    categorie = sorted({c for r in configurazioni.values() for c in per_categoria(r)})
    righe.append("| Categoria | " + " | ".join(configurazioni) + " |")
    righe.append("| :--- | " + " | ".join("---:" for _ in configurazioni) + " |")
    for categoria in categorie:
        celle = []
        for r in configurazioni.values():
            ok, tot = per_categoria(r).get(categoria, (0, 0))
            celle.append(f"{ok}/{tot}")
        righe.append(f"| {categoria} | " + " | ".join(celle) + " |")
    senza_risposta = {nome: s["tipi_errore"] for nome, s in sommari.items() if s["tipi_errore"]}
    if senza_risposta:
        righe += ["", "## Senza risposta", ""]
        for nome, tipi in senza_risposta.items():
            righe.append(f"- **{nome}:** " + ", ".join(f"{n} {tipo}" for tipo, n in sorted(tipi.items())))
    for nome, r in configurazioni.items():
        sbagliate = [
            x for x in r if not x["errore"] and (not x["ok_strumento"] or x["ok_argomenti"] is False)
        ]
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


def stato_macchina() -> dict[str, str]:
    """Com'e' la macchina e come e' limitato Ollama, al meglio che si riesce (su Windows ne esce meno).

    Senza, i tempi di un giro non si interpretano: il primo, sull'i5-8500T, e' stato misurato con Ollama
    limitato a 3 core su 6 (`CPUQuota=300%`), a priorita' bassa (`Nice=10`), mentre sulla stessa macchina
    giravano un server di gioco e un browser — e nel report non c'era scritto.
    """
    stato: dict[str, str] = {"Core logici": str(os.cpu_count())}
    try:
        meminfo = {
            riga.split(":")[0]: int(riga.split(":")[1].split()[0])
            for riga in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
            if ":" in riga
        }
        stato["Memoria"] = (
            f"{meminfo['MemAvailable'] / 1048576:.1f} GB disponibili su {meminfo['MemTotal'] / 1048576:.1f} GB"
        )
        stato["Swap"] = (
            f"{(meminfo['SwapTotal'] - meminfo['SwapFree']) / 1024:.0f} MB in uso su {meminfo['SwapTotal'] / 1024:.0f} MB"
        )
        stato["Carico (1/5/15 min)"] = " / ".join(
            Path("/proc/loadavg").read_text(encoding="utf-8").split()[:3]
        )
    except (OSError, KeyError, ValueError, IndexError):
        pass
    try:
        uscita = subprocess.run(
            [  # noqa: S607
                "systemctl",
                "show",
                "ollama",
                "-p",
                "CPUQuotaPerSecUSec",
                "-p",
                "Nice",
                "-p",
                "MemoryMax",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
        valori = dict(riga.split("=", 1) for riga in uscita.splitlines() if "=" in riga)
        if valori:
            stato["Ollama: CPU concessa (secondi di CPU al secondo)"] = valori.get("CPUQuotaPerSecUSec", "?")
            stato["Ollama: priorita' (Nice)"] = valori.get("Nice", "?")
            massimo = valori.get("MemoryMax", "?")
            stato["Ollama: tetto di memoria"] = (
                f"{int(massimo) / 1073741824:.1f} GB" if massimo.isdigit() else massimo
            )
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        grandi = subprocess.run(
            ["ps", "-eo", "rss=,comm=", "--sort=-rss"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.splitlines()[:5]
        voci = []
        for riga in grandi:
            rss, _, nome = riga.strip().partition(" ")
            if rss.isdigit():
                voci.append(f"{nome.strip()} {int(rss) / 1048576:.1f} GB")
        if voci:
            stato["Processi piu' grandi"] = ", ".join(voci)
    except (OSError, subprocess.SubprocessError):
        pass
    return stato


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
    if getattr(args, "agenti", False):
        from shinra.services import agenti as servizio_agenti

        print("Con gli agenti di dominio il modello vede solo gli strumenti del dominio scelto:")
        for nome_agente, agente in servizio_agenti.AGENTI.items():
            token = (len(json.dumps(list(agente.schemi), ensure_ascii=False)) + len(prompt)) // 4
            print(f"  {nome_agente:<20} {len(agente.strumenti):>2} strumenti, prompt ~{token} token")
    if args.prova:
        return 0

    contesti = [produzione if c == "produzione" else int(c) for c in args.num_ctx]
    TEMPI.richiesta = args.timeout
    TEMPI.dopo_timeout = args.dopo_timeout
    TEMPI.attesa_riavvio = args.attesa_riavvio
    args.stato_macchina = stato_macchina()
    for voce_stato, valore in args.stato_macchina.items():
        print(f"{voce_stato}: {valore}")

    indirizzo = args.url or settings.llm.ollama_url
    configurazioni: dict[str, list[dict[str, Any]]] = {}
    interrotto = False
    async with httpx.AsyncClient() as cliente:
        if not await aspetta_ollama(cliente, indirizzo, 30):
            print(f"Ollama non risponde su {indirizzo}: il giro non parte.", file=sys.stderr)
            return 2
        for modello in args.modelli:
            for ctx in contesti:
                if interrotto:
                    break
                nome = f"{modello} @ {ctx}" + (" + agenti" if getattr(args, "agenti", False) else "")
                print(f"\n=== {nome} ===")
                if not await aspetta_ollama(cliente, indirizzo, TEMPI.attesa_riavvio):
                    print("Ollama non risponde piu': giro interrotto.", file=sys.stderr)
                    interrotto = True
                    break
                # Il caricamento del modello non deve finire nella statistica della prima richiesta.
                guasto = await scalda(cliente, indirizzo, modello, ctx)
                print(
                    f"  ATTENZIONE: il modello non si e' caricato ({guasto})"
                    if guasto
                    else "  modello caricato"
                )
                risultati: list[dict[str, Any]] = []
                di_fila = 0
                for voce in corpus:
                    for _ in range(args.ripetizioni):
                        misura = await esegui_voce(
                            cliente,
                            indirizzo,
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
                            getattr(args, "agenti", False),
                            contesto_di_richiesta(mondo),
                        )
                        # I nomi degli alias sono un modo valido di indicare un dispositivo: non sono invenzioni.
                        verdetto = valuta(
                            voce,
                            [Chiamata(c["nome"], c["args"]) for c in misura["chiamate"]],
                            mondo.entita | mondo.nomi,
                            strumenti,
                            mondo.alias,
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
                        # Ollama non torna nemmeno dopo l'attesa: inutile consumare le altre richieste a vuoto.
                        di_fila = di_fila + 1 if misura["errore"].startswith(ERRORI_DI_RETE_NOMI) else 0
                        if di_fila >= 3:
                            print(
                                "Ollama non risponde: giro interrotto, i risultati parziali sono salvati.",
                                file=sys.stderr,
                            )
                            interrotto = True
                            break
                    if interrotto:
                        break
                configurazioni[nome] = risultati
                scrivi(configurazioni, args, parziale=True)

    esito = scrivi(configurazioni, args)
    return 2 if interrotto else esito


def scrivi(
    configurazioni: dict[str, list[dict[str, Any]]], args: argparse.Namespace, parziale: bool = False
) -> int:
    """Scrive il report e i dati grezzi. Si chiama anche a meta' giro: un giro lungo
    interrotto non deve perdere cio' che e' gia' stato misurato."""
    testo = markdown(configurazioni, args.macchina, args.ripetizioni, getattr(args, "stato_macchina", None))
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
        "--timeout",
        type=float,
        default=TEMPI.richiesta,
        help="secondi da aspettare una risposta (predefinito 600: su una CPU senza GPU 180 non bastano)",
    )
    p.add_argument(
        "--dopo-timeout",
        type=float,
        default=TEMPI.dopo_timeout,
        help="pausa dopo un timeout: Ollama continua a lavorare altri 40-70 secondi",
    )
    p.add_argument(
        "--attesa-riavvio",
        type=float,
        default=TEMPI.attesa_riavvio,
        help="secondi da aspettare che Ollama torni dopo un guasto prima di rinunciare",
    )
    p.add_argument(
        "--strumenti-sempre",
        action="store_true",
        help="passa gli strumenti a ogni giro (l'agente li passa solo al primo)",
    )
    p.add_argument(
        "--agenti",
        action="store_true",
        help="il router sceglie gli agenti di dominio e il modello vede solo i loro strumenti (ADR 0008)",
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
