"""Il ciclo dell'agente che si racconta, evento per evento (issue #188).

La scheda «Il Cervello» illumina il grafo quando Shinra lavora. Per farlo il
ciclo che ascolta una richiesta, consulta la conoscenza, sceglie uno strumento e
comanda un dispositivo deve dire cosa sta facendo. Qui stanno i tipi di evento e
il modo di costruirli: puro, senza rete e senza bus.

**Un evento dice dove, non cosa.** Porta il tipo e gli identificativi dei nodi
toccati (`strumento:control_device`, `dispositivo:light.cucina`), mai la frase
della richiesta, mai gli argomenti di uno strumento, mai il testo di un fatto,
mai il messaggio di un errore: tutto questo puo' contenere cio' che una persona
ha detto in casa, e l'evento viaggia verso un browser. Del contenuto basta
sapere che c'e' stato.

**Un evento ha un proprietario.** `profilo` e' chi ha fatto la richiesta; il
canale verso la dashboard lo consegna solo a lui (`per_il_profilo`) e non lo
inoltra al browser.

Riferimento: issue #188.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from shinra.domain.eventi import Evento

RICHIESTA_RICEVUTA = "agente.richiesta"
CONOSCENZA_CONSULTATA = "agente.conoscenza"
SKILL_SCELTA = "agente.skill"
DISPOSITIVO_COMANDATO = "agente.dispositivo"
RISPOSTA_DATA = "agente.risposta"
ERRORE = "agente.errore"

TIPI = (
    RICHIESTA_RICEVUTA,
    CONOSCENZA_CONSULTATA,
    SKILL_SCELTA,
    DISPOSITIVO_COMANDATO,
    RISPOSTA_DATA,
    ERRORE,
)

# Il nodo del modello: cio' che riceve la richiesta e che da' la risposta. Sta nel
# grafo come agente (`services/cervello.py`, `modello_come_agente`).
NODO_MODELLO = "agente:modello"

# Gli strumenti che **comandano** qualcosa. Gli altri leggono: «com'e' il
# salotto» non e' un comando, e il grafo non deve lampeggiare come se lo fosse.
STRUMENTI_CHE_COMANDANO = frozenset({"control_device", "comanda_clima", "comanda_tapparella"})

# Perche' un ciclo e' andato storto, in una parola. Mai il messaggio: un
# errore di Ollama o di uno strumento puo' citare la richiesta.
MOTIVO_MODELLO = "modello"
MOTIVO_STRUMENTO = "strumento"


def nodo_strumento(nome: str) -> str:
    return f"strumento:{nome}"


def nodo_dispositivo(entita: str) -> str:
    return f"dispositivo:{entita}"


def nodo_fatto(identificativo: Any) -> str:
    return f"fatto:{identificativo}"


def evento(
    tipo: str,
    *,
    profilo: Optional[str],
    richiesta: str,
    nodi: Iterable[str] = (),
    **extra: Any,
) -> Evento:
    """Un evento dell'agente. `extra` ammette solo valori semplici e innocui."""
    if tipo not in TIPI:
        raise ValueError(f"Tipo di evento dell'agente sconosciuto: {tipo}")
    dati: Dict[str, Any] = {"profilo": profilo, "richiesta": richiesta, "nodi": list(nodi)}
    for chiave, valore in extra.items():
        semplice = isinstance(valore, (bool, int, float)) or valore is None
        motivo_noto = chiave == "motivo" and valore in (MOTIVO_MODELLO, MOTIVO_STRUMENTO)
        if semplice or motivo_noto:
            dati[chiave] = valore
        else:
            raise ValueError(f"`{chiave}` non puo' viaggiare in un evento dell'agente")
    return Evento(tipo=tipo, dati=dati)


def per_il_profilo(ev: Evento, profilo: Optional[str]) -> bool:
    """Questo evento va mostrato a `profilo`?

    Senza autenticazione non si sa chi e' connesso (`profilo` e' `None`): la
    casa e' di tutti, e si consegna. Con un profilo si consegna solo se e'
    quello di chi ha chiesto; un evento senza proprietario non si consegna a
    nessun profilo.
    """
    if profilo is None:
        return True
    return ev.dati.get("profilo") == profilo


def per_il_browser(ev: Evento) -> Dict[str, Any]:
    """L'evento com'e' inviato alla dashboard: senza il proprietario."""
    dati = {k: v for k, v in ev.dati.items() if k != "profilo"}
    return {"tipo": ev.tipo, "dati": dati, "momento": ev.momento.isoformat(), "frase": ""}


def nodi_dei_fatti(fatti: Iterable[Mapping[str, Any]]) -> List[str]:
    return [nodo_fatto(f["id"]) for f in fatti if f.get("id") not in (None, "")]
