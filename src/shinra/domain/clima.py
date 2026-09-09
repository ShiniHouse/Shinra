"""Cosa sa fare un termostato, e come dirglielo.

Home Assistant non ha «il clima»: ha entita' `climate` che dichiarano, negli
attributi, quali modalita' accettano, quali velocita' di ventola, che
temperature reggono. Un condizionatore da finestra e una caldaia a
condensazione sono la stessa entita' con capacita' diversissime.

Da qui la regola di questo modulo: **si chiede al dispositivo cosa sa fare
prima di chiedergli di farlo.** Mandare `dry` a un termostato che non
deumidifica non produce un errore utile — produce una chiamata che fallisce
in silenzio o un 500, e una persona che ha sentito «fatto» mentre non e'
stato fatto niente. Meglio dire «questo termostato non deumidifica: sa fare
riscaldamento e spento».

Qui non si chiama niente e non si aspetta niente: entrano le parole della
persona e gli attributi letti da Home Assistant, esce cosa mandare — oppure
il motivo per cui non si puo'.

Riferimento: issue #21.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

DOMINIO = "climate"

# Le modalita' di Home Assistant, con le parole che una persona usa davvero.
# Non e' un dizionario di traduzione: e' l'elenco di come si chiede la stessa
# cosa. «Metti il caldo», «accendi il riscaldamento» e «heat» sono la stessa
# richiesta.
MODALITA: dict[str, tuple[str, ...]] = {
    "off": ("spento", "spegni", "off", "niente"),
    "heat": ("riscaldamento", "caldo", "riscalda", "calore", "heat", "termosifone"),
    "cool": ("raffrescamento", "freddo", "raffresca", "condizionatore", "aria condizionata", "cool"),
    "heat_cool": ("automatico", "auto", "caldo e freddo", "heat_cool"),
    "auto": ("automatico", "auto", "programma"),
    "dry": ("deumidificazione", "deumidifica", "deumidificatore", "secco", "dry", "umidita"),
    "fan_only": ("ventilazione", "ventola", "solo ventola", "aria", "fan", "fan_only"),
}

# I nomi italiani delle modalita', per quando bisogna dire alla persona cosa
# il suo termostato sa fare.
NOMI: dict[str, str] = {
    "off": "spento",
    "heat": "riscaldamento",
    "cool": "raffrescamento",
    "heat_cool": "caldo e freddo",
    "auto": "automatico",
    "dry": "deumidificazione",
    "fan_only": "ventilazione",
}

# I valori con cui Home Assistant parte quando l'integrazione non dichiara
# niente. Sono i suoi, non nostri: cambiarli qui vorrebbe dire rifiutare
# temperature che il termostato accetterebbe.
TEMPERATURA_MINIMA = 7.0
TEMPERATURA_MASSIMA = 35.0
UMIDITA_MINIMA = 30
UMIDITA_MASSIMA = 99

# `ClimateEntityFeature.TARGET_HUMIDITY`. E' un numero di Home Assistant:
# sta qui perche' il codice lo legge, non perche' lo decidiamo noi.
REGOLA_UMIDITA = 4


class NonSaFarlo(Exception):
    """Il dispositivo non dichiara questa capacita'.

    Porta con se' cosa sa fare davvero: un rifiuto che non dice l'alternativa
    costringe la persona a indovinare.
    """

    def __init__(self, messaggio: str, alternative: Optional[list[str]] = None):
        super().__init__(messaggio)
        self.alternative = alternative or []


@dataclass(frozen=True)
class Capacita:
    """Cio' che il termostato dichiara di saper fare, letto dai suoi attributi."""

    modalita: tuple[str, ...]
    ventole: tuple[str, ...]
    preset: tuple[str, ...]
    lamelle: tuple[str, ...]
    temperatura_minima: float
    temperatura_massima: float
    umidita_minima: int
    umidita_massima: int
    regola_umidita: bool


def _testo(valori: Any) -> tuple[str, ...]:
    if not isinstance(valori, (list, tuple)):
        return ()
    return tuple(str(v) for v in valori if v is not None)


def _numero(valore: Any, ripiego: float) -> float:
    try:
        return float(valore)
    except (TypeError, ValueError):
        return ripiego


def capacita(attributi: Mapping[str, Any]) -> Capacita:
    """Da quel che Home Assistant dichiara a quel che si puo' chiedere."""
    minima = _numero(attributi.get("min_temp"), TEMPERATURA_MINIMA)
    massima = _numero(attributi.get("max_temp"), TEMPERATURA_MASSIMA)
    if massima < minima:
        minima, massima = massima, minima

    umidita_min = int(_numero(attributi.get("min_humidity"), UMIDITA_MINIMA))
    umidita_max = int(_numero(attributi.get("max_humidity"), UMIDITA_MASSIMA))

    # `dry` fra le modalita' non basta: deumidificare e' una modalita',
    # impostare un'umidita' obiettivo e' un'altra cosa, e molti
    # condizionatori fanno la prima senza la seconda.
    #
    # Qui, a differenza delle modalita', il silenzio vale come «no». Le
    # modalita' si provano anche quando il dispositivo non le dichiara,
    # perche' il rischio e' negare una funzione che c'e'. Sull'umidita' il
    # rischio e' l'opposto: `set_humidity` a un termostato che non la regola
    # e' un errore secco di Home Assistant, e la persona si becca un guasto
    # invece di una frase che spiega.
    try:
        bit = int(attributi.get("supported_features") or 0)
    except (TypeError, ValueError):
        bit = 0
    dichiarata = bool(bit & REGOLA_UMIDITA) or any(
        attributi.get(chiave) is not None
        for chiave in ("min_humidity", "max_humidity", "humidity", "current_humidity")
    )

    return Capacita(
        modalita=_testo(attributi.get("hvac_modes")),
        ventole=_testo(attributi.get("fan_modes")),
        preset=_testo(attributi.get("preset_modes")),
        lamelle=_testo(attributi.get("swing_modes")),
        temperatura_minima=minima,
        temperatura_massima=massima,
        umidita_minima=umidita_min,
        umidita_massima=umidita_max,
        regola_umidita=dichiarata,
    )


def _normalizza(parola: str) -> str:
    return " ".join((parola or "").strip().lower().replace("_", " ").split())


def modalita_dalle_parole(parola: str) -> Optional[str]:
    """Da «deumidificazione» a `dry`. `None` se non e' una modalita'."""
    cercata = _normalizza(parola)
    if not cercata:
        return None

    for codice, sinonimi in MODALITA.items():
        if cercata == _normalizza(codice):
            return codice
        if any(cercata == _normalizza(s) for s in sinonimi):
            return codice

    # Poi per contenimento: «mettilo in aria condizionata per favore».
    for codice, sinonimi in MODALITA.items():
        if any(_normalizza(s) in cercata for s in sinonimi):
            return codice

    return None


def elenca(codici: Iterable[str]) -> list[str]:
    """I nomi italiani, per dire alla persona cosa e' possibile."""
    return [NOMI.get(c, c) for c in codici]


def scegli_modalita(parola: str, sapute: Capacita) -> str:
    """La modalita' da mandare a Home Assistant, o il motivo per cui no."""
    codice = modalita_dalle_parole(parola)
    if codice is None:
        raise NonSaFarlo(
            f"Non ho capito quale modalita' intendi con «{parola}».",
            elenca(sapute.modalita),
        )

    if not sapute.modalita:
        # Nessuna dichiarazione: si prova. Un'integrazione che non elenca le
        # sue modalita' non e' un'integrazione che non ne ha.
        return codice

    if codice in sapute.modalita:
        return codice

    # `auto` e `heat_cool` sono la stessa idea con due nomi, e le
    # integrazioni ne dichiarano una o l'altra.
    gemelle = {"auto": "heat_cool", "heat_cool": "auto"}
    gemella = gemelle.get(codice)
    if gemella and gemella in sapute.modalita:
        return gemella

    raise NonSaFarlo(
        f"Questo termostato non fa {NOMI.get(codice, codice)}.",
        elenca(sapute.modalita),
    )


def scegli_fra(parola: str, disponibili: tuple[str, ...], cosa: str) -> str:
    """Per ventola, preset e lamelle: i valori li nomina l'integrazione, non
    noi. «Medium», «Silenzioso», «Notte» sono tutti legittimi e nessun elenco
    scritto qui li conterrebbe."""
    if not disponibili:
        raise NonSaFarlo(f"Questo termostato non permette di scegliere {cosa}.")

    cercata = _normalizza(parola)
    if not cercata:
        raise NonSaFarlo(f"Serve dire quale {cosa}.", list(disponibili))

    for valore in disponibili:
        if _normalizza(valore) == cercata:
            return valore
    for valore in disponibili:
        if cercata in _normalizza(valore) or _normalizza(valore) in cercata:
            return valore

    raise NonSaFarlo(f"«{parola}» non e' fra le {cosa} di questo termostato.", list(disponibili))


def tempera(valore: float, sapute: Capacita) -> float:
    """La temperatura dentro ai limiti del dispositivo.

    Si accorcia invece di rifiutare: chi dice «mettilo a 30» in una casa il
    cui termostato arriva a 28 vuole il massimo, non un errore.
    """
    return max(sapute.temperatura_minima, min(sapute.temperatura_massima, float(valore)))


def umidifica(valore: int, sapute: Capacita) -> int:
    if not sapute.regola_umidita:
        raise NonSaFarlo("Questo termostato non imposta un'umidita' obiettivo.")
    return max(sapute.umidita_minima, min(sapute.umidita_massima, int(valore)))


def riassumi(stato: str, attributi: Mapping[str, Any]) -> str:
    """Come sta adesso, in una frase.

    Il criterio di accettazione della scheda e' «a che temperatura e'
    impostato il termostato?»: la risposta e' la temperatura *obiettivo*, che
    non e' quella misurata nella stanza. Confonderle e' il modo piu' facile
    per rispondere con sicurezza una cosa sbagliata.
    """
    pezzi = [NOMI.get(stato, stato)]

    obiettivo = attributi.get("temperature")
    if obiettivo is not None:
        pezzi.append(f"impostato a {arrotonda(obiettivo)} gradi")

    misurata = attributi.get("current_temperature")
    if misurata is not None:
        pezzi.append(f"in stanza ce ne sono {arrotonda(misurata)}")

    umidita = attributi.get("current_humidity")
    if umidita is not None:
        pezzi.append(f"umidita' al {arrotonda(umidita)} per cento")

    ventola = attributi.get("fan_mode")
    if ventola:
        pezzi.append(f"ventola {ventola}")

    preset = attributi.get("preset_mode")
    if preset and str(preset).lower() not in ("none", "null"):
        pezzi.append(f"modalita' {preset}")

    return ", ".join(pezzi) + "."


def arrotonda(valore: Any) -> str:
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return str(valore)
    return str(int(numero)) if numero == int(numero) else f"{numero:.1f}"
