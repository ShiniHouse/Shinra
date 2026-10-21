"""I lavori in background: cosa e' un lavoro, in che stati sta, e quando puo' passare da uno all'altro (#431, ADR 0013).

Una richiesta che non si risolve in pochi secondi diventa un **lavoro**: Shinra risponde subito «ci sto lavorando», il lavoro va avanti in
coda e l'esito arriva dopo. Questo modulo e' puro: non sa niente di database, di modelli o di rete. Dice solo le regole del gioco, che i
test difendono:

- **gli stati sono sei** e un lavoro finito non torna indietro: `fatto`, `fallito`, `annullato` e `interrotto` sono terminali;
- **`interrotto` non e' `fallito`**: il servizio si e' riavviato (o il lavoro non e' mai partito) e non si sa cosa sia successo. Si dice
  cosi', invece di inventare un esito, e la persona decide se rifarlo;
- **un lavoro ha un tetto di tempo** e nessuno lo supera: a quel punto e' `fallito` con il motivo «tetto di tempo»;
- **l'avanzamento sale e basta**: 0-100, mai indietro.
"""

from __future__ import annotations

IN_CODA = "in_coda"
IN_CORSO = "in_corso"
FATTO = "fatto"
FALLITO = "fallito"
ANNULLATO = "annullato"
INTERROTTO = "interrotto"

STATI = (IN_CODA, IN_CORSO, FATTO, FALLITO, ANNULLATO, INTERROTTO)
TERMINALI = frozenset({FATTO, FALLITO, ANNULLATO, INTERROTTO})

_TRANSIZIONI = {
    IN_CODA: frozenset({IN_CORSO, ANNULLATO, INTERROTTO}),
    IN_CORSO: frozenset({FATTO, FALLITO, ANNULLATO, INTERROTTO}),
}

# Un lavoro non puo' durare piu' di cosi', qualunque cosa dica la configurazione: un tetto sbagliato (un numero enorme) non deve
# trasformare un lavoro in un processo che non finisce mai su un server senza GPU.
TETTO_MASSIMO_SECONDI = 3600
TETTO_MINIMO_SECONDI = 10

MOTIVO_TETTO = "tetto di tempo"
MOTIVO_RIAVVIO = "il servizio si e' riavviato prima della fine"


def e_terminale(stato: str) -> bool:
    return stato in TERMINALI


def puo_passare(da: str, a: str) -> bool:
    """Un lavoro finito non cambia piu'; uno in corso non torna in coda."""
    return a in _TRANSIZIONI.get(da, frozenset())


def tetto_valido(secondi: float) -> int:
    """Il tetto di tempo da usare davvero: dentro i limiti, anche se la configurazione dice altro."""
    try:
        valore = int(secondi)
    except (TypeError, ValueError):
        return TETTO_MASSIMO_SECONDI
    return max(TETTO_MINIMO_SECONDI, min(TETTO_MASSIMO_SECONDI, valore))


def avanzamento_valido(attuale: int, nuovo: int) -> int:
    """L'avanzamento sale e basta: 0-100, e un valore piu' basso di quello che c'e' gia' non lo abbassa."""
    return max(attuale, max(0, min(100, int(nuovo))))
