# -*- coding: utf-8 -*-
"""Gli schemi con cui Shinra capisce una frase, una lingua per file.

Fino alla #36 stavano dentro gli intenti: `SEGNALI_INTERNI` in `casa.py`,
`PAROLE_METEO` e `CITTA` in `informazioni.py`, le frasi che aprono
l'intervista in `promemoria.py`. Erano costanti di modulo, quindi aggiungere
una lingua voleva dire **modificare la logica** — ed e' esattamente il
criterio che la #36 deve soddisfare: non deve servire.

Adesso un file YAML accanto a questo e' una lingua. Il caricatore controlla
che ci siano tutte le chiavi e dice **per nome** quale manca: un intento che
si rompe a meta' perche' una chiave non c'era sarebbe il guasto peggiore, dato
che il sintomo — «quella frase non la capisce» — e' identico a un modello che
non ha capito.

Gli schemi si leggono a ogni chiamata, non all'import: gli intenti nascono
quando il modulo si carica, e la lingua si puo' cambiare dalle impostazioni
senza riavviare.

Riferimento: issue #36.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

CARTELLA = Path(__file__).parent
LINGUA_DI_RIPIEGO = "it"

# Ogni chiave che il codice legge, con il suo percorso nel file. Sta qui e non
# sparsa negli intenti per una ragione sola: e' l'elenco che il caricatore usa
# per dire «manca questa» invece di lasciar scoppiare un KeyError dentro un
# intento, a meta' di una frase dell'utente.
RICHIESTE: Tuple[Tuple[str, ...], ...] = (
    ("casa", "segnali_interni"),
    ("casa", "controllo_dispositivo"),
    ("casa", "verbi_che_accendono"),
    ("meteo", "parole"),
    ("meteo", "citta"),
    ("meteo", "domani"),
    ("enciclopedia", "inneschi"),
    ("enciclopedia", "pulizia"),
    ("apprendimento", "avvii"),
    ("apprendimento", "interruzioni"),
)


class LinguaIncompleta(ValueError):
    """Un file di lingua a cui manca qualcosa che il codice legge."""


@dataclass(frozen=True)
class Schemi:
    """Gli schemi di una lingua, gia' compilati dove serve."""

    lingua: str
    nome: str
    segnali_interni: Tuple[str, ...]
    controllo_dispositivo: re.Pattern
    verbi_che_accendono: Tuple[str, ...]
    parole_meteo: Tuple[str, ...]
    domani: str
    citta: re.Pattern
    inneschi_enciclopedia: Tuple[str, ...]
    pulizia_enciclopedia: re.Pattern
    avvii_apprendimento: Tuple[str, ...]
    interruzioni_apprendimento: Tuple[str, ...]


def lingue_disponibili() -> Tuple[str, ...]:
    """Le lingue che esistono sul disco. Una lingua nuova entra qui il giorno
    che il suo file nasce, non il giorno che qualcuno la aggiunge a un elenco."""
    return tuple(sorted(f.stem for f in CARTELLA.glob("*.yaml")))


def _verifica(dati: Dict[str, Any], dove: Path) -> None:
    mancanti = []
    for percorso in RICHIESTE:
        nodo: Any = dati
        for pezzo in percorso:
            if not isinstance(nodo, dict) or pezzo not in nodo:
                mancanti.append(".".join(percorso))
                break
            nodo = nodo[pezzo]
    if mancanti:
        raise LinguaIncompleta(f"{dove.name}: mancano {', '.join(mancanti)}")


@lru_cache(maxsize=8)
def _compila(lingua: str) -> Schemi:
    percorso = CARTELLA / f"{lingua}.yaml"
    if not percorso.is_file():
        raise FileNotFoundError(f"lingua «{lingua}» non trovata: ci sono {', '.join(lingue_disponibili())}")
    dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    _verifica(dati, percorso)

    return Schemi(
        lingua=str(dati.get("lingua") or lingua),
        nome=str(dati.get("nome") or lingua),
        segnali_interni=tuple(dati["casa"]["segnali_interni"]),
        controllo_dispositivo=re.compile(dati["casa"]["controllo_dispositivo"], re.IGNORECASE),
        verbi_che_accendono=tuple(v.lower() for v in dati["casa"]["verbi_che_accendono"]),
        parole_meteo=tuple(dati["meteo"]["parole"]),
        domani=str(dati["meteo"]["domani"]),
        citta=re.compile(dati["meteo"]["citta"]),
        inneschi_enciclopedia=tuple(dati["enciclopedia"]["inneschi"]),
        pulizia_enciclopedia=re.compile(dati["enciclopedia"]["pulizia"], re.IGNORECASE),
        avvii_apprendimento=tuple(dati["apprendimento"]["avvii"]),
        interruzioni_apprendimento=tuple(dati["apprendimento"]["interruzioni"]),
    )


def schemi(lingua: str | None = None) -> Schemi:
    """Gli schemi della lingua chiesta, o di quella configurata.

    Una lingua configurata che non esiste sul disco non deve spegnere la casa:
    si ripiega sull'italiano. Il contrario — sollevare — vorrebbe dire che un
    refuso in `config.yaml` rende Shinra muta, e un refuso in un file di
    configurazione e' una cosa che succede.
    """
    if lingua is None:
        from shinra.config import settings as impostazioni

        lingua = impostazioni.settings.assistant.language

    try:
        return _compila(lingua)
    except (FileNotFoundError, LinguaIncompleta):
        if lingua == LINGUA_DI_RIPIEGO:
            raise
        import logging

        logging.getLogger("Shinra.Intenti").warning(
            "Lingua «%s» non utilizzabile: si prosegue in %s.", lingua, LINGUA_DI_RIPIEGO
        )
        return _compila(LINGUA_DI_RIPIEGO)
