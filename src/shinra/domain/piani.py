"""Un piano di un modello, controllato dal codice prima di eseguirlo (#191, ADR 0013).

Il modello non e' fidato. Quando scrive un piano (o quando un agente chiama uno strumento) puo' nominare uno strumento che non esiste, un
dispositivo che la casa non ha, un argomento che non e' un argomento, o dimenticare un parametro obbligatorio. Questo modulo e' il controllo che
sta **in mezzo**: riceve i passi, ritorna quelli che si possono eseguire e, per ciascuno scartato, **perche'**. Puro: nessuna rete, nessun
modello, nessun database, nessuna frase di una lingua (chi mostra gli scarti sceglie come dirli).

Nato dal banco dei piani (`scripts/banco_piani.py`, #430): sul modello da 3 miliardi di parametri il controllo toglie i dispositivi inventati (da 17 a 0)
e, **completando i parametri obbligatori ovvi**, ripara un errore che il modello fa spesso: «metti il clima a 20 gradi» arriva con `temperatura: 20` e senza
`azione`. Le regole che i test difendono:

- **non si indovina fra due scelte**: un obbligatorio mancante si completa solo se la frase lo ha gia' detto senza ambiguita' (uno solo dei valori possibili
  e' anche il nome di un altro argomento presente). Con due candidati, o nessuno, il passo si scarta dicendo cosa manca;
- **un passo scartato non rovina gli altri**: ogni passo si giudica da se';
- **c'e' un tetto di passi**: un modello che continua ad aggiungerne si ferma al tetto, e lo si dice;
- **il confine e' nel codice**: strumento esistente e dispositivo vero si controllano qui, non nel prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Mapping

MASSIMO_PASSI = 8

# Perche' un passo non si esegue.
NON_E_UN_OGGETTO = "non_e_un_oggetto"
STRUMENTO_INESISTENTE = "strumento_inesistente"
ARGOMENTI_NON_VALIDI = "argomenti_non_validi"
DISPOSITIVO_INESISTENTE = "dispositivo_inesistente"
OBBLIGATORIO_MANCANTE = "obbligatorio_mancante"
OLTRE_IL_TETTO = "oltre_il_tetto"


@dataclass(frozen=True)
class Passo:
    nome: str
    argomenti: dict[str, Any]


@dataclass(frozen=True)
class Scarto:
    """Un passo che non si esegue: il suo numero (da 1), il motivo come codice, e il dettaglio che serve a dirlo (un nome, un parametro)."""

    numero: int
    codice: str
    dettaglio: str = ""


def completa_argomenti(
    argomenti: Mapping[str, Any], funzione: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Completa cio' che e' ovvio e dice cosa manca: `(argomenti, obbligatori_mancanti)`.

    `funzione` e' lo schema dello strumento (il valore di `function` nello schema dei tool). Se un parametro obbligatorio manca ed e' una scelta fra
    valori (`enum`), e **uno solo** di quei valori e' anche il nome di un altro argomento presente (`temperatura`, `posizione`, `volume`...), e' quello:
    lo si completa. Altrimenti non si indovina: resta fra i mancanti.
    """
    parametri = (funzione.get("parameters") or {}).get("properties") or {}
    obbligatori = (funzione.get("parameters") or {}).get("required") or []
    completati = dict(argomenti)
    mancanti: list[str] = []
    for nome in obbligatori:
        if completati.get(nome) not in (None, ""):
            continue
        scelte = (parametri.get(nome) or {}).get("enum") or []
        candidati = [v for v in scelte if v in completati and v != nome]
        if len(candidati) == 1:
            completati[nome] = candidati[0]
        else:
            mancanti.append(nome)
    return completati, mancanti


def valida_passi(
    passi: Any,
    funzioni: Mapping[str, Mapping[str, Any]],
    dispositivi: Collection[str],
    massimo: int = MASSIMO_PASSI,
) -> tuple[list[Passo], list[Scarto]]:
    """I passi che si possono eseguire, e il perche' degli altri.

    `passi` e' l'elenco come lo scrive il modello (`[{"strumento": ..., "argomenti": {...}}]`); qualunque altra cosa vale come «nessun passo».
    `funzioni` e' `nome -> schema` degli strumenti consentiti; `dispositivi` sono gli identificativi e i nomi (alias) validi, in minuscolo: un
    `entity_id` che non e' li' dentro e' un'invenzione.
    """
    consentiti = {d.casefold() for d in dispositivi}
    accettati: list[Passo] = []
    scarti: list[Scarto] = []
    for numero, passo in enumerate(passi if isinstance(passi, list) else [], start=1):
        if numero > massimo:
            scarti.append(Scarto(numero, OLTRE_IL_TETTO, str(massimo)))
            break
        if not isinstance(passo, dict):
            scarti.append(Scarto(numero, NON_E_UN_OGGETTO))
            continue
        nome = str(passo.get("strumento") or "")
        if nome not in funzioni:
            scarti.append(Scarto(numero, STRUMENTO_INESISTENTE, nome))
            continue
        argomenti = passo.get("argomenti")
        if argomenti is None:
            argomenti = {}
        if not isinstance(argomenti, dict):
            scarti.append(Scarto(numero, ARGOMENTI_NON_VALIDI, nome))
            continue
        dispositivo = argomenti.get("entity_id")
        if isinstance(dispositivo, str) and dispositivo.strip().casefold() not in consentiti:
            scarti.append(Scarto(numero, DISPOSITIVO_INESISTENTE, dispositivo))
            continue
        argomenti, mancanti = completa_argomenti(argomenti, funzioni[nome])
        if mancanti:
            scarti.append(Scarto(numero, OBBLIGATORIO_MANCANTE, f"{nome}:{mancanti[0]}"))
            continue
        accettati.append(Passo(nome, argomenti))
    return accettati, scarti
