"""Quali fatti servono a questa domanda, e quali no.

`get_enabled_knowledge_summary()` concatenava **tutti** i fatti abilitati e li
infilava nel prompt a ogni richiesta. Con la modalita' apprendimento
funzionante la conoscenza cresce in fretta, e il contesto cresceva con lei:
prima si paga in latenza, poi si satura la finestra e i fatti piu' vecchi
vengono troncati **in silenzio** — la casa dimentica senza dirlo.

Tre decisioni che questo modulo tiene ferme:

**Il recupero non deve mai far sapere alla casa meno di prima.** Sotto una
certa quantita' di fatti si mandano tutti, come si e' sempre fatto: il
problema esiste a duecento fatti, non a venti, e introdurre un recupero
imperfetto dove non serviva vorrebbe dire perdere risposte che prima
funzionavano. E' anche il modo piu' semplice per non peggiorare la latenza.

**La ricerca e' ibrida perche' i vettori sbagliano proprio dove fa male.** Un
embedding avvicina «la password del wifi» a «la chiave della rete», ed e'
esattamente cio' che serve; ma appiattisce «4471» e «4417» sullo stesso punto,
perche' semanticamente sono la stessa cosa — un numero. Nomi propri e cifre
sono la meta' di cio' che una casa sa, e li recupera il confronto testuale.

**Un fatto senza embedding non e' un fatto che non esiste.** Ollama puo'
essere spento, il modello puo' non essere installato, un fatto puo' essere
appena stato scritto. In tutti questi casi resta la strada testuale, e la
casa risponde peggio invece di rispondere «non lo so».

Qui non si calcola nessun embedding e non si chiama niente: entrano dei
vettori gia' fatti, esce quali fatti passano.

Riferimento: issue #32.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

# Sotto questa soglia si mandano tutti i fatti, come prima. Venticinque fatti
# stanno in poche centinaia di token: recuperarne cinque su venticinque
# costerebbe una chiamata di embedding per risparmiare niente, e
# rischierebbe di lasciare fuori quello giusto.
SOGLIA_RECUPERO = 25

# Quanti fatti al massimo finiscono nel prompt. E' il numero che rende
# costante il contesto: da qui in poi la conoscenza puo' crescere quanto
# vuole e il prompt non cresce.
MASSIMO_FATTI = 8

# Sotto questo punteggio un fatto non entra. Serve a non riempire il prompt
# di rumore quando la domanda non c'entra niente con la conoscenza di casa:
# «che tempo fa» non deve tirarsi dietro i cinque fatti meno lontani.
SOGLIA_PUNTEGGIO = 0.28

# Quanto pesa la similarita' dei vettori rispetto alla corrispondenza
# testuale. Il testo pesa meno ma non poco: e' l'unico che riconosce «4471».
PESO_VETTORE = 0.7
PESO_TESTO = 0.3

# Le parole troppo comuni per dire qualcosa su quale fatto serve.
VUOTE = frozenset(
    {
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "un",
        "uno",
        "una",
        "di",
        "a",
        "da",
        "in",
        "con",
        "su",
        "per",
        "tra",
        "fra",
        "e",
        "ed",
        "o",
        "che",
        "chi",
        "cosa",
        "come",
        "quando",
        "dove",
        "perche",
        "qual",
        "quale",
        "quali",
        "mi",
        "ti",
        "si",
        "ci",
        "vi",
        "ne",
        "del",
        "della",
        "dei",
        "delle",
        "al",
        "alla",
        "ai",
        "alle",
        "dal",
        "dalla",
        "nel",
        "nella",
        "sul",
        "sulla",
        "e'",
        "ho",
        "hai",
        "ha",
        "sono",
        "sei",
        "essere",
        "avere",
        "mio",
        "mia",
        "tuo",
        "tua",
        "suo",
        "sua",
        "questo",
        "questa",
        "quello",
    }
)


@dataclass(frozen=True)
class Fatto:
    """Un fatto con il suo vettore, se ce l'ha, e la sua storia."""

    identificativo: str
    testo: str
    categoria: str = "generale"
    vettore: Optional[Sequence[float]] = None
    # La storia (#246): quanto conta (1-5, 3 se nessuno l'ha detto), quante volte e' servito, e l'ultimo momento in cui e'
    # servito o, se mai, e' nato (secondi dall'epoca). Senza data non c'e' recenza: pesa zero, non «e' vecchio».
    importanza: int = 3
    usi: int = 0
    ultimo: Optional[float] = None


@dataclass(frozen=True)
class Pesi:
    """Quanto pesano, **oltre alla somiglianza**, l'importanza, la recenza e l'uso. Tutti a zero: il recupero di oggi.

    Non sono a zero per dimenticanza: un peso diverso da zero deve essere giustificato dal banco della memoria
    (`scripts/banco_memoria.py`, con l'ablazione per fattore), e finche' non c'e' una misura su una casa vera non si accende.
    """

    importanza: float = 0.0
    recenza: float = 0.0
    uso: float = 0.0
    # Dopo quanti giorni la recenza si dimezza.
    emivita_giorni: float = 30.0


# Un ricordo di importanza massima e' «fissato»: entra sempre, dentro il massimo, anche se la domanda non lo nomina.
IMPORTANZA_FISSATA = 5
USI_DI_RIFERIMENTO = 20


@dataclass(frozen=True)
class Trovato:
    fatto: Fatto
    punteggio: float
    per_vettore: float
    per_testo: float
    # Quanto ha aggiunto ciascun fattore della storia (importanza, recenza, uso); vuoto se non pesano.
    fattori: Mapping[str, float] = field(default_factory=dict)
    fissato: bool = False

    @property
    def solo_testuale(self) -> bool:
        """Trovato senza l'aiuto dei vettori. Utile a capire, guardando i
        log, se il recupero semantico sta funzionando o se e' spento."""
        return self.per_vettore == 0.0 and self.per_testo > 0.0


# ------------------------------------------------------------ i vettori


def coseno(primo: Sequence[float], secondo: Sequence[float]) -> float:
    """Quanto due vettori puntano nella stessa direzione, fra -1 e 1.

    Zero quando uno dei due non c'e' o e' nullo: un vettore assente non e'
    un vettore ortogonale, e trattarlo come tale darebbe un punteggio
    inventato invece che nessun punteggio.
    """
    if not primo or not secondo or len(primo) != len(secondo):
        return 0.0

    prodotto = 0.0
    norma_a = 0.0
    norma_b = 0.0
    for a, b in zip(primo, secondo, strict=False):
        prodotto += a * b
        norma_a += a * a
        norma_b += b * b

    if norma_a <= 0 or norma_b <= 0:
        return 0.0

    return prodotto / (math.sqrt(norma_a) * math.sqrt(norma_b))


# ------------------------------------------------------------- il testo


def normalizza(testo: str) -> str:
    piatto = unicodedata.normalize("NFD", (testo or "").lower())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    return piatto


def parole(testo: str) -> set[str]:
    """Le parole che dicono qualcosa, piu' i numeri.

    I numeri non si scartano mai, nemmeno corti: «la stanza 3» e «il codice
    4471» sono esattamente cio' che i vettori non sanno distinguere.
    """
    grezze = re.findall(r"[a-z0-9']+", normalizza(testo))
    tenute = set()
    for parola in grezze:
        if parola.isdigit() or (len(parola) > 2 and parola not in VUOTE):
            tenute.add(parola)
    return tenute


def somiglianza_testuale(domanda: str, fatto: str) -> float:
    """Quanta della domanda si ritrova nel fatto, fra 0 e 1.

    Si divide per le parole **della domanda** e non per l'unione: un fatto
    lungo che contiene tutto cio' che si e' chiesto e' una risposta buona, e
    penalizzarlo per la sua lunghezza premierebbe i fatti brevi e generici.
    """
    cercate = parole(domanda)
    if not cercate:
        return 0.0

    dentro = parole(fatto)
    comuni = cercate & dentro
    if not comuni:
        return 0.0

    # I numeri valgono doppio: sono la ragione per cui questa meta' esiste.
    peso = sum(2.0 if p.isdigit() else 1.0 for p in comuni)
    totale = sum(2.0 if p.isdigit() else 1.0 for p in cercate)
    return min(1.0, peso / totale)


# ---------------------------------------------------------- il recupero


def serve_recuperare(quanti_fatti: int, soglia: int = SOGLIA_RECUPERO) -> bool:
    """Se conviene recuperare, o se e' meglio mandarli tutti.

    Il problema esiste a duecento fatti, non a venti: introdurre un recupero
    imperfetto dove non serviva vorrebbe dire perdere risposte che prima
    funzionavano.
    """
    return quanti_fatti > soglia


def fattori_della_storia(fatto: Fatto, pesi: Pesi, adesso: Optional[float]) -> dict[str, float]:
    """Quanto aggiungono al punteggio l'importanza, la recenza e l'uso di un fatto. Puro, deterministico.

    - **importanza** da 1 a 5, normalizzata attorno al 3 (che e' il valore di chi non ha detto niente): da -1 a +1;
    - **recenza**: decadimento esponenziale con emivita in giorni, su `ultimo`; senza data, zero;
    - **uso**: logaritmico (il decimo uso conta meno del primo) e con un tetto, cosi' un ricordo non vince solo perche' e' vecchio.
    """
    fuori: dict[str, float] = {}
    if pesi.importanza:
        normalizzata = (max(1, min(5, int(fatto.importanza))) - 3) / 2
        fuori["importanza"] = pesi.importanza * normalizzata
    if pesi.recenza and fatto.ultimo is not None and adesso is not None and pesi.emivita_giorni > 0:
        giorni = max(0.0, (adesso - fatto.ultimo) / 86400.0)
        fuori["recenza"] = pesi.recenza * (0.5 ** (giorni / pesi.emivita_giorni))
    if pesi.uso and fatto.usi > 0:
        fuori["uso"] = pesi.uso * min(1.0, math.log1p(fatto.usi) / math.log1p(USI_DI_RIFERIMENTO))
    return fuori


def cerca(
    domanda: str,
    fatti: Iterable[Fatto],
    vettore_domanda: Optional[Sequence[float]] = None,
    massimo: int = MASSIMO_FATTI,
    soglia: float = SOGLIA_PUNTEGGIO,
    pesi: Pesi = Pesi(),
    adesso: Optional[float] = None,
) -> list[Trovato]:
    """I fatti pertinenti, dal piu' al meno.

    Senza `vettore_domanda` — Ollama spento, modello mancante — si cerca solo
    per testo: la casa risponde peggio, non smette di sapere.

    La **soglia** guarda la sola somiglianza: la storia (importanza, recenza, uso) riordina cio' che gia' passa, non fa
    entrare cio' che non c'entra con la domanda. Fanno eccezione i ricordi **fissati** (importanza 5): entrano sempre, in testa,
    dentro il `massimo`.
    """
    trovati: list[Trovato] = []
    fissati: list[Trovato] = []

    for fatto in fatti:
        per_vettore = (
            coseno(vettore_domanda, fatto.vettore) if vettore_domanda is not None and fatto.vettore else 0.0
        )
        per_testo = somiglianza_testuale(domanda, fatto.testo)

        if per_vettore <= 0 and per_testo <= 0:
            punteggio = 0.0
        elif vettore_domanda is None:
            # Senza vettori il punteggio e' tutto testuale, e la soglia si
            # applica a quello: dividerlo per il peso lo terrebbe sempre
            # sotto e non troverebbe mai niente.
            punteggio = per_testo
        else:
            punteggio = PESO_VETTORE * max(0.0, per_vettore) + PESO_TESTO * per_testo

        storia = fattori_della_storia(fatto, pesi, adesso)
        if fatto.importanza >= IMPORTANZA_FISSATA:
            fissati.append(
                Trovato(
                    fatto, punteggio + sum(storia.values()), max(0.0, per_vettore), per_testo, storia, True
                )
            )
            continue

        if punteggio <= 0 or punteggio < soglia:
            continue

        trovati.append(
            Trovato(fatto, punteggio + sum(storia.values()), max(0.0, per_vettore), per_testo, storia)
        )

    trovati.sort(key=lambda t: t.punteggio, reverse=True)
    fissati.sort(key=lambda t: t.punteggio, reverse=True)
    return (fissati + trovati)[:massimo]


def come_prompt(trovati: Sequence[Trovato]) -> str:
    """I fatti trovati, nella forma in cui entravano prima nel prompt.

    Deliberatamente identica a `get_enabled_knowledge_summary`: cambiare
    forma insieme al meccanismo vorrebbe dire non sapere quale delle due cose
    ha cambiato le risposte.
    """
    if not trovati:
        return ""
    return "\n".join(f"- {t.fatto.testo}" for t in trovati)


def tutti_come_prompt(fatti: Iterable[Fatto]) -> str:
    return "\n".join(f"- {f.testo}" for f in fatti)


def impronta(testo: str) -> str:
    """Cosa identifica il testo di un fatto, per accorgersi che e' cambiato.

    Serve a ricalcolare l'embedding quando il fatto viene modificato senza
    dover ricordarsi di chiamare qualcosa: se l'impronta salvata non
    corrisponde, il vettore e' vecchio.
    """
    import hashlib

    return hashlib.sha256((testo or "").encode("utf-8")).hexdigest()[:32]


def spiega(trovati: Sequence[Trovato]) -> list[Mapping[str, Any]]:
    """Quali fatti hanno contribuito, e quanto.

    Il criterio della scheda «mostrare quali fatti hanno contribuito a una
    risposta» non e' una curiosita': quando l'assistente risponde una cosa
    strana, la prima domanda e' «da dove l'ha presa».
    """
    return [
        {
            "id": t.fatto.identificativo,
            "testo": t.fatto.testo,
            "punteggio": round(t.punteggio, 3),
            "semantico": round(t.per_vettore, 3),
            "testuale": round(t.per_testo, 3),
            "storia": {k: round(v, 3) for k, v in t.fattori.items()},
            "fissato": t.fissato,
        }
        for t in trovati
    ]
