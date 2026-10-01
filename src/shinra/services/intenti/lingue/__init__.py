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
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

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
    ("casa", "parole_temperatura"),
    ("casa", "preposizioni_stanza"),
    ("notizie", "inneschi"),
    ("agente", "parole_azione"),
    ("conferma", "accetta"),
    ("conferma", "rifiuta"),
    ("calendario", "giorni"),
    ("calendario", "mesi"),
    ("calendario", "formato_data"),
)

# Le frasi che Shinra **dice**, una per chiave. Stanno qui e non in
# `RICHIESTE` perche' il controllo e' piu' fine: non basta che la sezione
# `messaggi` esista, ogni frase che il codice sa dire deve avere la sua in
# ogni lingua. Una chiave che manca non deve scoppiare dentro una risposta a
# chi sta parlando: si dice per nome al caricamento.
CHIAVI_MESSAGGI: Tuple[str, ...] = (
    "temperatura_sensori_illeggibili",
    "temperatura_nessun_sensore",
    "temperatura_nessun_sensore_in",
    "temperatura_una_lettura",
    "temperatura_piu_letture",
    "dispositivo_negato",
    "dispositivo_non_comandato",
    "dispositivo_acceso",
    "dispositivo_spento",
    "modalita_attivata",
    "meteo_domani",
    "meteo_adesso",
    "meteo_massima",
    "condizione_variabile",
    "notizie_ultime",
    "apprendimento_interrotto",
    "timer_impostato",
    "promemoria_impostato",
    "argomento_vietato",
    "errore_ollama",
    "operazione_completata",
    "dati_verificati",
    "risultato_operazione",
    "conferma_richiesta",
    "conferma_vietata",
    "conferma_senza_identita",
    "conferma_senza_canale",
    "conferma_nessuna",
    "conferma_scaduta",
    "conferma_rifiutata",
    "conferma_eseguita",
)

# I pezzi del prompt di sistema. Lo stesso ragionamento: il prompt e' il
# punto in cui la lingua della risposta si decide davvero, perche' il modello
# risponde nella lingua in cui gli si parla. Un prompt in italiano con
# l'utente che scrive in inglese produce risposte in un italiano stentato.
CHIAVI_PROMPT: Tuple[str, ...] = (
    "intro",
    "utente_anonimo",
    "persona_bambino",
    "persona_ragazzo",
    "persona_adulto",
    "ruolo_admin",
    "ruolo_adulto",
    "regole",
    "titolo_conoscenza",
    "titolo_alias",
    "titolo_modalita",
    "titolo_dispositivi",
    "informazioni_in_tempo_reale",
    "informazioni_chiusura",
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
    parole_temperatura: Tuple[str, ...]
    stanza: re.Pattern
    inneschi_notizie: Tuple[str, ...]
    parole_azione: Tuple[str, ...]
    conferma_accetta: Tuple[str, ...]
    conferma_rifiuta: Tuple[str, ...]
    giorni: Tuple[str, ...]
    mesi: Tuple[str, ...]
    formato_data: str
    messaggi: Mapping[str, str]
    prompt: Mapping[str, str]

    def dice(self, chiave: str, **valori: Any) -> str:
        """Una frase di questa lingua, con i valori al loro posto."""
        return self.messaggi[chiave].format_map(valori)

    def prompt_di(self, chiave: str, **valori: Any) -> str:
        """Un pezzo del prompt di sistema in questa lingua."""
        return self.prompt[chiave].format_map(valori)

    def data_e_ora(self, momento: "datetime") -> str:
        """«mercoledi 30 settembre 2026, ore 21:40», senza passare dal locale
        del sistema: i nomi dei giorni e dei mesi stanno nel file della
        lingua, cosi' la risposta non dipende da come e' configurata la
        macchina che ospita Shinra."""
        return self.formato_data.format(
            giorno=self.giorni[momento.weekday()],
            numero=momento.day,
            mese=self.mesi[momento.month - 1],
            anno=momento.year,
            ore=f"{momento.hour:02d}",
            minuti=f"{momento.minute:02d}",
        )


def lingue_disponibili() -> Tuple[str, ...]:
    """Le lingue che esistono sul disco. Una lingua nuova entra qui il giorno
    che il suo file nasce, non il giorno che qualcuno la aggiunge a un elenco."""
    return tuple(sorted(f.stem for f in CARTELLA.glob("*.yaml")))


def _verifica(dati: Dict[str, Any], dove: Path) -> None:
    mancanti = []
    for sezione, chiavi in (("messaggi", CHIAVI_MESSAGGI), ("prompt", CHIAVI_PROMPT)):
        presenti = dati.get(sezione)
        if not isinstance(presenti, dict):
            mancanti.append(sezione)
            continue
        mancanti.extend(f"{sezione}.{k}" for k in chiavi if not presenti.get(k))
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
        parole_temperatura=tuple(dati["casa"]["parole_temperatura"]),
        stanza=re.compile(dati["casa"]["preposizioni_stanza"], re.IGNORECASE),
        inneschi_notizie=tuple(dati["notizie"]["inneschi"]),
        parole_azione=tuple(dati["agente"]["parole_azione"]),
        conferma_accetta=tuple(p.lower() for p in dati["conferma"]["accetta"]),
        conferma_rifiuta=tuple(p.lower() for p in dati["conferma"]["rifiuta"]),
        giorni=tuple(dati["calendario"]["giorni"]),
        mesi=tuple(dati["calendario"]["mesi"]),
        formato_data=str(dati["calendario"]["formato_data"]),
        messaggi={k: str(v) for k, v in dati["messaggi"].items()},
        prompt={k: str(v) for k, v in dati["prompt"].items()},
    )


def elenco_lingue() -> Dict[str, Any]:
    """Le lingue fra cui scegliere, per il menu del profilo.

    Ritorna anche quella dell'installazione, perche' «come la casa» e' una
    scelta a parte: una persona che non sceglie niente la segue, anche se
    un giorno la casa cambia lingua.
    """
    disponibili = []
    for codice in lingue_disponibili():
        try:
            disponibili.append({"codice": codice, "nome": _compila(codice).nome})
        except LinguaIncompleta:
            continue  # un file a meta' non si offre: sceglierlo sarebbe ripiegare sull'italiano
    from shinra.config import settings as impostazioni

    return {"installazione": impostazioni.settings.assistant.language, "lingue": disponibili}


def schemi(lingua: str | None = None) -> Schemi:
    """Gli schemi della lingua chiesta, o di quella configurata.

    Una lingua configurata che non esiste sul disco non deve spegnere la casa:
    si ripiega sull'italiano. Il contrario — sollevare — vorrebbe dire che un
    refuso in `config.yaml` rende Shinra muta, e un refuso in un file di
    configurazione e' una cosa che succede.
    """
    if not lingua:
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
