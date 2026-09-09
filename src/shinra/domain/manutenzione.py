"""Le scadenze che tornano: filtri, revisione, bollo, garanzie.

Una scadenza non e' un promemoria. Il promemoria suona una volta e finisce;
la scadenza **ricomincia**: fatto il cambio filtri, ne nasce un altro fra sei
mesi. Se ricominciasse contando dalla data prevista invece che da quella in
cui si e' fatto davvero, ogni ritardo si accumulerebbe — un cambio filtri
fatto con due mesi di ritardo terrebbe il calendario indietro per sempre.
Qui si conta da quando e' stata fatta.

L'altra cosa che questo modulo tiene ferma: **una scadenza passata resta
passata.** Non si sposta in avanti da sola per far tornare i conti; se il
bollo era a marzo e siamo a maggio, il bollo e' scaduto, e va detto.

Qui non si scrive niente e non si programma niente: entrano una data e una
ricorrenza, esce la prossima.

Riferimento: issue #25.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional, Sequence

GIORNI = "giorni"
MESI = "mesi"
ANNI = "anni"

UNITA = (GIORNI, MESI, ANNI)

NOMI_UNITA = {GIORNI: "giorni", MESI: "mesi", ANNI: "anni"}

# Da quanti giorni prima una scadenza vale la pena nominarla. Un bollo
# annunciato il giorno stesso non serve a niente; annunciato tre mesi prima
# diventa rumore e si smette di ascoltarlo.
PREAVVISO_PREDEFINITO = 7


@dataclass(frozen=True)
class Scadenza:
    identificativo: str
    titolo: str
    prossima: date
    ogni: int = 0
    unita: str = MESI
    preavviso: int = PREAVVISO_PREDEFINITO
    documento: str = ""

    @property
    def ricorrente(self) -> bool:
        return self.ogni > 0

    def giorni_mancanti(self, oggi: Optional[date] = None) -> int:
        return (self.prossima - (oggi or date.today())).days

    def scaduta(self, oggi: Optional[date] = None) -> bool:
        return self.giorni_mancanti(oggi) < 0

    def in_arrivo(self, oggi: Optional[date] = None) -> bool:
        return 0 <= self.giorni_mancanti(oggi) <= self.preavviso


def _aggiungi_mesi(partenza: date, quanti: int) -> date:
    """Il 31 gennaio piu' un mese e' il 28 febbraio, non il 3 marzo.

    Una scadenza che scivola in avanti di qualche giorno a ogni rinnovo, dopo
    dieci anni e' in un altro mese.
    """
    indice = partenza.month - 1 + quanti
    anno = partenza.year + indice // 12
    mese = indice % 12 + 1

    giorno = partenza.day
    while giorno > 0:
        try:
            return date(anno, mese, giorno)
        except ValueError:
            giorno -= 1
    return date(anno, mese, 1)


def prossima_dopo(fatta_il: date, ogni: int, unita: str) -> Optional[date]:
    """La prossima scadenza, contata da quando e' stata fatta davvero.

    `None` per le scadenze che non tornano — una garanzia scade una volta
    sola, e riproporla ogni due anni sarebbe una bugia.
    """
    if ogni <= 0:
        return None
    if unita == GIORNI:
        return fatta_il + timedelta(days=ogni)
    if unita == ANNI:
        return _aggiungi_mesi(fatta_il, 12 * ogni)
    return _aggiungi_mesi(fatta_il, ogni)


def da_segnalare(
    scadenze: Iterable[Scadenza], oggi: Optional[date] = None
) -> tuple[list[Scadenza], list[Scadenza]]:
    """Quelle scadute e quelle in arrivo, separate.

    Sono due cose diverse da dire: «il bollo scade fra tre giorni» e «il bollo
    e' scaduto due mesi fa» richiedono reazioni diverse, e metterle nello
    stesso elenco le confonde.
    """
    giorno = oggi or date.today()
    scadute = [s for s in scadenze if s.scaduta(giorno)]
    in_arrivo = [s for s in scadenze if s.in_arrivo(giorno)]
    return (
        sorted(scadute, key=lambda s: s.prossima),
        sorted(in_arrivo, key=lambda s: s.prossima),
    )


def descrivi(scadenza: Scadenza, oggi: Optional[date] = None) -> str:
    giorni = scadenza.giorni_mancanti(oggi)

    if giorni < 0:
        quanto = -giorni
        detto = "ieri" if quanto == 1 else f"{quanto} giorni fa"
        return f"{scadenza.titolo}: era scaduta {detto}"
    if giorni == 0:
        return f"{scadenza.titolo}: scade oggi"
    if giorni == 1:
        return f"{scadenza.titolo}: scade domani"
    return f"{scadenza.titolo}: scade fra {giorni} giorni"


def riassumi(scadenze: Sequence[Scadenza], oggi: Optional[date] = None) -> str:
    scadute, in_arrivo = da_segnalare(scadenze, oggi)

    if not scadute and not in_arrivo:
        return "Non c'e' niente in scadenza."

    pezzi = []
    if scadute:
        pezzi.append("Scadute: " + "; ".join(descrivi(s, oggi) for s in scadute))
    if in_arrivo:
        pezzi.append("In arrivo: " + "; ".join(descrivi(s, oggi) for s in in_arrivo))
    return ". ".join(pezzi) + "."
