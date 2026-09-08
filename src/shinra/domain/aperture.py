"""Cosa e' rimasto aperto.

Serve a rispondere «sono chiuse tutte le finestre?», e serve soprattutto a
non armare l'allarme mentre una finestra e' spalancata: un allarme armato su
una casa aperta suona da solo dopo dieci minuti, e chi lo ha armato ha
imparato una cosa sbagliata — che l'allarme e' inaffidabile.

Home Assistant non ha un dominio «aperture»: le porte e le finestre sono
`binary_sensor` con una `device_class`, e le tapparelle sono `cover`. Qui i
due mondi diventano un elenco solo.

Nessun IO: entrano gli stati, esce cio' che e' aperto.

Riferimento: issue #23.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# Le classi di `binary_sensor` che rappresentano un varco. `motion` o
# `battery` non c'entrano: aprire non e' muoversi.
CLASSI_APERTURA = frozenset({"door", "window", "garage_door", "opening"})

# `on` per un binary_sensor di questo tipo significa **aperto**. E' una
# convenzione di Home Assistant che si dimentica facilmente, e sbagliarla
# significa armare l'allarme esattamente quando non si dovrebbe.
APERTO = "on"

# Per le tapparelle e le porte da garage la parola la dice Home Assistant.
STATI_COVER_APERTI = frozenset({"open", "opening"})

IGNOTI = frozenset({"unknown", "unavailable", ""})


@dataclass(frozen=True)
class Apertura:
    entity_id: str
    nome: str
    aperta: bool
    tipo: str


def _classe(stato: dict[str, Any]) -> str:
    return str((stato.get("attributes") or {}).get("device_class") or "").lower()


def _nome(stato: dict[str, Any]) -> str:
    return str((stato.get("attributes") or {}).get("friendly_name") or stato.get("entity_id", ""))


def aperture(stati: Iterable[dict[str, Any]]) -> list[Apertura]:
    """Tutte le porte, finestre e coperture, aperte o chiuse.

    Chi ha uno stato ignoto resta fuori dall'elenco: un sensore che non
    risponde non e' una finestra chiusa, ma nemmeno una aperta, e metterlo
    fra le aperte farebbe rifiutare ogni armamento per un guasto.
    """
    trovate: list[Apertura] = []
    for stato in stati:
        entita = str(stato.get("entity_id", ""))
        dominio = entita.split(".", 1)[0] if "." in entita else ""
        valore = str(stato.get("state", "")).strip().lower()
        if valore in IGNOTI:
            continue

        if dominio == "binary_sensor" and _classe(stato) in CLASSI_APERTURA:
            trovate.append(Apertura(entita, _nome(stato), valore == APERTO, _classe(stato)))
        elif dominio == "cover":
            trovate.append(
                Apertura(entita, _nome(stato), valore in STATI_COVER_APERTI, _classe(stato) or "cover")
            )
    return trovate


def aperte(stati: Iterable[dict[str, Any]]) -> list[Apertura]:
    return [a for a in aperture(stati) if a.aperta]


def riassunto(elenco: list[Apertura]) -> str:
    """La frase da dire a voce. Vuota quando non c'e' niente di aperto."""
    nomi = [a.nome for a in elenco if a.aperta]
    if not nomi:
        return ""
    if len(nomi) == 1:
        return nomi[0]
    return ", ".join(nomi[:-1]) + " e " + nomi[-1]
