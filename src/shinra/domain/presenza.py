"""Chi c'e' in casa, e cosa e' cambiato da un momento all'altro.

E' l'informazione piu' utile della domotica, e fino alla v0.3.0 non veniva
usata da nessuno: `person` e `device_tracker` comparivano fra i domini
visibili e nessuna riga li guardava. Il sistema non sapeva se in casa ci
fosse qualcuno.

Qui dentro non c'e' niente che aspetti, chiami o scriva: due fotografie
entrano, un elenco di cambiamenti esce. La parte che ha a che fare con il
tempo — il ritardo contro i buchi del GPS — sta nel servizio, perche' e' li'
che serve un orologio.

Riferimento: issue #22.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

DOMINIO = "person"

# Home Assistant dice `home` quando la persona e' nella zona di casa. Tutto
# il resto — `not_home`, il nome di un'altra zona, `unknown` — significa che
# in casa non c'e'.
IN_CASA = "home"

# Uno stato che Home Assistant non sa dare. Non e' «fuori»: e' «non lo so», e
# trattarlo come un'uscita e' il modo piu' rapido di annunciare casa vuota
# mentre ci sono tutti.
IGNOTO = frozenset({"unknown", "unavailable", ""})


@dataclass(frozen=True)
class StatoCasa:
    """Chi c'e' e chi no, in un dato momento."""

    presenti: frozenset[str]
    assenti: frozenset[str]

    @property
    def abitata(self) -> bool:
        return bool(self.presenti)

    @property
    def conosciuta(self) -> bool:
        """Se sappiamo qualcosa di qualcuno. Senza persone configurate in
        Home Assistant, «casa vuota» sarebbe una deduzione dal nulla."""
        return bool(self.presenti or self.assenti)


PERSONA_RIENTRATA = "persona.rientrata"
PERSONA_USCITA = "persona.uscita"
CASA_ABITATA = "casa.abitata"
CASA_VUOTA = "casa.vuota"


@dataclass(frozen=True)
class Transizione:
    tipo: str
    persona: str = ""


def persone_dagli_stati(stati: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Solo le entita' `person`, con il loro stato grezzo."""
    return {
        s["entity_id"]: str(s.get("state", ""))
        for s in stati
        if str(s.get("entity_id", "")).startswith(f"{DOMINIO}.")
    }


def leggi(persone: dict[str, str]) -> StatoCasa:
    """Da «chi sta dove» a «chi c'e'».

    Chi ha uno stato ignoto non finisce ne' fra i presenti ne' fra gli
    assenti: non sapere dov'e' una persona non e' saperla fuori.
    """
    presenti: set[str] = set()
    assenti: set[str] = set()
    for entita, valore in persone.items():
        pulito = (valore or "").strip().lower()
        if pulito in IGNOTO:
            continue
        (presenti if pulito == IN_CASA else assenti).add(entita)
    return StatoCasa(frozenset(presenti), frozenset(assenti))


def transizioni(prima: Optional[StatoCasa], dopo: StatoCasa) -> list[Transizione]:
    """Cosa e' cambiato fra due fotografie.

    `prima` nullo significa che ci stiamo appena accendendo: non si annuncia
    niente. Altrimenti l'avvio del servizio direbbe che sono appena rientrati
    tutti, il che e' falso e per giunta farebbe partire le routine di rientro
    a ogni riavvio.
    """
    if prima is None:
        return []

    cambiamenti = [
        Transizione(PERSONA_RIENTRATA, persona) for persona in sorted(dopo.presenti - prima.presenti)
    ]
    cambiamenti += [Transizione(PERSONA_USCITA, persona) for persona in sorted(dopo.assenti - prima.assenti)]

    # Le transizioni della casa vanno dopo quelle delle persone: chi ascolta
    # «casa vuota» vuole gia' sapere chi e' stato l'ultimo a uscire.
    if prima.conosciuta and dopo.conosciuta:
        if prima.abitata and not dopo.abitata:
            cambiamenti.append(Transizione(CASA_VUOTA))
        elif not prima.abitata and dopo.abitata:
            cambiamenti.append(Transizione(CASA_ABITATA))

    return cambiamenti
