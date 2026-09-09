"""«Cosa ho oggi»: eventi, giornate, e la differenza fra le due.

Home Assistant restituisce gli eventi di un calendario in una forma che va
letta con attenzione: l'inizio e la fine sono `date` **oppure** `dateTime`, e
la differenza non e' un dettaglio di formato — e' la differenza fra «il 14
settembre» e «il 14 settembre alle 15:30». Un evento di giornata intera letto
come se avesse un'ora finisce alle 00:00 e sembra passato per tutto il giorno
in cui accade.

Qui non si chiama niente: entrano gli eventi come li manda Home Assistant,
esce cio' che si puo' dire a una persona.

Riferimento: issue #25.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Optional, Sequence

DOMINIO_HA = "calendar"


@dataclass(frozen=True)
class Evento:
    titolo: str
    inizio: datetime
    fine: Optional[datetime] = None
    tutto_il_giorno: bool = False
    luogo: str = ""
    calendario: str = ""

    @property
    def giorno(self) -> date:
        return self.inizio.date()


def _istante(grezzo: Any) -> tuple[Optional[datetime], bool]:
    """Da `{"date": "2026-09-14"}` o `{"dateTime": "..."}` a un istante.

    Il secondo valore dice se e' una giornata intera, ed e' la parte che non
    si puo' perdere: un evento di giornata intera trattato come un evento
    delle 00:00 risulta gia' passato per tutte le ore in cui sta accadendo.
    """
    if isinstance(grezzo, str):
        grezzo = {"dateTime": grezzo} if "T" in grezzo else {"date": grezzo}
    if not isinstance(grezzo, dict):
        return None, False

    solo_data = grezzo.get("date")
    if solo_data:
        try:
            return datetime.combine(date.fromisoformat(str(solo_data)), time(0, 0)), True
        except ValueError:
            return None, True

    con_ora = grezzo.get("dateTime")
    if con_ora:
        try:
            letto = datetime.fromisoformat(str(con_ora).replace("Z", "+00:00"))
            return (letto.astimezone().replace(tzinfo=None) if letto.tzinfo else letto), False
        except ValueError:
            return None, False

    return None, False


def da_home_assistant(grezzi: Iterable[dict[str, Any]], calendario: str = "") -> list[Evento]:
    eventi: list[Evento] = []
    for grezzo in grezzi or []:
        inizio, tutto_il_giorno = _istante(grezzo.get("start"))
        if inizio is None:
            continue
        fine, _ = _istante(grezzo.get("end"))
        eventi.append(
            Evento(
                titolo=str(grezzo.get("summary") or "Impegno").strip(),
                inizio=inizio,
                fine=fine,
                tutto_il_giorno=tutto_il_giorno,
                luogo=str(grezzo.get("location") or "").strip(),
                calendario=calendario,
            )
        )
    return ordina(eventi)


def ordina(eventi: Iterable[Evento]) -> list[Evento]:
    """Prima le giornate intere, poi gli altri in ordine di ora.

    Chi chiede «cosa ho oggi» vuole sapere prima che e' il compleanno di
    qualcuno, e poi che alle 15 c'e' il dentista.
    """
    return sorted(eventi, key=lambda e: (e.inizio.date(), not e.tutto_il_giorno, e.inizio))


def del_giorno(eventi: Iterable[Evento], giorno: date) -> list[Evento]:
    """Gli eventi che toccano questo giorno, anche se cominciati prima.

    Una vacanza dal 10 al 17 e' un impegno anche il 14, e un calendario che
    la mostra solo il 10 non risponde alla domanda «cosa ho oggi».
    """
    dentro: list[Evento] = []
    for evento in eventi:
        inizio = evento.inizio.date()
        fine = (evento.fine or evento.inizio).date()
        # Home Assistant chiude le giornate intere alla mezzanotte del giorno
        # dopo: un evento del 14 arriva come 14 → 15, e senza questa
        # correzione comparirebbe anche il 15.
        if evento.tutto_il_giorno and evento.fine is not None and fine > inizio:
            fine -= timedelta(days=1)
        if inizio <= giorno <= fine:
            dentro.append(evento)
    return ordina(dentro)


def descrivi(evento: Evento) -> str:
    if evento.tutto_il_giorno:
        base = f"{evento.titolo}, tutto il giorno"
    else:
        base = f"{evento.titolo} alle {evento.inizio.strftime('%H:%M')}"
    return f"{base} a {evento.luogo}" if evento.luogo else base


def riassumi(eventi: Sequence[Evento], quando_detto: str = "oggi") -> str:
    """La giornata come si racconta a voce."""
    if not eventi:
        return f"Non hai impegni {quando_detto}."

    if len(eventi) == 1:
        return f"{quando_detto.capitalize()} hai un impegno: {descrivi(eventi[0])}."

    elencati = "; ".join(descrivi(e) for e in eventi)
    return f"{quando_detto.capitalize()} hai {len(eventi)} impegni: {elencati}."
