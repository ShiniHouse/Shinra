"""Gli agenti di dominio e il router che li sceglie (ADR 0008, issue #190).

Un modello piccolo, davanti a tutti i trentasei strumenti, ne sceglie uno di un
altro dominio (una luce comandata con lo strumento delle tapparelle) e, con il
contesto di produzione, nemmeno li vede tutti: il banco di prova (#183) ha
misurato 5.460 token di prompt contro i 514 che Ollama legge. Qui ogni dominio
del catalogo diventa un **agente**: un nome e l'elenco degli strumenti che
dichiara. Il router guarda la frase e dice quali agenti prendono la richiesta;
il modello vede soltanto i loro strumenti.

**Il confine sta nell'esecuzione, non nel prompt.** Togliere uno strumento dallo
schema non basta: un modello puo' nominarlo lo stesso. `consente` e' il
controllo che l'agente applica prima di eseguire: uno strumento non dichiarato
non parte, comunque il modello lo chieda.

**Il router non usa il modello.** Parole chiave per dominio, nella lingua di chi
parla (`agente.domini` nei file delle lingue): costa microsecondi e non puo'
inventare. Se nessuna parola riconosce un dominio, il router non sceglie e
il modello non riceve **nessuno strumento** e risponde a parole: la frase e' ambigua o parla di qualcosa
che la casa non ha, e la risposta giusta e' una domanda, non un comando. Il catalogo intero non e' un ripiego:
pesa ~5.460 token, non ci sta nel contesto (il banco lo ha visto troncato anche a 4096) e invita a indovinare.

Le frasi che toccano due domini ricevono i due agenti con piu' parole
riconosciute, mai di piu': sono comunque meno strumenti del catalogo intero.
L'ADR 0008 prevede di scomporle in due passaggi; per ora si uniscono, e la
misura dira' se serve di piu'.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Sequence

from shinra.services.intenti.lingue import Schemi
from shinra.skills.catalogo import (
    agenda,
    casa,
    clima_e_tapparelle,
    dispositivi,
    energia,
    informazioni,
    promemoria,
    sicurezza,
)

# Quanti agenti al massimo prendono una stessa richiesta.
MASSIMO_AGENTI = 2


@dataclass(frozen=True)
class Agente:
    """Un dominio e gli strumenti che dichiara. Non ne ha altri."""

    nome: str
    schemi: tuple
    # Parole del router per gli agenti che non stanno nei file delle lingue: i plugin (#193).
    parole: tuple = ()

    @property
    def strumenti(self) -> FrozenSet[str]:
        return frozenset(s["function"]["name"] for s in self.schemi)


def _agente(nome: str, modulo: Any) -> Agente:
    return Agente(nome=nome, schemi=tuple(modulo.SCHEMI))


# Il nome del dominio e' quello che le lingue usano in `agente.domini`.
#
# **L'ordine conta a parita' di parole riconosciute**: vince chi sta prima. I
# domini delicati (sicurezza, serrature) stanno in testa, e `casa`, le cui parole
# («accendi», «spegni») sono le piu' generiche, in fondo.
AGENTI: Dict[str, Agente] = {
    a.nome: a
    for a in (
        _agente("sicurezza", sicurezza),
        _agente("dispositivi", dispositivi),
        _agente("clima_e_tapparelle", clima_e_tapparelle),
        _agente("energia", energia),
        _agente("promemoria", promemoria),
        _agente("agenda", agenda),
        _agente("informazioni", informazioni),
        _agente("casa", casa),
    )
}


def aggiungi_agente(nome: str, schemi: Sequence[Dict[str, Any]], parole: Sequence[str]) -> None:
    """Un agente in piu' (un plugin), in fondo: a parita' di parole vincono quelli del catalogo."""
    AGENTI[nome] = Agente(nome=nome, schemi=tuple(schemi), parole=tuple(parole))


def togli_agente(nome: str) -> None:
    AGENTI.pop(nome, None)


def scegli(testo: str, lingua: Schemi) -> List[str]:
    """I nomi degli agenti che prendono la richiesta, dal piu' al meno pertinente.

    Vuota se nessuna parola riconosce un dominio: chi chiama usa il ripiego.
    """
    minuscolo = testo.lower()
    punteggi = []
    for posizione, nome in enumerate(AGENTI):
        parole = lingua.domini_agente.get(nome, ()) or AGENTI[nome].parole
        colpi = sum(1 for p in parole if p and p in minuscolo)
        if colpi:
            punteggi.append((-colpi, posizione, nome))
    punteggi.sort()
    return [nome for _, _, nome in punteggi[:MASSIMO_AGENTI]]


def strumenti_di(nomi: Sequence[str]) -> FrozenSet[str]:
    """L'unione degli strumenti dichiarati dagli agenti indicati."""
    return frozenset().union(*(AGENTI[n].strumenti for n in nomi)) if nomi else frozenset()


def schemi_di(nomi: Sequence[str]) -> List[Dict[str, Any]]:
    """Gli schemi che il modello vede quando lavorano questi agenti."""
    return [schema for n in nomi for schema in AGENTI[n].schemi]


def consente(nomi: Sequence[str], strumento: str) -> bool:
    """Questo strumento puo' partire, con questi agenti al lavoro?

    Senza agenti non parte niente: se il router non ha riconosciuto un dominio il modello non ha
    ricevuto strumenti, e uno che ne nomina lo stesso (a memoria, o in un `[TOOL: ...]` nel testo)
    sta inventando.
    """
    return strumento in strumenti_di(nomi)
