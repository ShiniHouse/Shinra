"""A che ora sorge e tramonta il sole, secondo la casa.

Home Assistant lo sa gia': l'entita' `sun.sun` porta `next_rising` e
`next_setting`, che sono esattamente le due domande che si fanno qui. Questo
modulo le legge e basta — non calcola effemeridi, non ha bisogno della
latitudine, e non va su Internet.

Esiste per un difetto trovato misurando. `services/regole.riprogramma_tutte`
chiamava `prossimo_scatto` **senza** passare alba e tramonto; il dominio, che
giustamente non li inventa, rispondeva `None`; e il motore saltava la regola
senza dire niente. Il risultato e' che **nessuna regola all'alba o al tramonto
e' mai stata programmata**, da quando esiste la issue #27. Non se n'era accorto
nessuno perche' una regola che non scatta e una regola che non c'e' si
somigliano troppo, ed e' esattamente il difetto contro cui `perche_no` era
stato scritto — solo che qui succedeva un livello piu' sotto, dove nessuno
guardava.

Lo stesso `sun.sun` era gia' letto da `skills/simulazione.py`, con la sua
copia della lettura. Adesso la lettura e' una sola: due implementazioni dello
stesso attributo divergono, e la divergenza si vede come «la simulazione crede
che tramonti a un'ora e le regole a un'altra».

Riferimento: issue #27, issue #28.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

ENTITA = "sun.sun"

PROSSIMA_ALBA = "next_rising"
PROSSIMO_TRAMONTO = "next_setting"

# Quando `sun.sun` non c'e', un tramonto plausibile per l'Italia. Serve alla
# simulazione di presenza — che deve pur accendere qualcosa la sera, e per cui
# sbagliare di mezz'ora non ha nessuna conseguenza.
#
# Non serve alle regole, e non deve: programmare l'apertura delle tapparelle a
# un'ora inventata vorrebbe dire una casa che fa le cose al momento sbagliato
# senza che niente lo spieghi. Meglio non programmarla e dirlo.
ORA_DI_RIPIEGO = 19
MINUTO_DI_RIPIEGO = 30


@dataclass(frozen=True)
class Sole:
    """I due momenti, o `None` per quelli che non si sanno."""

    alba: Optional[datetime] = None
    tramonto: Optional[datetime] = None

    @property
    def conosciuto(self) -> bool:
        return self.alba is not None or self.tramonto is not None


def _momento(grezzo: Any) -> Optional[datetime]:
    """Un istante ISO di Home Assistant, nel fuso di casa.

    `None` quando non si capisce: un orario inventato e' peggio di un orario
    mancante, perche' il mancante si vede e l'inventato no.

    Non c'e' nessun controllo sul vuoto prima del `try`, e non e' una
    dimenticanza: ce n'era uno, e toglierlo non faceva fallire niente. Un
    attributo assente arriva qui come `None`, diventa la stringa «None», e
    `fromisoformat` la rifiuta esattamente come rifiuta «domani mattina».
    """
    try:
        return datetime.fromisoformat(str(grezzo).replace("Z", "+00:00")).astimezone()
    except (ValueError, TypeError):
        return None


def leggi(stato: Optional[Mapping[str, Any]]) -> Sole:
    """Alba e tramonto dallo stato di `sun.sun`.

    Un `Sole` vuoto quando l'entita' non c'e' — una casa senza integrazione
    del sole, o Home Assistant irraggiungibile — ed e' un'informazione, non un
    errore: chi chiama decide se rinunciare o ripiegare.
    """
    attributi = (stato or {}).get("attributes") or {}
    return Sole(
        alba=_momento(attributi.get(PROSSIMA_ALBA)),
        tramonto=_momento(attributi.get(PROSSIMO_TRAMONTO)),
    )


def dagli_stati(stati: Any) -> Sole:
    """Come `leggi`, ma pescando `sun.sun` da un elenco di stati."""
    for stato in stati or ():
        if (stato or {}).get("entity_id") == ENTITA:
            return leggi(stato)
    return Sole()


def tramonto_plausibile(adesso: datetime) -> datetime:
    """Un tramonto inventato, per chi puo' permetterselo.

    Solo la simulazione di presenza: vedi il commento su `ORA_DI_RIPIEGO`.
    """
    return adesso.replace(hour=ORA_DI_RIPIEGO, minute=MINUTO_DI_RIPIEGO, second=0, microsecond=0)
