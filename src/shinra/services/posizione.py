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

# Quanto puo' essere vecchia una posizione per valere ancora. Home Assistant la aggiorna da solo; se tace da piu' di cosi'
# (telefono spento, app chiusa) «dove sei» deve dire che non lo sa, non indicare un posto di ore fa.
VALIDITA_SECONDI = 30 * 60

SPENTA = "spenta"
IGNOTA = "ignota"
IN_UN_LUOGO = "in_un_luogo"
IN_GIRO = "in_giro"


@dataclass(frozen=True)
class DoveSei:
    stato: str
    luogo: Optional[str] = None
    tipo: Optional[str] = None
    principale: bool = False

    def come_dizionario(self) -> dict[str, Any]:
        return {"stato": self.stato, "luogo": self.luogo, "tipo": self.tipo, "principale": self.principale}


def _troppo_vecchia(stato: dict[str, Any], adesso: float) -> bool:
    """La posizione e' ferma da piu' di `VALIDITA_SECONDI`? Senza data non si puo' dire, e non si scarta."""
    scritto = stato.get("last_updated") or stato.get("last_changed")
    if not scritto:
        return False
    try:
        quando = datetime.fromisoformat(str(scritto).replace("Z", "+00:00"))
    except ValueError:
        return False
    return adesso - quando.timestamp() > VALIDITA_SECONDI


def dove_sei(entita_posizione: str, adesso: Optional[float] = None) -> DoveSei:
    """In quale luogo registrato si trova la persona collegata a `entita_posizione`."""
    if not entita_posizione:
        return DoveSei(SPENTA)

    stato = cache_stati.stato(entita_posizione)
    if not stato:
        return DoveSei(IGNOTA)
    if _troppo_vecchia(stato, time.time() if adesso is None else adesso):
        return DoveSei(IGNOTA)
    attributi = stato.get("attributes") or {}
    lat, lon = attributi.get("latitude"), attributi.get("longitude")
    if lat is None or lon is None:
        return DoveSei(IGNOTA)

    try:
        punto = (float(lat), float(lon))
    except (TypeError, ValueError):
        return DoveSei(IGNOTA)

    registrati = luoghi.elenco()
    luogo = dominio.piu_vicino(punto[0], punto[1], registrati)
    if luogo is None:
        return DoveSei(IN_GIRO)
    return DoveSei(IN_UN_LUOGO, str(luogo["nome"]), str(luogo["tipo"]), bool(luogo["principale"]))


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
