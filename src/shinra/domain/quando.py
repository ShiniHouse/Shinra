"""«Domani mattina», «sabato», «fra due giorni»: da come si dice a quando e'.

Serve ai promemoria (#92) e alle scadenze. E' puro: entra una frase, un momento
di riferimento e il **lessico di una lingua**; esce un istante — oppure `None`,
che e' la parte importante.

**`None` non e' un fallimento da nascondere: e' la risposta.** Il difetto che
questo modulo esiste per riparare era proprio questo — un tool che, non
capendo l'orario, rispondeva «Promemoria salvato» e non salvava niente. Chi
non sa quando deve suonare la sveglia non la mette a caso: chiede. Per questo
qui non c'e' nessun ripiego a «fra un'ora» o «domani alle 9» quando la frase
non lo dice.

**Nessuna parola di nessuna lingua sta qui** (#205). I numeri in lettere, le
unita' di tempo, i nomi dei giorni e dei mesi, «domani», «stasera», le
preposizioni stanno nel file della lingua (`intenti/lingue/*.yaml`, sezione
`tempo`) e arrivano come `Lessico`. Il dominio non importa il caricatore: la
lingua e' un argomento, come per i resto degli schemi. Qui restano le **ore**
di default, che non sono parole: chi dice «domani mattina» un'ora la sta
dicendo, solo non con un numero, e le nove sono il momento in cui una giornata
comincia per chi deve ricordarsi qualcosa.

Riferimento: issue #92, #205.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Mapping, Optional

# Le ore in cui cade un momento della giornata detto a parole. Non sono
# arbitrarie: sono l'ora in cui una persona che dice «in mattinata» si
# aspetta di essere disturbata. Il file della lingua dice **quali parole**
# indicano ciascun momento; qui si dice a che ora cade.
ORE_DEI_MOMENTI: dict[str, time] = {
    "morning": time(9, 0),
    "noon": time(12, 0),
    "afternoon": time(15, 0),
    "evening": time(20, 0),
    "night": time(22, 0),
}

# Quando si dice solo un giorno, senza momento.
ORA_PREDEFINITA = ORE_DEI_MOMENTI["morning"]

UNITA = ("minutes", "hours", "days", "weeks", "months")


@dataclass(frozen=True)
class Lessico:
    """Il modo in cui una lingua dice il tempo, compilato.

    Si costruisce da un dizionario con `compila`, che dice **per nome** cosa
    manca: un lessico a meta' farebbe capire male una frase senza dirlo.
    """

    numeri: Mapping[str, int]
    momenti: Mapping[str, time]  # parola -> ora
    pasti: frozenset
    prima_dei_pasti: str
    giorni_della_settimana: tuple  # lunedi..domenica, senza accenti
    mesi: Mapping[str, int]
    today: str
    tomorrow: str
    day_after_tomorrow: str
    giorno_prossimo: str  # con {giorno}
    fra: str
    unita: Mapping[str, str]
    mezz_ora: str
    alle: str
    e_mezza: Optional[str]
    dopo_mezzogiorno: str
    date: tuple  # espressioni compilate con (?P<giorno>), (?P<mese>) o (?P<mese_num>)
    espressioni: tuple  # da togliere dal testo di un promemoria
    servizio_finale: str
    servizio_iniziale: Optional[str]
    frasi: Mapping[str, str]

    @property
    def numero(self) -> str:
        return r"(\d+|" + "|".join(sorted(self.numeri, key=len, reverse=True)) + r")"

    def quantita(self, parola: str) -> Optional[int]:
        if parola.isdigit():
            return int(parola)
        return self.numeri.get(parola)


class LessicoIncompleto(ValueError):
    """Il file di una lingua a cui manca una voce del tempo."""


_CHIAVI = (
    "numeri",
    "momenti",
    "pasti",
    "prima_dei_pasti",
    "settimana",
    "mesi",
    "word_today",
    "word_tomorrow",
    "word_day_after_tomorrow",
    "next_weekday",
    "fra",
    "unita",
    "mezz_ora",
    "alle",
    "dopo_mezzogiorno",
    "date",
    "extra",
    "servizio_finale",
    "frasi",
)
_FRASI = ("today", "tomorrow", "day_after_tomorrow", "weekday", "date")


def normalizza(testo: str) -> str:
    """Minuscolo e senza accenti.

    «Lunedì», «lunedi» e «LUNEDI'» sono la stessa parola detta da tastiere
    diverse, e chi parla all'Echo non mette gli accenti perche' non scrive
    affatto: il riconoscimento vocale li mette come gli pare.
    """
    piatto = unicodedata.normalize("NFD", (testo or "").lower())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    return " ".join(piatto.replace("'", " ").split())


def compila(dati: Mapping[str, Any]) -> Lessico:
    """Dal dizionario di una lingua al `Lessico`, o `LessicoIncompleto` con tutte le voci che mancano."""
    mancanti = [k for k in _CHIAVI if not dati.get(k)]
    mancanti += [f"unita.{u}" for u in UNITA if not (dati.get("unita") or {}).get(u)]
    mancanti += [f"momenti.{m}" for m in ORE_DEI_MOMENTI if not (dati.get("momenti") or {}).get(m)]
    mancanti += [f"frasi.{f}" for f in _FRASI if not (dati.get("frasi") or {}).get(f)]
    if len(dati.get("settimana") or ()) != 7:
        mancanti.append("settimana (sette giorni)")
    if len(dati.get("mesi") or ()) != 12:
        mancanti.append("mesi (dodici)")
    if mancanti:
        raise LessicoIncompleto(f"tempo: mancano {', '.join(sorted(set(mancanti)))}")

    momenti = {
        normalizza(parola): ORE_DEI_MOMENTI[nome]
        for nome, parole in dati["momenti"].items()
        if nome in ORE_DEI_MOMENTI
        for parola in parole
    }
    mesi = {normalizza(m): i for i, m in enumerate(dati["mesi"], start=1)}
    giorni = tuple(normalizza(g) for g in dati["settimana"])
    nomi_mesi = "|".join(mesi)
    date = tuple(re.compile(p.replace("@MESI@", nomi_mesi)) for p in dati["date"])
    parole_dei_momenti = "|".join(m for m in momenti if normalizza(m) not in dati["pasti"])
    pasti = frozenset(normalizza(p) for p in dati["pasti"])
    numeri = {normalizza(k): int(v) for k, v in dati["numeri"].items()}
    cifre_e_parole = r"(?:\d+|" + "|".join(sorted(numeri, key=len, reverse=True)) + ")"
    con_prossimo = "|".join(dati["next_weekday"].format(giorno=g) for g in giorni)

    def intera(modello: str) -> str:
        return rf"\b(?:{modello})\b"

    ora_alle = rf"{dati['alle']}\s+\d{{1,2}}(?:[:.]\d{{2}})?"
    espressioni = (
        intera(rf"{dati['fra']}\s+{cifre_e_parole}\s*(?:{'|'.join(dati['unita'].values())})"),
        intera(dati["mezz_ora"]),
        intera(ora_alle + (rf"(?:\s+{dati['e_mezza']})?" if dati.get("e_mezza") else "")),
        intera(dati["dopo_mezzogiorno"]),
        *(p.replace("@MESI@", nomi_mesi) for p in dati["date"]),
        intera(rf"{con_prossimo}|{'|'.join(giorni)}"),
        intera(rf"{dati['word_day_after_tomorrow']}|{dati['word_tomorrow']}|{dati['word_today']}"),
        intera(rf"{dati['prima_dei_pasti']}\s+(?:{'|'.join(sorted(pasti))})"),
        intera(parole_dei_momenti),
        *dati["extra"],
    )
    return Lessico(
        numeri=numeri,
        momenti=momenti,
        pasti=pasti,
        prima_dei_pasti=str(dati["prima_dei_pasti"]),
        giorni_della_settimana=giorni,
        mesi=mesi,
        today=str(dati["word_today"]),
        tomorrow=str(dati["word_tomorrow"]),
        day_after_tomorrow=str(dati["word_day_after_tomorrow"]),
        giorno_prossimo=str(dati["next_weekday"]),
        fra=str(dati["fra"]),
        unita={u: str(dati["unita"][u]) for u in UNITA},
        mezz_ora=str(dati["mezz_ora"]),
        alle=str(dati["alle"]),
        e_mezza=str(dati["e_mezza"]) if dati.get("e_mezza") else None,
        dopo_mezzogiorno=str(dati["dopo_mezzogiorno"]),
        date=date,
        espressioni=espressioni,
        servizio_finale=str(dati["servizio_finale"]),
        servizio_iniziale=str(dati["servizio_iniziale"]) if dati.get("servizio_iniziale") else None,
        frasi={k: str(v) for k, v in dati["frasi"].items()},
    )


def _con_ora(giorno: datetime, orario: time) -> datetime:
    return giorno.replace(hour=orario.hour, minute=orario.minute, second=0, microsecond=0)


def _momento_detto(testo: str, lessico: Lessico) -> Optional[time]:
    for parola, orario in lessico.momenti.items():
        if parola in lessico.pasti:
            # Serve la preposizione: «dopo cena» si', «cena con Marco» no.
            if re.search(rf"\b{lessico.prima_dei_pasti}\s+{parola}\b", testo):
                return orario
            continue
        if re.search(rf"\b{parola}\b", testo):
            return orario
    return None


def _ora_esplicita(testo: str, lessico: Lessico) -> Optional[time]:
    """«alle 18», «alle 17:30», «alle 8 e mezza»."""
    trovata = re.search(rf"\b{lessico.alle}\s+(\d{{1,2}})(?:[:.](\d{{2}}))?\b", testo)
    if not trovata:
        return None

    ore = int(trovata.group(1))
    minuti = int(trovata.group(2) or 0)

    if lessico.e_mezza and re.search(rf"\b{lessico.alle}\s+{ore}\b\s+{lessico.e_mezza}\b", testo):
        minuti = 30

    if ore > 23 or minuti > 59:
        return None

    # «alle 8 di sera» sono le 20. Senza indicazione si prende il numero
    # com'e': chi dice «alle 8» a mezzogiorno intende domani mattina, e ci
    # pensa il confronto con adesso.
    if ore < 12 and re.search(rf"\b{lessico.dopo_mezzogiorno}\b", testo):
        ore += 12

    return time(ore, minuti)


def quando(testo: str, adesso: Optional[datetime] = None, *, lessico: Lessico) -> Optional[datetime]:
    """L'istante che la frase indica, o `None` se non lo indica.

    `None` e' una risposta legittima e va riferita a chi ha chiesto: e'
    meglio domandare «a che ora?» che mettere una sveglia a caso.
    """
    ora_zero = adesso or datetime.now()
    piatto = normalizza(testo)
    if not piatto:
        return None

    orario = _ora_esplicita(piatto, lessico)
    momento = _momento_detto(piatto, lessico)

    # 1. «fra venti minuti», «tra due giorni», «fra una settimana»
    gruppi = "|".join(f"(?P<{u}>{lessico.unita[u]})" for u in UNITA)
    fra = re.search(rf"\b{lessico.fra}\s+(?P<n>{lessico.numero[1:-1]})\s*(?:{gruppi})\b", piatto)
    if fra:
        quanti = lessico.quantita(fra.group("n"))
        if quanti is None:
            return None
        if fra.group("minutes"):
            return (ora_zero + timedelta(minutes=quanti)).replace(second=0, microsecond=0)
        if fra.group("hours"):
            return (ora_zero + timedelta(hours=quanti)).replace(second=0, microsecond=0)
        if fra.group("weeks"):
            giorno = ora_zero + timedelta(weeks=quanti)
        elif fra.group("months"):
            giorno = ora_zero + timedelta(days=30 * quanti)
        else:
            giorno = ora_zero + timedelta(days=quanti)
        return _con_ora(giorno, orario or momento or ORA_PREDEFINITA)

    # 2. «fra mezz'ora»
    if re.search(rf"\b{lessico.mezz_ora}\b", piatto):
        return (ora_zero + timedelta(minutes=30)).replace(second=0, microsecond=0)

    # 3. I giorni con un nome: oggi, domani, dopodomani
    if re.search(rf"\b{lessico.day_after_tomorrow}\b", piatto):
        return _con_ora(ora_zero + timedelta(days=2), orario or momento or ORA_PREDEFINITA)

    if re.search(rf"\b{lessico.tomorrow}\b", piatto):
        return _con_ora(ora_zero + timedelta(days=1), orario or momento or ORA_PREDEFINITA)

    # 4. Un giorno della settimana: «sabato», «lunedi prossimo»
    for indice, nome in enumerate(lessico.giorni_della_settimana):
        if not re.search(rf"\b{nome}\b", piatto):
            continue
        avanti = (indice - ora_zero.weekday()) % 7
        # «Sabato» detto di sabato significa fra una settimana, non adesso;
        # e «sabato prossimo» lo dice esplicitamente.
        if avanti == 0 or re.search(lessico.giorno_prossimo.format(giorno=nome), piatto):
            avanti = avanti or 7
        return _con_ora(ora_zero + timedelta(days=avanti), orario or momento or ORA_PREDEFINITA)

    # 5. Una data: «il 15», «il 15 marzo», «il 15/3»
    for modello in lessico.date:
        data = modello.search(piatto)
        if not data:
            continue
        giorno_del_mese = int(data.group("giorno"))
        gruppi_data = data.groupdict()
        mese = lessico.mesi.get(gruppi_data.get("mese") or "") or (
            int(gruppi_data["mese_num"]) if gruppi_data.get("mese_num") else ora_zero.month
        )
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


def descrivi(momento: datetime, adesso: Optional[datetime] = None, *, lessico: Lessico) -> str:
    """«domani alle 9:00», «sabato alle 20:00»: come ridirlo a chi ha chiesto.

    Serve a far verificare la comprensione: se l'assistente ha capito
    «sabato» e la persona intendeva oggi, deve poterlo sentire subito.
    """
    ora_zero = adesso or datetime.now()
    giorni = (momento.date() - ora_zero.date()).days
    ora = momento.strftime("%H:%M")
    frasi = lessico.frasi

    if giorni == 0:
        return frasi["today"].format(ora=ora)
    if giorni == 1:
        return frasi["tomorrow"].format(ora=ora)
    if giorni == 2:
        return frasi["day_after_tomorrow"].format(ora=ora)
    if 3 <= giorni <= 6:
        return frasi["weekday"].format(giorno=lessico.giorni_della_settimana[momento.weekday()], ora=ora)
    return frasi["date"].format(data=momento.strftime("%d/%m"), ora=ora)


def separa(testo: str, *, lessico: Lessico) -> tuple[str, Optional[datetime]]:
    """Da «chiamare il dentista domani mattina» a («chiamare il dentista»,
    domani alle 9).

    Il testo si ripulisce dall'espressione di tempo perche' un promemoria che
    suona dicendo «chiamare il dentista domani» e' fuorviante: quando suona,
    quel domani e' diventato oggi.
    """
    momento = quando(testo, lessico=lessico)
    ripulito = normalizza(testo)

    for espressione in lessico.espressioni:
        ripulito = re.sub(espressione, " ", ripulito)

    # Le parole di servizio rimaste appese: «ricordami di ... di», «per».
    ripulito = re.sub(rf"\b{lessico.servizio_finale}\s*$", " ", ripulito.strip())
    if lessico.servizio_iniziale:
        ripulito = re.sub(rf"^\s*{lessico.servizio_iniziale}\b", " ", ripulito)
    ripulito = " ".join(ripulito.split()).strip(" ,.;:")

    return ripulito, momento
