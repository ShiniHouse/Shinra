"""I luoghi: validare cio' che si registra e misurare le distanze (#342).

Puro: nessun database, nessuna rete. Le coordinate arrivano gia' lette (da un telefono, da un browser) e qui si decide solo
se sono un luogo possibile e quanto sono vicine fra loro. La posizione e' un dato delicato: nulla di cio' che sta qui
scrive o registra coordinate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

TIPI = ("abitazione", "lavoro", "altro")
ORIGINI = ("telefono", "browser")

RAGGIO_PREDEFINITO_M = 150
RAGGIO_MINIMO_M = 25
RAGGIO_MASSIMO_M = 5_000

# Il raggio di un luogo non puo' essere piu' stretto della precisione con cui e' stato registrato: un PC che sa dov'e' a
# 800 metri non puo' promettere un luogo largo 100.
FATTORE_PRECISIONE = 1.5

RAGGIO_TERRA_M = 6_371_000.0


class LuogoNonValido(ValueError):
    """Cio' che si vuole registrare non e' un luogo."""


@dataclass(frozen=True)
class Registrazione:
    nome: str
    tipo: str
    latitudine: float
    longitudine: float
    raggio_m: int
    citta: str
    origine: str
    precisione_m: Optional[int]


def distanza_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """La distanza in metri fra due punti (formula dell'emisenoverso)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * RAGGIO_TERRA_M * math.asin(math.sqrt(min(1.0, a)))


def _numero(valore: Any, nome: str) -> float:
    if isinstance(valore, bool) or valore is None:
        raise LuogoNonValido(f"{nome}: serve un numero")
    try:
        numero = float(valore)
    except (TypeError, ValueError) as errore:
        raise LuogoNonValido(f"{nome}: serve un numero") from errore
    if math.isnan(numero) or math.isinf(numero):
        raise LuogoNonValido(f"{nome}: serve un numero")
    return numero


def valida(dati: Mapping[str, Any]) -> Registrazione:
    """Trasforma cio' che arriva da un telefono o da un browser in una registrazione, o dice cosa non va."""
    nome = " ".join(str(dati.get("nome") or "").split())
    if not nome:
        raise LuogoNonValido("nome: serve un nome")
    if len(nome) > 120:
        raise LuogoNonValido("nome: troppo lungo")

    tipo = str(dati.get("tipo") or "abitazione")
    if tipo not in TIPI:
        raise LuogoNonValido(f"tipo: uno fra {', '.join(TIPI)}")

    lat = _numero(dati.get("latitudine"), "latitudine")
    lon = _numero(dati.get("longitudine"), "longitudine")
    if not -90 <= lat <= 90:
        raise LuogoNonValido("latitudine: fra -90 e 90")
    if not -180 <= lon <= 180:
        raise LuogoNonValido("longitudine: fra -180 e 180")
    if lat == 0 and lon == 0:
        # (0, 0) e' il valore di un dispositivo che non sa dov'e': non e' un luogo.
        raise LuogoNonValido("coordinate: (0, 0) e' una posizione non letta, non un luogo")

    origine = str(dati.get("origine") or "browser")
    if origine not in ORIGINI:
        raise LuogoNonValido(f"origine: una fra {', '.join(ORIGINI)}")

    precisione: Optional[int] = None
    if dati.get("precisione_m") not in (None, ""):
        precisione = int(_numero(dati.get("precisione_m"), "precisione_m"))
        if precisione < 0:
            raise LuogoNonValido("precisione_m: non puo' essere negativa")

    richiesto = RAGGIO_PREDEFINITO_M
    if dati.get("raggio_m") not in (None, ""):
        richiesto = int(_numero(dati.get("raggio_m"), "raggio_m"))
    raggio = max(RAGGIO_MINIMO_M, min(RAGGIO_MASSIMO_M, richiesto))
    if precisione:
        raggio = min(RAGGIO_MASSIMO_M, max(raggio, math.ceil(precisione * FATTORE_PRECISIONE)))

    return Registrazione(
        nome=nome,
        tipo=tipo,
        latitudine=lat,
        longitudine=lon,
        raggio_m=raggio,
        citta=" ".join(str(dati.get("citta") or "").split())[:120],
        origine=origine,
        precisione_m=precisione,
    )


def piu_vicino(lat: float, lon: float, luoghi: Sequence[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    """Il luogo il cui raggio contiene il punto (il piu' vicino se piu' d'uno); `None` se il punto e' «in giro»."""
    migliore: Optional[Mapping[str, Any]] = None
    migliore_distanza = float("inf")
    for luogo in luoghi:
        d = distanza_m(lat, lon, float(luogo["latitudine"]), float(luogo["longitudine"]))
        if d <= float(luogo["raggio_m"]) and d < migliore_distanza:
            migliore, migliore_distanza = luogo, d
    return migliore


def arrotonda_per_servizi_esterni(lat: float, lon: float) -> tuple[float, float]:
    """Le coordinate per un servizio di terzi (il meteo): arrotondate a circa un chilometro.

    Due decimali sono ~1,1 km di latitudine. Il servizio non deve conoscere l'ingresso di casa.
    """
    return round(lat, 2), round(lon, 2)
