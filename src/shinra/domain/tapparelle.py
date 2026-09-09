"""Tapparelle, tende e persiane: quanto sono aperte e quanto sanno aprirsi.

In Home Assistant sono tutte `cover`, e la parola non dice quasi niente: una
tapparella elettrica con posizione al centimetro e un cancello che sa solo
aprirsi e chiudersi sono la stessa entita'. La differenza sta in
`supported_features`, una maschera di bit che l'integrazione dichiara.

Da qui la regola: **si guarda cosa dichiara prima di chiedere.** Mandare
`set_cover_position` a un motore che non sa posizionarsi non produce una
tapparella a meta': produce niente, e una persona convinta che sia a meta'.

Una nota sul verso, perche' e' la cosa che si sbaglia piu' spesso: in Home
Assistant **la posizione dice quanto e' aperta**, non quanto e' abbassata.
Zero e' chiusa, cento e' aperta. «Portala al 40 per cento» vuol dire aperta
al 40, cioe' piuttosto abbassata — ed e' quello che vede anche chi guarda la
dashboard, quindi e' il verso giusto da tenere.

Riferimento: issue #21.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

DOMINIO = "cover"

# `CoverEntityFeature` di Home Assistant. Sono numeri suoi: stanno scritti
# qui perche' il codice li legge, non perche' li decidiamo noi.
APRE = 1
CHIUDE = 2
POSIZIONA = 4
FERMA = 8
APRE_LAMELLE = 16
CHIUDE_LAMELLE = 32
FERMA_LAMELLE = 64
POSIZIONA_LAMELLE = 128

CHIUSA = 0
APERTA = 100


class NonSaFarlo(Exception):
    """Il motore non dichiara questa capacita'."""


@dataclass(frozen=True)
class Capacita:
    sa_posizionarsi: bool
    sa_fermarsi: bool
    sa_orientare_lamelle: bool
    sa_aprire: bool
    sa_chiudere: bool


def capacita(attributi: Mapping[str, Any]) -> Capacita:
    try:
        bit = int(attributi.get("supported_features") or 0)
    except (TypeError, ValueError):
        bit = 0

    if bit == 0:
        # Nessuna dichiarazione: si prova tutto. Un'integrazione muta non e'
        # un'integrazione incapace, e rifiutare a priori toglierebbe la
        # funzione a chi ha un motore vecchio ma funzionante.
        return Capacita(True, True, True, True, True)

    return Capacita(
        sa_posizionarsi=bool(bit & POSIZIONA),
        sa_fermarsi=bool(bit & FERMA),
        sa_orientare_lamelle=bool(bit & POSIZIONA_LAMELLE),
        sa_aprire=bool(bit & APRE),
        sa_chiudere=bool(bit & CHIUDE),
    )


def posiziona(valore: Any, sapute: Capacita) -> int:
    """La percentuale da mandare, dentro ai limiti e con il verso giusto."""
    if not sapute.sa_posizionarsi:
        raise NonSaFarlo(
            "Questa tapparella si apre e si chiude, ma non sa fermarsi a una " "posizione precisa."
        )
    try:
        richiesta = round(float(valore))
    except (TypeError, ValueError):
        raise NonSaFarlo(f"«{valore}» non e' una percentuale.") from None
    return max(CHIUSA, min(APERTA, richiesta))


def orienta(valore: Any, sapute: Capacita) -> int:
    if not sapute.sa_orientare_lamelle:
        raise NonSaFarlo("Questa tenda non ha lamelle orientabili.")
    try:
        richiesta = round(float(valore))
    except (TypeError, ValueError):
        raise NonSaFarlo(f"«{valore}» non e' una percentuale.") from None
    return max(0, min(100, richiesta))


def ferma(sapute: Capacita) -> None:
    if not sapute.sa_fermarsi:
        raise NonSaFarlo("Questa tapparella non si puo' fermare a meta' corsa.")


def posizione(attributi: Mapping[str, Any]) -> Optional[int]:
    """Quanto e' aperta adesso, se il motore lo sa dire."""
    grezza = attributi.get("current_position")
    if grezza is None:
        return None
    try:
        return round(float(grezza))
    except (TypeError, ValueError):
        return None


def riassumi(stato: str, attributi: Mapping[str, Any]) -> str:
    """Com'e' adesso, in una frase.

    La percentuale, quando c'e', vale piu' di «aperta»: una tapparella al 5
    per cento e una spalancata sono tutte e due `open` per Home Assistant, e
    non sono per niente la stessa cosa in casa.
    """
    dove = posizione(attributi)
    if dove is None:
        return {"open": "aperta", "closed": "chiusa"}.get(stato, stato)

    if dove <= CHIUSA:
        descrizione = "chiusa"
    elif dove >= APERTA:
        descrizione = "aperta del tutto"
    else:
        descrizione = f"aperta al {dove} per cento"

    lamelle = attributi.get("current_tilt_position")
    if lamelle is not None:
        try:
            descrizione += f", lamelle al {round(float(lamelle))} per cento"
        except (TypeError, ValueError):
            pass

    return descrizione
