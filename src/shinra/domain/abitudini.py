"""Le abitudini, contate dal codice e non indovinate dal modello (#261).

Una persona che accende la stessa luce alla stessa ora per quattro giorni su quattordici ha un'abitudine: lo dice il registro,
non un modello che «ha l'impressione». Questo modulo conta; il modello, se c'e', al piu' la racconta (e non e' mai lui a decidere
che esiste). Il risultato e' una **proposta con le prove**: i giorni in cui e' successo davvero.

Cosa non diventa mai un'abitudine, per costruzione:

- le azioni di **sola lettura** (meteo, stato, liste): non c'e' niente da automatizzare;
- le azioni **sensibili** (serrature, allarme, garage, script): `sensibilita.classifica` le dichiara tali e qui non entrano
  nemmeno come proposta: un'abitudine «apri la porta alle otto» non si propone, si lascia alla persona;
- le azioni **fallite**: un tentativo andato a vuoto non e' un'abitudine;
- le azioni **senza attore** (routine, regole): sono gia' automazioni, non c'e' una persona di cui contare le abitudini;
- l'azione di un profilo non conta per un altro: ogni profilo ha le sue.

Puro: nessun database, nessuna rete. Gli orari arrivano gia' nel fuso di casa.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Optional

from shinra.domain import sensibilita

FINESTRA_GIORNI = 14
MINIMO_GIORNI = 4
FINESTRA_MINUTI = 60
ARROTONDAMENTO_MINUTI = 5
ABITUDINI_MASSIME = 5

# Gli strumenti che *fanno* qualcosa in casa. Tutto il resto (meteo, stato, liste, ricerche) non si automatizza.
STRUMENTI_CHE_AGISCONO = frozenset(
    {
        "control_device",
        "comanda_media",
        "comanda_aspirapolvere",
        "comanda_ventilatore",
        "comanda_clima",
        "comanda_tapparella",
        "activate_scene_or_routine",
        "activate_mode",
    }
)

_VERBI_DI_LETTURA = frozenset({"stato", "status", "state"})


@dataclass(frozen=True)
class Abitudine:
    profilo: str
    strumento: str
    bersaglio: str
    verbo: str
    # L'orario tipico, in minuti dalla mezzanotte, arrotondato.
    minuto: int
    # I giorni distinti in cui e' successo vicino a quell'orario: le prove.
    giorni: tuple[date, ...]

    @property
    def orario(self) -> str:
        return f"{self.minuto // 60:02d}:{self.minuto % 60:02d}"

    @property
    def chiave(self) -> str:
        """Identifica l'abitudine, non il giorno: serve a non riproporre ogni notte la stessa cosa."""
        return f"{self.profilo}|{self.strumento}|{self.bersaglio}|{self.verbo}|{self.orario}"


def _momento(voce: Mapping[str, Any]) -> Optional[datetime]:
    valore = voce.get("momento")
    if isinstance(valore, datetime):
        return valore
    try:
        return datetime.fromisoformat(str(valore))
    except ValueError:
        return None


def _argomenti(voce: Mapping[str, Any]) -> Mapping[str, Any]:
    dettagli = voce.get("dettagli") or {}
    parametri = dettagli.get("parametri") if isinstance(dettagli, Mapping) else None
    return parametri if isinstance(parametri, Mapping) else {}


def _verbo(argomenti: Mapping[str, Any]) -> str:
    return str(argomenti.get("azione") or argomenti.get("action") or "").strip().lower()


def _candidata(voce: Mapping[str, Any]) -> Optional[tuple[str, str, str]]:
    """(strumento, bersaglio, verbo) se questa riga puo' far parte di un'abitudine, altrimenti None."""
    if str(voce.get("esito") or "ok") != "ok":
        return None
    azione = str(voce.get("azione") or "")
    if not azione.startswith("tool."):
        return None
    strumento = azione[len("tool.") :]
    if strumento not in STRUMENTI_CHE_AGISCONO:
        return None
    argomenti = _argomenti(voce)
    verbo = _verbo(argomenti)
    if verbo in _VERBI_DI_LETTURA:
        return None
    if sensibilita.classifica(strumento, argomenti) != sensibilita.SICURA:
        return None
    bersaglio = (
        sensibilita.bersaglio_di(argomenti)
        or str(argomenti.get("nome") or argomenti.get("name") or "").strip()
    )
    if not bersaglio:
        return None
    if sensibilita.entita_sensibile(bersaglio, verbo or "attiva"):
        return None
    return strumento, bersaglio, verbo


def _minuto(m: datetime) -> int:
    return m.hour * 60 + m.minute


def _arrotonda(minuto: int) -> int:
    return (round(minuto / ARROTONDAMENTO_MINUTI) * ARROTONDAMENTO_MINUTI) % (24 * 60)


def trova(
    voci: Iterable[Mapping[str, Any]],
    adesso: datetime,
    minimo_giorni: int = MINIMO_GIORNI,
    finestra_giorni: int = FINESTRA_GIORNI,
) -> list[Abitudine]:
    """Le abitudini di ciascun profilo nelle ultime `finestra_giorni`, dalle sole righe del registro. Le piu' solide per prime."""
    primo_giorno = adesso.date().toordinal() - finestra_giorni + 1
    gruppi: dict[tuple[str, str, str, str], list[datetime]] = defaultdict(list)
    for voce in voci:
        attore = str(voce.get("attore") or "")
        if not attore:
            continue
        quando = _momento(voce)
        if quando is None or quando > adesso or quando.date().toordinal() < primo_giorno:
            continue
        candidata = _candidata(voce)
        if candidata is None:
            continue
        gruppi[(attore, *candidata)].append(quando)

    trovate: list[Abitudine] = []
    for (profilo, strumento, bersaglio, verbo), momenti in gruppi.items():
        migliore = _finestra_piu_piena(momenti)
        if len(migliore) < minimo_giorni:
            continue
        minuti = sorted(_minuto(m) for m in migliore.values())
        tipico = _arrotonda(minuti[len(minuti) // 2])
        trovate.append(
            Abitudine(profilo, strumento, bersaglio, verbo, tipico, tuple(sorted(d for d in migliore)))
        )

    trovate.sort(key=lambda a: (-len(a.giorni), a.chiave))
    return trovate[:ABITUDINI_MASSIME]


def _finestra_piu_piena(momenti: list[datetime]) -> dict[date, datetime]:
    """Per ogni giorno la volta piu' vicina all'orario in cui ci sono piu' giorni distinti dentro `FINESTRA_MINUTI`."""
    migliore: dict[date, datetime] = {}
    for inizio in sorted({_minuto(m) for m in momenti}):
        dentro: dict[date, datetime] = {}
        for m in momenti:
            if 0 <= _minuto(m) - inizio <= FINESTRA_MINUTI:
                dentro.setdefault(m.date(), m)
        if len(dentro) > len(migliore):
            migliore = dentro
    return migliore
