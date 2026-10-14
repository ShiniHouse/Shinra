"""Dove si trova una persona, rispetto ai luoghi registrati (#343).

La posizione e' un dato delicato e questo modulo ne tiene tre regole, difese dai test:

- **si legge al momento e non si conserva**: nessuna tabella di posizioni, nessuna traccia degli spostamenti. Si guarda
  l'ultimo stato che Home Assistant ha mandato (la cache) e si confronta con i luoghi;
- **solo chi l'ha acceso e' localizzato**: un profilo senza `entita_posizione` non ha una posizione, e dirlo e' la risposta;
- **si risponde col nome del luogo, mai con le coordinate**: le coordinate non escono da qui.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from shinra.domain import luoghi as dominio
from shinra.infra.db import depositi
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services import luoghi, registro

# Quanto puo' essere vecchia una posizione per valere ancora. Un telefono fermo non manda aggiornamenti: chi sta otto ore al
# lavoro ha una posizione «vecchia» di otto ore che e' giustissima. Si scarta solo oltre mezza giornata (telefono spento, app
# chiusa da ieri), e comunque si dice **quanto** e' vecchia.
VALIDITA_SECONDI = 12 * 3600

SPENTA = "spenta"
IGNOTA = "ignota"
IN_UN_LUOGO = "in_un_luogo"
IN_GIRO = "in_giro"

# Perche' non si sa dove e': detto a chi chiede, cosi' sa cosa guardare.
NON_E_IN_HOME_ASSISTANT = "non_in_home_assistant"
SENZA_COORDINATE = "senza_coordinate"
TROPPO_VECCHIA = "troppo_vecchia"
COORDINATE_ILLEGGIBILI = "coordinate_illeggibili"


@dataclass(frozen=True)
class DoveSei:
    stato: str
    luogo: Optional[str] = None
    tipo: Optional[str] = None
    principale: bool = False
    # Per spiegare un «non so» o un «in giro»: mai le coordinate, solo cose che aiutano a capire cosa non va.
    motivo: Optional[str] = None
    vicino: Optional[str] = None
    distanza_m: Optional[int] = None
    eta_minuti: Optional[int] = None

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "stato": self.stato,
            "luogo": self.luogo,
            "tipo": self.tipo,
            "principale": self.principale,
            "motivo": self.motivo,
            "vicino": self.vicino,
            "distanza_m": self.distanza_m,
            "eta_minuti": self.eta_minuti,
        }


def _eta_secondi(stato: dict[str, Any], adesso: float) -> Optional[float]:
    """Da quanto tempo l'ultimo aggiornamento della posizione, se Home Assistant lo dice."""
    scritto = stato.get("last_updated") or stato.get("last_changed")
    if not scritto:
        return None
    try:
        quando = datetime.fromisoformat(str(scritto).replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0.0, adesso - quando.timestamp())


def dove_sei(entita_posizione: str, adesso: Optional[float] = None) -> DoveSei:
    """In quale luogo registrato si trova la persona collegata a `entita_posizione`."""
    if not entita_posizione:
        return DoveSei(SPENTA)

    ora = time.time() if adesso is None else adesso
    stato = cache_stati.stato(entita_posizione)
    if not stato:
        return DoveSei(IGNOTA, motivo=NON_E_IN_HOME_ASSISTANT)

    eta = _eta_secondi(stato, ora)
    eta_minuti = None if eta is None else int(eta // 60)
    if eta is not None and eta > VALIDITA_SECONDI:
        return DoveSei(IGNOTA, motivo=TROPPO_VECCHIA, eta_minuti=eta_minuti)

    attributi = stato.get("attributes") or {}
    lat, lon = attributi.get("latitude"), attributi.get("longitude")
    if lat is None or lon is None:
        return DoveSei(IGNOTA, motivo=SENZA_COORDINATE, eta_minuti=eta_minuti)
    try:
        punto = (float(lat), float(lon))
    except (TypeError, ValueError):
        return DoveSei(IGNOTA, motivo=COORDINATE_ILLEGGIBILI, eta_minuti=eta_minuti)

    registrati = luoghi.elenco()
    luogo = dominio.piu_vicino(punto[0], punto[1], registrati)
    if luogo is not None:
        return DoveSei(
            IN_UN_LUOGO,
            str(luogo["nome"]),
            str(luogo["tipo"]),
            bool(luogo["principale"]),
            eta_minuti=eta_minuti,
        )

    # In giro: il piu' vicino e a quanto, arrotondato a cento metri. Aiuta a capire se il luogo e' stato registrato male
    # (una posizione presa da un PC puo' sbagliare di chilometri) senza dire dove si e'.
    vicino, distanza = None, None
    for x in registrati:
        d = dominio.distanza_m(punto[0], punto[1], float(x["latitudine"]), float(x["longitudine"]))
        if distanza is None or d < distanza:
            vicino, distanza = str(x["nome"]), d
    arrotondata = None if distanza is None else int(round(distanza / 100.0) * 100)
    return DoveSei(IN_GIRO, vicino=vicino, distanza_m=arrotondata, eta_minuti=eta_minuti)


def luogo_attuale(entita_posizione: str) -> Optional[dict[str, Any]]:
    """Il luogo registrato in cui si trova la persona, **con le coordinate**: per uso interno (il meteo), mai da mostrare."""
    risposta = dove_sei(entita_posizione)
    if risposta.stato != IN_UN_LUOGO:
        return None
    return next((x for x in luoghi.elenco() if x["nome"] == risposta.luogo), None)


PREFISSI_AMMESSI = ("person.", "device_tracker.")


class EntitaNonValida(ValueError):
    pass


def collega(profilo_id: str, entita: str) -> DoveSei:
    """Collega la persona o il telefono di Home Assistant a un profilo (vuoto: spegne la posizione).

    Si salva il **nome dell'entita'**, mai dove si trova la persona. Il registro scrive chi ha acceso o spento, non dove e'.
    """
    entita = (entita or "").strip()
    if entita and not entita.startswith(PREFISSI_AMMESSI):
        raise EntitaNonValida(
            "Serve una persona o un telefono di Home Assistant (person.… o device_tracker.…)."
        )
    depositi.utenti.aggiorna(profilo_id, {"entita_posizione": entita})
    registro.registra(
        "posizione.collegata" if entita else "posizione.spenta", dettagli={"profilo": profilo_id}
    )
    return dove_sei(entita)


def candidati() -> list[dict[str, Any]]:
    """Le persone e i telefoni di Home Assistant fra cui scegliere, col nome che si legge.

    Chi collega la propria posizione non conosce `device_tracker.iphone_di_mario`: conosce «iPhone di Mario». Si elencano
    solo quelli che hanno gia' una posizione (latitudine e longitudine), prima le persone. Le coordinate non escono.
    """
    trovati = []
    for stato in cache_stati.tutti():
        identificativo = str(stato.get("entity_id", ""))
        if not identificativo.startswith(PREFISSI_AMMESSI):
            continue
        attributi = stato.get("attributes") or {}
        trovati.append(
            {
                "entita": identificativo,
                "nome": str(attributi.get("friendly_name") or identificativo),
                "persona": identificativo.startswith("person."),
                "ha_posizione": attributi.get("latitude") is not None
                and attributi.get("longitude") is not None,
            }
        )
    return sorted(trovati, key=lambda c: (not c["ha_posizione"], not c["persona"], c["nome"].lower()))
