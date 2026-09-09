"""Da kilowattora a euro, e da letture a consumi.

Due conti, tenuti separati perche' sbagliano in modi diversi.

**Il costo.** Una tariffa monoraria ha un prezzo solo; una bioraria ne ha due
(F1 da una parte, F2 e F3 dall'altra); una trioraria ne ha tre. Sono tutte e
tre lo stesso conto — kilowattora per prezzo — su fasce raggruppate in modo
diverso, quindi qui c'e' una struttura sola con tre modi di riempirla.

**Il consumo.** I sensori di energia di Home Assistant sono quasi sempre
contatori che salgono e non si azzerano mai: il consumo di un'ora non e' la
lettura, e' la differenza fra due letture. Da qui i due casi che rovinano i
conti, e che questo modulo tratta apposta: un contatore che **si azzera** (il
dispositivo e' stato riavviato, o il sensore e' stato ricreato) e uno che
**salta indietro**.

Una nota che vale piu' del codice: quando i dati non ci sono, qui non esce un
numero. «Zero kilowattora» e «non lo so» sono risposte diverse, e la prima
detta al posto della seconda e' il modo piu' rapido per far perdere fiducia a
un conto in bolletta.

Riferimento: issue #24.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping, Optional, Sequence

from shinra.domain import fasce

MONORARIA = "monoraria"
BIORARIA = "bioraria"
TRIORARIA = "trioraria"

TIPI = (MONORARIA, BIORARIA, TRIORARIA)

# Un prezzo di riferimento in euro al kilowattora, usato solo quando non ne
# e' configurato nessuno. Non e' «il prezzo dell'energia»: e' un ordine di
# grandezza, e ogni risposta che lo usa lo dichiara come stimato.
PREZZO_DI_RIPIEGO = 0.25


class SenzaDati(Exception):
    """Non ci sono letture per rispondere.

    Esiste perche' la strada facile — restituire zero — e' anche la
    peggiore: chi chiede quanto ha consumato e sente «zero» crede di non aver
    consumato niente.
    """


@dataclass(frozen=True)
class Tariffa:
    """Quanto costa un kilowattora, per fascia.

    La bioraria raggruppa F2 e F3 sotto lo stesso prezzo: e' come la
    scrivono i contratti italiani, dove le due si chiamano insieme «ore
    fuori punta».
    """

    tipo: str = MONORARIA
    prezzi: Mapping[str, float] = field(default_factory=dict)
    stimata: bool = False

    def prezzo(self, fascia: str) -> float:
        if fascia in self.prezzi:
            return self.prezzi[fascia]
        # Una fascia senza prezzo proprio ricade su F1, che e' la piu' cara:
        # sbagliare per eccesso in una stima di spesa e' meno dannoso che
        # promettere un risparmio che non c'e'.
        return self.prezzi.get(fasce.F1, PREZZO_DI_RIPIEGO)


def tariffa_monoraria(prezzo: float, stimata: bool = False) -> Tariffa:
    return Tariffa(MONORARIA, dict.fromkeys(fasce.FASCE, prezzo), stimata)


def tariffa_bioraria(punta: float, fuori_punta: float) -> Tariffa:
    return Tariffa(BIORARIA, {fasce.F1: punta, fasce.F2: fuori_punta, fasce.F3: fuori_punta})


def tariffa_trioraria(f1: float, f2: float, f3: float) -> Tariffa:
    return Tariffa(TRIORARIA, {fasce.F1: f1, fasce.F2: f2, fasce.F3: f3})


def tariffa_di_ripiego() -> Tariffa:
    """Quando non e' configurato niente. Si dichiara stimata, sempre."""
    return tariffa_monoraria(PREZZO_DI_RIPIEGO, stimata=True)


@dataclass(frozen=True)
class Consumo:
    """Quanti kilowattora, divisi per fascia, e quanto costano."""

    per_fascia: Mapping[str, float]

    @property
    def totale(self) -> float:
        return round(sum(self.per_fascia.values()), 3)

    def costo(self, tariffa: Tariffa) -> float:
        return round(sum(kwh * tariffa.prezzo(f) for f, kwh in self.per_fascia.items()), 2)

    def dominante(self) -> Optional[str]:
        """La fascia in cui si e' consumato di piu'. Serve a dire dove
        conviene spostare le abitudini, che e' l'unica cosa su cui una
        persona puo' agire."""
        if not self.per_fascia:
            return None
        return max(self.per_fascia.items(), key=lambda voce: voce[1])[0]


def consumo_vuoto() -> Consumo:
    return Consumo(dict.fromkeys(fasce.FASCE, 0.0))


@dataclass(frozen=True)
class Lettura:
    """Un contatore a un istante: il valore che segna e quando."""

    momento: datetime
    valore: float


def differenze(letture: Sequence[Lettura]) -> list[tuple[datetime, float]]:
    """Da contatore cumulativo a consumo per intervallo.

    I due casi che rovinano i conti:

    - **il contatore si azzera** (dispositivo riavviato, sensore ricreato):
      la differenza verrebbe negativa e sottrarrebbe consumo mai avvenuto.
      Si prende il nuovo valore come consumo dell'intervallo, che e' la
      lettura giusta di un contatore ripartito da zero.
    - **il contatore salta indietro di poco** senza azzerarsi: e' un guasto
      del sensore, non un consumo negativo. L'intervallo vale zero.

    In entrambi i casi non si solleva: un contatore che si comporta male
    all'una di notte non deve far sparire il conto di tutta la giornata.
    """
    fuori: list[tuple[datetime, float]] = []
    precedente: Optional[Lettura] = None

    for lettura in sorted(letture, key=lambda x: x.momento):
        if precedente is not None:
            salto = lettura.valore - precedente.valore
            if salto >= 0:
                fuori.append((lettura.momento, salto))
            elif lettura.valore < precedente.valore / 2:
                # Ripartito da zero: quel che segna adesso e' quel che ha
                # consumato da quando e' ripartito.
                fuori.append((lettura.momento, max(0.0, lettura.valore)))
            else:
                fuori.append((lettura.momento, 0.0))
        precedente = lettura

    return fuori


def per_fascia(intervalli: Iterable[tuple[datetime, float]]) -> Consumo:
    """Somma i consumi raggruppandoli nella fascia del loro momento.

    La fascia si prende dalla **fine** dell'intervallo, che e' il momento
    della lettura. Un'ora a cavallo di un cambio fascia finisce tutta nella
    seconda: con letture orarie l'errore vale al massimo un'ora al giorno, e
    dividerla proporzionalmente richiederebbe di sapere *quando* dentro
    quell'ora si e' consumato — che e' esattamente cio' che il contatore non
    dice.
    """
    totali = dict.fromkeys(fasce.FASCE, 0.0)
    for momento, kwh in intervalli:
        totali[fasce.fascia(momento)] += kwh
    return Consumo({f: round(v, 3) for f, v in totali.items()})


def consumo_da_letture(letture: Sequence[Lettura]) -> Consumo:
    """La strada completa: contatori dentro, kilowattora per fascia fuori."""
    if len(letture) < 2:
        raise SenzaDati(
            "Servono almeno due letture del contatore per sapere quanto e' "
            "stato consumato: una sola dice a che punto e', non quanto e' "
            "passato."
        )
    return per_fascia(differenze(letture))


def costo_orario(potenza_watt: float, tariffa: Tariffa, momento: datetime) -> float:
    """Quanto costa tenere acceso per un'ora un carico di questa potenza."""
    return round((potenza_watt / 1000.0) * tariffa.prezzo(fasce.fascia(momento)), 3)


def in_euro(valore: float) -> str:
    """Il numero come lo direbbe una persona: «1,25 euro», «38 centesimi»."""
    if valore < 1:
        centesimi = round(valore * 100)
        return f"{centesimi} centesim{'o' if centesimi == 1 else 'i'}"
    return f"{valore:.2f}".replace(".", ",") + " euro"
