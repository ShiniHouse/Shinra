"""La posizione dell'app diventa notizia: arrivi e partenze arrivano a presenza e regole come se le avesse dette Home Assistant (#343, #346).

Chi sceglie «questo telefono» come fonte della propria posizione non passa da Home Assistant, e finora la presenza in casa e le
regole «quando arrivo in...» non lo vedevano. Qui ogni segnalazione dell'app si traduce nel modo in cui Home Assistant racconta
una persona: `home` per il luogo principale, il **nome** di un altro luogo registrato, `not_home` se si e' in giro. Quando quel
valore cambia si pubblica lo stesso evento (`ha.stato_cambiato` su `person.app_<profilo>`) e il resto del sistema non deve sapere
da dove viene.

Regole, difese dai test:

- **la prima segnalazione non e' un arrivo**: dopo un riavvio (la memoria si perde) aprire l'app a casa non deve far partire il
  benvenuto. Si registra in silenzio e si annuncia solo dal cambiamento successivo;
- **niente coordinate**: l'evento porta il nome del luogo e basta, e non si conserva nessuno spostamento (solo l'ultimo stato, in memoria);
- **«non so» non e' «fuori»**: una posizione ignota (app senza segnalazioni, troppo vecchia) non annuncia niente. L'app chiusa non
  dice che si e' usciti: dice solo che non lo sappiamo piu'.
"""

from __future__ import annotations

from typing import Optional

from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento, bus
from shinra.domain.presenza import DOMINIO
from shinra.services import posizione

_ultimo: dict[str, str] = {}


def entita_del_profilo(profilo_id: str) -> str:
    return f"{DOMINIO}.app_{profilo_id}"


def stato_alla_maniera_di_home_assistant(dove: posizione.DoveSei) -> Optional[str]:
    """`home`, il nome di un luogo, `not_home` — o `None` se non si sa."""
    if dove.stato == posizione.IN_UN_LUOGO:
        return "home" if dove.principale else str(dove.luogo)
    if dove.stato == posizione.IN_GIRO:
        return "not_home"
    return None


def annuncia(profilo_id: str, dove: posizione.DoveSei, nome: str = "") -> None:
    """Dopo una segnalazione: se il luogo e' cambiato lo dice al bus."""
    nuovo = stato_alla_maniera_di_home_assistant(dove)
    if nuovo is None:
        return
    prima = _ultimo.get(profilo_id)
    _ultimo[profilo_id] = nuovo
    entita = entita_del_profilo(profilo_id)
    if prima is None:
        from shinra.services.presenza import presenza

        presenza.conosci(entita, nuovo)
        return
    if prima == nuovo:
        return
    bus.pubblica_senza_attendere(
        Evento(
            tipo=HA_STATO_CAMBIATO,
            dati={
                "entity_id": entita,
                "stato": nuovo,
                "stato_precedente": prima,
                "nome": nome or profilo_id,
                "dominio": DOMINIO,
            },
        )
    )


def dimentica(profilo_id: str) -> None:
    """Cambiata o spenta la fonte: la persona dell'app non c'e' piu' per nessuno."""
    _ultimo.pop(profilo_id, None)
    from shinra.services.presenza import presenza

    presenza.dimentica(entita_del_profilo(profilo_id))
