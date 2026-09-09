"""Le fasce orarie italiane dell'energia elettrica: F1, F2, F3.

Le definisce ARERA, valgono per tutti, e non le decide questo file: qui sono
solo trascritte. Chi le cambia e' l'autorita', e quando succedera' si cambiano
qui e in nessun altro posto.

    F1  lunedi'-venerdi' 8-19                          (ore di punta)
    F2  lunedi'-venerdi' 7-8 e 19-23; sabato 7-23      (ore intermedie)
    F3  tutti i giorni 0-7 e 23-24; domenica e festivi (fuori punta)

Tre cose che si sbagliano facilmente, e che qui sono trattate apposta:

**I festivi valgono F3 per l'intera giornata.** Non le domeniche soltanto:
Natale che cade di mercoledi' e' F3 dalle 0 alle 24, e chi calcola la fascia
guardando solo il giorno della settimana sbaglia undici giorni all'anno.

**Pasquetta si muove.** E' l'unico festivo nazionale che non ha una data
fissa, quindi va calcolata. Pasqua invece cade sempre di domenica ed e' gia'
F3 per quello.

**L'ora e' quella italiana, non UTC.** Home Assistant scrive i suoi
timestamp in UTC; una fascia calcolata sull'ora UTC sbaglia di un'ora
d'inverno e di due d'estate — cioe' quasi sempre, e proprio nelle ore in cui
le fasce cambiano. Qui ogni momento viene riportato a `Europe/Rome` prima di
guardare l'orologio.

Riferimento: issue #24.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

F1 = "F1"
F2 = "F2"
F3 = "F3"

FASCE = (F1, F2, F3)

NOMI = {
    F1: "ore di punta",
    F2: "ore intermedie",
    F3: "fuori punta",
}

FUSO = ZoneInfo("Europe/Rome")

# I dieci festivi nazionali a data fissa. Le feste patronali non contano:
# valgono in un comune solo, e la tariffa e' nazionale.
FESTIVI_FISSI: frozenset[tuple[int, int]] = frozenset(
    {
        (1, 1),  # Capodanno
        (1, 6),  # Epifania
        (4, 25),  # Liberazione
        (5, 1),  # Festa del lavoro
        (6, 2),  # Repubblica
        (8, 15),  # Ferragosto
        (11, 1),  # Ognissanti
        (12, 8),  # Immacolata
        (12, 25),  # Natale
        (12, 26),  # Santo Stefano
    }
)


def pasqua(anno: int) -> date:
    """La domenica di Pasqua, con l'algoritmo gregoriano anonimo.

    Serve solo per arrivare a Pasquetta, che e' il giorno dopo: Pasqua cade
    di domenica e sarebbe F3 comunque.
    """
    a = anno % 19
    b, c = divmod(anno, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lettera = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lettera) // 451
    mese, giorno = divmod(h + lettera - 7 * m + 114, 31)
    return date(anno, mese, giorno + 1)


def pasquetta(anno: int) -> date:
    return pasqua(anno) + timedelta(days=1)


def e_festivo(giorno: date) -> bool:
    """Festivo nazionale: F3 dalle 0 alle 24, comunque cada."""
    return (giorno.month, giorno.day) in FESTIVI_FISSI or giorno == pasquetta(giorno.year)


def ora_italiana(momento: datetime) -> datetime:
    """Il momento riportato all'ora di Roma.

    Un momento senza fuso viene creduto sulla parola: e' gia' l'ora di casa.
    Uno con il fuso — come quelli che arrivano da Home Assistant, in UTC —
    viene convertito, perche' altrimenti la fascia sarebbe sbagliata di
    un'ora d'inverno e di due d'estate.
    """
    if momento.tzinfo is None:
        return momento
    return momento.astimezone(FUSO)


def fascia(momento: datetime) -> str:
    """In che fascia cade questo momento."""
    locale = ora_italiana(momento)
    giorno = locale.date()
    ora = locale.hour

    # La notte e' fuori punta per tutti, festivo o feriale.
    if ora < 7 or ora >= 23:
        return F3

    # Domenica e festivi sono F3 per l'intera giornata.
    if locale.weekday() == 6 or e_festivo(giorno):
        return F3

    # Il sabato non ha ore di punta: dalle 7 alle 23 e' tutto intermedio.
    if locale.weekday() == 5:
        return F2

    # Dal lunedi' al venerdi': punta dalle 8 alle 19, intermedio ai bordi.
    return F1 if 8 <= ora < 19 else F2


def nome(codice: str) -> str:
    return NOMI.get(codice, codice)


def descrivi(momento: datetime) -> str:
    """La fascia con il perche', che e' la parte che serve a una persona."""
    locale = ora_italiana(momento)
    corrente = fascia(locale)
    motivo = _perche(locale, corrente)
    return f"Siamo in {corrente}, {nome(corrente)}{motivo}."


def _perche(locale: datetime, corrente: str) -> str:
    if corrente != F3:
        return ""
    if e_festivo(locale.date()):
        return ": e' un giorno festivo, e i festivi sono fuori punta tutto il giorno"
    if locale.weekday() == 6:
        return ": e' domenica, e la domenica e' fuori punta tutto il giorno"
    return ""


def prossimo_cambio(momento: datetime) -> datetime:
    """Quando cambia la fascia. Serve a dire «aspetta un'ora e costa meno».

    Si cerca in avanti ora per ora invece di ragionare sui bordi: le regole
    sono poche ma si incastrano (sabato, domenica, festivi, mezzanotte), e
    una funzione che le riattraversa non puo' dissentire da `fascia`, mentre
    una seconda copia delle regole prima o poi lo farebbe.
    """
    locale = ora_italiana(momento)
    adesso = fascia(locale)

    candidato = locale.replace(minute=0, second=0, microsecond=0)
    # Al massimo cinque giorni: fra un festivo e la domenica successiva non
    # c'e' mai piu' di tanto, e un limite evita di cercare per sempre se un
    # giorno le regole diventassero contraddittorie.
    for _ in range(24 * 5):
        candidato += timedelta(hours=1)
        if fascia(candidato) != adesso:
            return candidato
    return candidato
