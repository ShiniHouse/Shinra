"""Piu' punti di ascolto in casa, e uno solo che risponde.

Un satellite e' un posto da cui si puo' parlare alla casa: per adesso la
dashboard aperta su un telefono o su un portatile, domani un dispositivo da
poche decine di euro in ogni stanza. Cio' che rende utile un satellite non e'
il microfono — quello ce l'ha anche il telefono in tasca — ma il fatto che
**sa dove si trova**: «accendi la luce» detto in cucina vuol dire quella
della cucina.

Due cose che questo dominio tiene ferme.

**Chi sente la stessa frase in due non risponde in due.** Due telefoni sullo
stesso tavolo sentono la stessa cosa; se rispondessero entrambi, la casa
direbbe tutto due volte e accenderebbe la luce due volte — che per una luce
non si nota e per una serranda si'. Risponde uno solo, e quale lo si decide
qui.

**Un satellite che tace non e' un satellite spento.** Chi chiude la scheda
del browser non si disconnette: smette e basta. Perche' l'elenco dei punti
di ascolto voglia dire qualcosa, chi non si fa sentire da un po' esce
dall'elenco da solo.

Qui non si ascolta niente e non si risponde a nessuno: entrano chi ha sentito
cosa e quando, esce chi deve rispondere.

Riferimento: issue #33.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence

from shinra.domain import stanze

# Quanto vicine devono essere due frasi nel tempo perche' si consideri la
# stessa, sentita da due orecchie diverse.
#
# Due secondi e mezzo: una frase breve dura meno di questo, e due satelliti
# nella stessa stanza la finiscono di trascrivere a pochi decimi l'uno
# dall'altro. Allargare troppo vorrebbe dire scambiare per un'eco due
# richieste diverse dette di seguito — «accendi la luce», «spegni la luce» —
# e la seconda andrebbe persa, che e' molto peggio di rispondere due volte.
DURATA_ECO = timedelta(seconds=2.5)

# Dopo quanto silenzio un satellite si considera andato via. Generoso di
# proposito: un telefono che si blocca lo schermo smette di farsi sentire e
# non e' sparito.
SILENZIO_MASSIMO = timedelta(minutes=5)


# La stessa normalizzazione dei nomi di stanza, e non una seconda copia: due
# frasi che questo modulo considera diverse e quello considera uguali sono un
# difetto che si manifesta solo con due satelliti accesi, cioe' mai in prova.
_normalizza = stanze.normalizza


@dataclass(frozen=True)
class Satellite:
    """Un punto di ascolto, e dove si trova."""

    identificativo: str
    nome: str = ""
    stanza: str = ""
    visto_il: Optional[datetime] = None

    def presente(self, adesso: datetime, silenzio_massimo: timedelta = SILENZIO_MASSIMO) -> bool:
        if self.visto_il is None:
            return False
        return adesso - self.visto_il <= silenzio_massimo


@dataclass(frozen=True)
class Ascolto:
    """Un satellite ha sentito una frase, a un certo momento."""

    satellite: str
    frase: str
    quando: datetime


def e_la_stessa_frase(uno: Ascolto, altro: Ascolto, finestra: timedelta = DURATA_ECO) -> bool:
    """Due ascolti sono la stessa frase sentita da due orecchie diverse.

    Lo stesso satellite che ripete non e' un'eco: se qualcuno dice due volte
    «accendi la luce» allo stesso telefono, sono due richieste.
    """
    if uno.satellite == altro.satellite:
        return False
    if _normalizza(uno.frase) != _normalizza(altro.frase):
        return False
    return abs(uno.quando - altro.quando) <= finestra


def deve_rispondere(
    ascolto: Ascolto, gia_sentiti: Sequence[Ascolto], finestra: timedelta = DURATA_ECO
) -> bool:
    """Se tocca a questo satellite, o se un altro ci ha gia' pensato.

    **Risponde chi arriva per primo**, ed e' una scelta, non una scorciatoia.
    L'alternativa sarebbe aspettare la finestra intera per sentire tutti e
    poi scegliere il piu' vicino — ma quella finestra e' due secondi e mezzo,
    e due secondi e mezzo prima di accendere una luce li sente chiunque. Una
    casa che risponde subito dalla stanza sbagliata e' meglio di una casa che
    risponde tardi dalla stanza giusta, perche' la seconda sembra rotta.

    Chi arriva primo e' anche, quasi sempre, chi sta piu' vicino: il suono ci
    mette meno ad arrivare e la trascrizione parte prima.

    Un ascolto senza frase non e' un ascolto: non blocca nessuno.
    """
    if not ascolto.frase.strip():
        return False
    return not any(e_la_stessa_frase(ascolto, gia, finestra) for gia in gia_sentiti)


def solo_recenti(
    ascolti: Sequence[Ascolto], adesso: datetime, finestra: timedelta = DURATA_ECO
) -> list[Ascolto]:
    """Cio' che vale ancora la pena ricordare per riconoscere un'eco.

    Senza questo l'elenco degli ascolti cresce per sempre, e con esso il costo
    di ogni frase detta in casa.
    """
    return [a for a in ascolti if adesso - a.quando <= finestra]


def presenti(
    satelliti: Iterable[Satellite],
    adesso: datetime,
    silenzio_massimo: timedelta = SILENZIO_MASSIMO,
) -> list[Satellite]:
    """Chi si e' fatto sentire di recente, in ordine di stanza.

    L'ordine e' per stanza e non per ultimo contatto perche' questo elenco
    finisce sotto gli occhi di qualcuno, e un elenco che si riordina da solo
    a ogni sguardo non si riesce a leggere.
    """
    vivi = [s for s in satelliti if s.presente(adesso, silenzio_massimo)]
    return sorted(vivi, key=lambda s: (_normalizza(s.stanza), s.identificativo))


def stanza_di(satelliti: Iterable[Satellite], identificativo: str) -> str:
    """Da dove parla questo satellite, o stringa vuota se non lo si conosce.

    Vuota e non un ripiego: attribuire un comando alla stanza sbagliata e'
    peggio che non attribuirlo a nessuna, perche' accende la luce di qualcun
    altro.
    """
    for s in satelliti:
        if s.identificativo == identificativo:
            return s.stanza
    return ""
