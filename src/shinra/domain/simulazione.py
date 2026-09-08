"""Far sembrare che in casa ci sia qualcuno.

Una luce che si accende alle 20:00 e si spegne alle 23:00, tutte le sere,
non dice «c'e' qualcuno»: dice «c'e' un timer». Chi guarda una casa per tre
sere di fila lo capisce, ed e' esattamente la persona da cui ci si vorrebbe
difendere. Per questo il piano di ogni sera e' diverso da quello della sera
prima, e il confronto e' esplicito: se per caso ne esce uno uguale, si
riprova.

Qui non si accende niente e non si aspetta niente. Entrano le luci
disponibili, l'ora del tramonto e il piano di ieri; esce il piano di stasera.
Con lo stesso seme esce sempre lo stesso piano, ed e' cio' che rende
verificabile una funzione fatta di casualita'.

Riferimento: issue #23.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Sequence

# Quante luci si accendono in una sera. Una sola sembra una dimenticanza;
# tutta la casa illuminata sembra una festa, e nessuna delle due somiglia a
# una persona che vive.
MINIME = 3
MASSIME = 5

# Quanto resta accesa una luce: da mezz'ora a un'ora e tre quarti.
DURATA_MINIMA = timedelta(minutes=30)
DURATA_MASSIMA = timedelta(minutes=105)

# La sera comincia poco dopo il tramonto e finisce quando si va a dormire —
# con un'ora di scarto, perche' nemmeno le persone vanno a letto a orario
# fisso.
DOPO_IL_TRAMONTO = (timedelta(minutes=10), timedelta(minutes=70))
ORA_DI_DORMIRE = (time(22, 30), time(0, 30))


@dataclass(frozen=True)
class Accensione:
    entity_id: str
    accendi_alle: datetime
    spegni_alle: datetime

    @property
    def durata(self) -> timedelta:
        return self.spegni_alle - self.accendi_alle


def _fine_serata(giorno: datetime, caso: random.Random) -> datetime:
    """L'ora in cui si spegne tutto, fra le 22:30 e le 00:30."""
    minuti = caso.randint(0, int((timedelta(hours=2).total_seconds()) // 60))
    inizio = giorno.replace(
        hour=ORA_DI_DORMIRE[0].hour, minute=ORA_DI_DORMIRE[0].minute, second=0, microsecond=0
    )
    return inizio + timedelta(minutes=minuti)


def _impronta(piano: Sequence[Accensione]) -> tuple:
    """Cio' che rende due sere «uguali»: stesse luci, nello stesso ordine, a
    orari che si somigliano. I minuti esatti non contano — cambiare 20:04 in
    20:06 non inganna nessuno."""
    return tuple((a.entity_id, a.accendi_alle.hour, a.accendi_alle.minute // 15) for a in piano)


def _un_piano(luci: Sequence[str], tramonto: datetime, caso: random.Random) -> list[Accensione]:
    quante = min(len(luci), caso.randint(MINIME, MASSIME))
    scelte = caso.sample(list(luci), quante)

    apertura = tramonto + timedelta(
        seconds=caso.uniform(DOPO_IL_TRAMONTO[0].total_seconds(), DOPO_IL_TRAMONTO[1].total_seconds())
    )
    chiusura = _fine_serata(tramonto, caso)
    if chiusura <= apertura:
        chiusura = apertura + timedelta(hours=2)

    finestra = (chiusura - apertura).total_seconds()
    piano: list[Accensione] = []
    for indice, luce in enumerate(scelte):
        # Le accensioni scorrono lungo la serata invece di ammucchiarsi: una
        # persona non accende tutte le stanze nello stesso quarto d'ora.
        fetta = finestra / quante
        inizio = apertura + timedelta(seconds=fetta * indice + caso.uniform(0, fetta * 0.6))
        durata = timedelta(
            seconds=caso.uniform(DURATA_MINIMA.total_seconds(), DURATA_MASSIMA.total_seconds())
        )
        fine = min(inizio + durata, chiusura)
        if fine <= inizio:
            continue
        piano.append(Accensione(luce, inizio, fine))

    return sorted(piano, key=lambda a: a.accendi_alle)


def pianifica(
    luci: Sequence[str],
    tramonto: datetime,
    seme: Optional[int] = None,
    ieri: Optional[Sequence[Accensione]] = None,
    tentativi: int = 8,
) -> list[Accensione]:
    """Il piano di stasera, diverso da quello di ieri sera.

    `seme` rende la sequenza riproducibile: senza, una funzione fatta di
    casualita' non si potrebbe provare, e questa e' una funzione che deve
    funzionare mentre nessuno la guarda.
    """
    if not luci:
        return []

    # `random` e non `secrets`: qui la casualita' serve a non sembrare un
    # timer, non a resistere a chi prova a indovinarla. E deve essere
    # riproducibile da un seme, altrimenti la funzione non si puo' provare.
    caso = random.Random(seme)  # noqa: S311
    impronta_ieri = _impronta(ieri) if ieri else None

    piano: list[Accensione] = []
    for _ in range(max(1, tentativi)):
        piano = _un_piano(luci, tramonto, caso)
        if impronta_ieri is None or _impronta(piano) != impronta_ieri:
            return piano

    # Con una luce sola le combinazioni finiscono davvero: si accetta la
    # ripetizione invece di restituire una casa spenta, che sarebbe il
    # segnale piu' chiaro di tutti.
    return piano
