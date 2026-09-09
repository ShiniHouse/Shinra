"""«Domani mattina», «sabato», «fra due giorni»: da come si dice a quando e'.

Serve ai promemoria (#92) e alle scadenze. E' puro: entra una frase e un
momento di riferimento, esce un istante — oppure `None`, che e' la parte
importante.

**`None` non e' un fallimento da nascondere: e' la risposta.** Il difetto che
questo modulo esiste per riparare era proprio questo — un tool che, non
capendo l'orario, rispondeva «Promemoria salvato» e non salvava niente. Chi
non sa quando deve suonare la sveglia non la mette a caso: chiede. Per questo
qui non c'e' nessun ripiego a «fra un'ora» o «domani alle 9» quando la frase
non lo dice.

Le ore di default, invece, ci sono e sono dichiarate: chi dice «domani
mattina» un'ora la sta dicendo, solo non con un numero. Chi dice «domani» e
basta intende la giornata, e le nove del mattino sono il momento in cui una
giornata comincia per chi deve ricordarsi qualcosa.

Riferimento: issue #92.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, time, timedelta
from typing import Optional

# Le ore in cui cade un momento della giornata detto a parole. Non sono
# arbitrarie: sono l'ora in cui una persona che dice «in mattinata» si
# aspetta di essere disturbata.
MATTINA = time(9, 0)
MEZZOGIORNO = time(12, 0)
POMERIGGIO = time(15, 0)
SERA = time(20, 0)
NOTTE = time(22, 0)

# Quando si dice solo un giorno, senza momento.
ORA_PREDEFINITA = MATTINA

# «Cena» e «pranzo» sono insieme un pasto e un'ora, e la differenza la fa
# la preposizione: «dopo cena» e' un'ora, «cena con Marco» e' il titolo di un
# impegno. Senza questa distinzione «segna cena con Marco» diventava
# l'impegno «con Marco» alle venti — il titolo mangiato dall'orario.
AMBIGUI = frozenset({"pranzo", "cena"})
PRIMA_DEGLI_AMBIGUI = r"(?:a|per|dopo|verso|prima\s+di|entro)"

MOMENTI: dict[str, time] = {
    "mattina": MATTINA,
    "mattino": MATTINA,
    "mattinata": MATTINA,
    "stamattina": MATTINA,
    "stamane": MATTINA,
    "mezzogiorno": MEZZOGIORNO,
    "pranzo": MEZZOGIORNO,
    "pomeriggio": POMERIGGIO,
    "sera": SERA,
    "serata": SERA,
    "stasera": SERA,
    "cena": SERA,
    "notte": NOTTE,
    "stanotte": NOTTE,
}

GIORNI_SETTIMANA: dict[str, int] = {
    "lunedi": 0,
    "martedi": 1,
    "mercoledi": 2,
    "giovedi": 3,
    "venerdi": 4,
    "sabato": 5,
    "domenica": 6,
}

MESI: dict[str, int] = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

NUMERI_A_PAROLE: dict[str, int] = {
    "un": 1,
    "uno": 1,
    "una": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
    "sei": 6,
    "sette": 7,
    "otto": 8,
    "nove": 9,
    "dieci": 10,
    "quindici": 15,
    "venti": 20,
    "trenta": 30,
    "quaranta": 40,
    "sessanta": 60,
}

_NUMERO = r"(\d+|" + "|".join(sorted(NUMERI_A_PAROLE, key=len, reverse=True)) + r")"


def normalizza(testo: str) -> str:
    """Minuscolo e senza accenti.

    «Lunedì», «lunedi» e «LUNEDI'» sono la stessa parola detta da tastiere
    diverse, e chi parla all'Echo non mette gli accenti perche' non scrive
    affatto: il riconoscimento vocale li mette come gli pare.
    """
    piatto = unicodedata.normalize("NFD", (testo or "").lower())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    return " ".join(piatto.replace("'", " ").split())


def _quantita(parola: str) -> Optional[int]:
    if parola.isdigit():
        return int(parola)
    return NUMERI_A_PAROLE.get(parola)


def _con_ora(giorno: datetime, orario: time) -> datetime:
    return giorno.replace(hour=orario.hour, minute=orario.minute, second=0, microsecond=0)


def _momento_detto(testo: str) -> Optional[time]:
    for parola, orario in MOMENTI.items():
        if parola in AMBIGUI:
            # Serve la preposizione: «dopo cena» si', «cena con Marco» no.
            if re.search(rf"\b{PRIMA_DEGLI_AMBIGUI}\s+{parola}\b", testo):
                return orario
            continue
        if re.search(rf"\b{parola}\b", testo):
            return orario
    return None


def _ora_esplicita(testo: str) -> Optional[time]:
    """«alle 18», «alle 17:30», «alle 8 e mezza»."""
    trovata = re.search(r"\balle\s+(\d{1,2})(?:[:.](\d{2}))?\b", testo)
    if not trovata:
        trovata = re.search(r"\ball[ae]\s+(\d{1,2})(?:[:.](\d{2}))?\b", testo)
    if not trovata:
        return None

    ore = int(trovata.group(1))
    minuti = int(trovata.group(2) or 0)

    if re.search(rf"\balle\s+{ore}\b\s+e\s+mezza\b", testo):
        minuti = 30

    if ore > 23 or minuti > 59:
        return None

    # «alle 8 di sera» sono le 20. Senza indicazione si prende il numero
    # com'e': chi dice «alle 8» a mezzogiorno intende domani mattina, e ci
    # pensa il confronto con adesso.
    if ore < 12 and re.search(r"\b(di sera|del pomeriggio|di pomeriggio)\b", testo):
        ore += 12

    return time(ore, minuti)


def quando(testo: str, adesso: Optional[datetime] = None) -> Optional[datetime]:
    """L'istante che la frase indica, o `None` se non lo indica.

    `None` e' una risposta legittima e va riferita a chi ha chiesto: e'
    meglio domandare «a che ora?» che mettere una sveglia a caso.
    """
    ora_zero = adesso or datetime.now()
    piatto = normalizza(testo)
    if not piatto:
        return None

    orario = _ora_esplicita(piatto)
    momento = _momento_detto(piatto)

    # 1. «fra venti minuti», «tra due giorni», «fra una settimana»
    fra = re.search(
        rf"\b(?:tra|fra|entro)\s+{_NUMERO}\s*(minut\w*|or[ae]|giorn\w*|settiman\w*|mes\w*)\b", piatto
    )
    if fra:
        quanti = _quantita(fra.group(1))
        if quanti is None:
            return None
        unita = fra.group(2)
        if unita.startswith("minut"):
            return (ora_zero + timedelta(minutes=quanti)).replace(second=0, microsecond=0)
        if unita.startswith("or"):
            return (ora_zero + timedelta(hours=quanti)).replace(second=0, microsecond=0)
        if unita.startswith("settiman"):
            giorno = ora_zero + timedelta(weeks=quanti)
        elif unita.startswith("mes"):
            giorno = ora_zero + timedelta(days=30 * quanti)
        else:
            giorno = ora_zero + timedelta(days=quanti)
        return _con_ora(giorno, orario or momento or ORA_PREDEFINITA)

    # 2. «fra mezz'ora»
    if re.search(r"\b(?:tra|fra)\s+mezz\s*ora\b", piatto):
        return (ora_zero + timedelta(minutes=30)).replace(second=0, microsecond=0)

    # 3. I giorni con un nome: oggi, domani, dopodomani
    if re.search(r"\bdopodomani\b", piatto):
        return _con_ora(ora_zero + timedelta(days=2), orario or momento or ORA_PREDEFINITA)

    if re.search(r"\bdomani\b", piatto):
        return _con_ora(ora_zero + timedelta(days=1), orario or momento or ORA_PREDEFINITA)

    # 4. Un giorno della settimana: «sabato», «lunedi prossimo»
    for nome, indice in GIORNI_SETTIMANA.items():
        if not re.search(rf"\b{nome}\b", piatto):
            continue
        avanti = (indice - ora_zero.weekday()) % 7
        # «Sabato» detto di sabato significa fra una settimana, non adesso;
        # e «sabato prossimo» lo dice esplicitamente.
        if avanti == 0 or re.search(rf"\b{nome}\s+prossimo\b", piatto):
            avanti = avanti or 7
        candidato = _con_ora(ora_zero + timedelta(days=avanti), orario or momento or ORA_PREDEFINITA)
        return candidato

    # 5. Una data: «il 15», «il 15 marzo», «il 15/3»
    data = re.search(
        r"\b(?:il|per il|entro il)\s+(\d{1,2})(?:\s+(" + "|".join(MESI) + r")|[/-](\d{1,2}))?\b", piatto
    )
    if data:
        giorno_del_mese = int(data.group(1))
        mese = MESI.get(data.group(2) or "") or (int(data.group(3)) if data.group(3) else ora_zero.month)
        risultato = _prossima_data(ora_zero, giorno_del_mese, mese)
        if risultato is None:
            return None
        return _con_ora(risultato, orario or momento or ORA_PREDEFINITA)

    # 6. Solo un'ora, o solo un momento della giornata: e' oggi, se non e'
    #    gia' passato; altrimenti domani. Chi dice «alle 8» alle 9 di sera
    #    intende domattina.
    scelto = orario or momento
    if scelto is not None:
        candidato = _con_ora(ora_zero, scelto)
        if candidato <= ora_zero:
            candidato += timedelta(days=1)
        return candidato

    return None


def _prossima_data(adesso: datetime, giorno: int, mese: int) -> Optional[datetime]:
    """La prossima occorrenza di questo giorno e mese, quest'anno o il
    prossimo. `None` se la data non esiste (il 31 di febbraio)."""
    for anno in (adesso.year, adesso.year + 1):
        try:
            candidato = adesso.replace(year=anno, month=mese, day=giorno)
        except ValueError:
            continue
        if candidato.date() >= adesso.date():
            return candidato
    return None


def descrivi(momento: datetime, adesso: Optional[datetime] = None) -> str:
    """«domani alle 9:00», «sabato alle 20:00»: come ridirlo a chi ha chiesto.

    Serve a far verificare la comprensione: se l'assistente ha capito
    «sabato» e la persona intendeva oggi, deve poterlo sentire subito.
    """
    ora_zero = adesso or datetime.now()
    giorni = (momento.date() - ora_zero.date()).days
    orario = momento.strftime("alle %H:%M")

    if giorni == 0:
        return f"oggi {orario}"
    if giorni == 1:
        return f"domani {orario}"
    if giorni == 2:
        return f"dopodomani {orario}"
    if 3 <= giorni <= 6:
        nomi = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
        return f"{nomi[momento.weekday()]} {orario}"
    return momento.strftime("il %d/%m ") + orario


# Le espressioni di tempo, per toglierle dal testo del promemoria. Chi dice
# «ricordami di chiamare il dentista domani mattina» vuole che il promemoria
# dica «chiamare il dentista», non «chiamare il dentista domani mattina»:
# quando suona, il «domani» e' gia' diventato oggi ed e' fuorviante.
_ESPRESSIONI = [
    r"\b(?:tra|fra|entro)\s+" + _NUMERO + r"\s*(?:minut\w*|or[ae]|giorn\w*|settiman\w*|mes\w*)\b",
    r"\b(?:tra|fra)\s+mezz\s*ora\b",
    r"\ball[ae]\s+\d{1,2}(?:[:.]\d{2})?(?:\s+e\s+mezza)?\b",
    r"\b(?:di sera|del pomeriggio|di pomeriggio|di mattina|del mattino)\b",
    r"\b(?:il|per il|entro il)\s+\d{1,2}(?:\s+(?:" + "|".join(MESI) + r")|[/-]\d{1,2})?\b",
    r"\b(?:" + "|".join(GIORNI_SETTIMANA) + r")(?:\s+prossimo)?\b",
    r"\b(?:dopodomani|domani|oggi)\b",
    r"\b" + PRIMA_DEGLI_AMBIGUI + r"\s+(?:" + "|".join(sorted(AMBIGUI)) + r")\b",
    r"\b(?:" + "|".join(m for m in MOMENTI if m not in AMBIGUI) + r")\b",
    r"\bquesta\s+(?:mattina|sera|notte)\b",
    r"\bnel\s+pomeriggio\b",
    r"\bin\s+(?:mattinata|serata)\b",
]


def separa(testo: str) -> tuple[str, Optional[datetime]]:
    """Da «chiamare il dentista domani mattina» a («chiamare il dentista»,
    domani alle 9).

    Il testo si ripulisce dall'espressione di tempo perche' un promemoria che
    suona dicendo «chiamare il dentista domani» e' fuorviante: quando suona,
    quel domani e' diventato oggi.
    """
    momento = quando(testo)
    ripulito = normalizza(testo)

    for espressione in _ESPRESSIONI:
        ripulito = re.sub(espressione, " ", ripulito)

    # Le parole di servizio rimaste appese: «ricordami di ... di», «per».
    ripulito = re.sub(r"\b(?:di|a|per|che|devo|dovrei)\s*$", " ", ripulito.strip())
    ripulito = " ".join(ripulito.split()).strip(" ,.;:")

    return ripulito, momento
