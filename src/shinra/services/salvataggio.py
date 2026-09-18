"""Mettere al sicuro la configurazione della casa, e rimetterla dov'era.

Chi ha passato un'ora a insegnare alla casa come si chiamano le luci, quali
routine partono all'alba e cosa sa della famiglia, finora non aveva modo di
salvare quel lavoro ne' di spostarlo su un'altra macchina. Riferimento:
issue #35.

## Cosa entra nell'archivio, e cosa no

Entra la **configurazione**: chi abita la casa, cosa sa, come si chiamano le
cose, cosa fa da sola. Sono le ore di lavoro che rifarle costerebbe.

Non entra quello che la casa si rifa' da sola in un minuto — i timer in corso,
i promemoria, le letture dell'energia, gli embedding — perche' un archivio che
contiene tutto e' un archivio che nessuno guarda, e perche' ripristinarlo
rimetterebbe in piedi timer scaduti mesi prima.

E soprattutto **non entrano i segreti**. Su questo il modulo e' esplicito, e
c'e' una guardia che esporta una casa piena di credenziali finte e poi cerca
ognuna di quelle stringhe nell'archivio intero.

## Perche' non e' `scripts/esporta_json.py`

Quello script esiste dalla v0.2.0 e scrive una cartella di file JSON. Ha due
difetti che lo rendono un salvataggio solo in apparenza:

1. scrive `users.json` con dentro la colonna `pin` — cioe' l'impronta del PIN
   di ogni persona di casa, in chiaro su disco, in una cartella che finisce
   volentieri su una chiavetta;
2. non dice di che versione e', quindi rileggerlo fra due versioni di Shinra
   e' un atto di fede.

Da qui in avanti quello che e' un segreto lo decide **questo** modulo, in un
posto solo, e lo script vecchio gli chiede.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from shinra import percorsi, versione
from shinra.config import secrets as segreti
from shinra.config import settings as impostazioni
from shinra.infra.db.depositi import DEPOSITI

logger = logging.getLogger("Shinra.Salvataggio")

# La versione del **formato dell'archivio**, non dell'applicazione. Sale solo
# quando la forma cambia in modo che una versione precedente non saprebbe
# rileggere, e allora si aggiunge una migrazione qui sotto.
VERSIONE = 1

# Lo schema 0 non e' mai stato scritto da nessuno: e' il nome che diamo alla
# cartella di file JSON prodotta da `scripts/esporta_json.py` dalla v0.2.0.
# Esiste su disco in casa di chi ha seguito quel consiglio, e deve poter
# rientrare.
SCHEMA_CARTELLA_JSON = 0

# Le tabelle che valgono la pena di essere salvate, e il perche' di ognuna.
TABELLE: dict[str, str] = {
    "users": "chi abita la casa: nomi, ruoli, preferenze",
    "ruoli": "i permessi che i ruoli danno, se sono stati personalizzati",
    "knowledge": "quello che la casa sa della famiglia",
    "device_aliases": "come si chiamano le cose, in casa, a voce",
    "modes": "le modalita': «cinema», «notte», «via»",
    "sources": "le fonti di notizie scelte",
}

# Quello che si rifa' da solo, elencato apposta: senza questo elenco scritto,
# la prossima tabella nuova finirebbe nell'archivio o ne resterebbe fuori
# senza che nessuno l'abbia deciso. `test_ogni_tabella_e_stata_decisa` lo
# verifica.
FUORI: dict[str, str] = {
    "timers": "durano minuti: ripristinarne uno di tre mesi fa non ha senso",
    "reminders": "come sopra, e sono legati a un momento che e' passato",
}

# Cosa si toglie da ogni riga prima di scriverla. La colonna `pin` e'
# l'impronta del PIN: sei cifre dietro una funzione di hash si ritrovano in
# pochi secondi, quindi vale come il PIN stesso.
CAMPI_SEGRETI_PER_TABELLA: dict[str, tuple[str, ...]] = {
    "users": ("pin",),
}


class ArchivioNonValido(Exception):
    """L'archivio non e' leggibile, o non e' un archivio di Shinra."""


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _configurazione_senza_segreti() -> dict[str, Any]:
    """La configurazione com'e' adesso, meno i campi dichiarati segreti.

    Non si rilegge `config.yaml` dal disco: i segreti possono arrivare
    dall'ambiente o da `.env` e nel file non comparirebbero comunque, mentre
    in memoria ci sono. Si parte quindi da cio' che l'applicazione ha davvero
    in mano, e si toglie — cosi' la guardia prova il caso peggiore.
    """
    dati = impostazioni.settings.model_dump()
    for sezione, campo in segreti.CAMPI_SEGRETI:
        if isinstance(dati.get(sezione), dict) and campo in dati[sezione]:
            dati[sezione][campo] = ""
    return dati


def riga_pubblica(tabella: str, riga: dict[str, Any]) -> dict[str, Any]:
    """La riga senza i campi che non devono uscire da questa macchina.

    E' pubblica apposta: anche `scripts/esporta_json.py` la usa, cosi' la
    domanda «cos'e' un segreto» ha una risposta sola invece di due copie che
    un giorno divergono. E' lo stesso motivo per cui la sessione si chiede a
    `sessione_dalla_richiesta` da un posto solo.
    """
    da_togliere = CAMPI_SEGRETI_PER_TABELLA.get(tabella, ())
    return {chiave: valore for chiave, valore in riga.items() if chiave not in da_togliere}


def esporta() -> dict[str, Any]:
    """L'archivio, come struttura. Chi lo scrive su disco e' `scrivi`."""
    tabelle = {
        nome: [riga_pubblica(nome, riga) for riga in DEPOSITI[nome].elenco()]
        for nome in TABELLE
        if nome in DEPOSITI
    }
    return {
        "shinra": {
            "schema": VERSIONE,
            "creato_il": _adesso(),
            "versione": versione.descrizione(),
        },
        "configurazione": _configurazione_senza_segreti(),
        "tabelle": tabelle,
    }


def scrivi(percorso: Path) -> dict[str, int]:
    """Scrive l'archivio, e restituisce quante voci per tabella.

    Scrittura atomica: se il processo muore a meta', l'archivio di prima e'
    ancora intero. E' il difetto che ha portato al database, e ripeterlo
    proprio nel salvataggio sarebbe beffardo.
    """
    archivio = esporta()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_suffix(percorso.suffix + ".tmp")
    temporaneo.write_text(json.dumps(archivio, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    temporaneo.replace(percorso)
    return {nome: len(voci) for nome, voci in archivio["tabelle"].items()}


def _da_cartella_json(cartella: Path) -> dict[str, Any]:
    """Legge la cartella prodotta da `scripts/esporta_json.py` (schema 0)."""
    from shinra.infra.db.importazione import SORGENTI

    tabelle: dict[str, list[dict[str, Any]]] = {}
    for nome_file, tabella in SORGENTI.items():
        percorso = cartella / nome_file
        if not percorso.exists():
            continue
        contenuto = json.loads(percorso.read_text(encoding="utf-8"))
        if not isinstance(contenuto, list):
            raise ArchivioNonValido(f"{nome_file} non contiene un elenco")
        tabelle[tabella] = contenuto
    if not tabelle:
        raise ArchivioNonValido(f"in {cartella} non c'e' nessun file di esportazione")
    return {
        "shinra": {"schema": SCHEMA_CARTELLA_JSON, "creato_il": "", "versione": ""},
        "configurazione": {},
        "tabelle": tabelle,
    }


def _migra(archivio: dict[str, Any]) -> dict[str, Any]:
    """Porta un archivio vecchio alla forma di adesso.

    Una migrazione per salto, applicate in fila: cosi' aggiungerne una domani
    non vuol dire rileggere quelle di ieri.
    """
    schema = archivio["shinra"]["schema"]
    if schema > VERSIONE:
        raise ArchivioNonValido(
            f"l'archivio e' di schema {schema} e questa versione di Shinra arriva "
            f"allo {VERSIONE}: serve una versione piu' recente per rileggerlo"
        )

    if schema == SCHEMA_CARTELLA_JSON:
        # Lo schema 0 portava anche timer e promemoria, che oggi non si
        # ripristinano: si lasciano cadere qui, dove si vede.
        archivio["tabelle"] = {nome: voci for nome, voci in archivio["tabelle"].items() if nome in TABELLE}
        # E portava la colonna `pin`. Non la si scrive mai piu', ma un
        # archivio vecchio ce l'ha: si toglie entrando.
        archivio["tabelle"] = {
            nome: [riga_pubblica(nome, riga) for riga in voci] for nome, voci in archivio["tabelle"].items()
        }
        archivio["shinra"]["schema"] = 1
        schema = 1

    return archivio


def leggi(percorso: Path) -> dict[str, Any]:
    """Un archivio dal disco, portato alla forma di adesso.

    Accetta sia il file unico di oggi sia la cartella di file JSON di ieri:
    chi ha un salvataggio vecchio non deve convertirlo a mano per rientrare.
    """
    if percorso.is_dir():
        return _migra(_da_cartella_json(percorso))

    if not percorso.exists():
        raise ArchivioNonValido(f"{percorso} non esiste")

    try:
        archivio = json.loads(percorso.read_text(encoding="utf-8"))
    except json.JSONDecodeError as errore:
        raise ArchivioNonValido(f"{percorso.name} non e' JSON leggibile: {errore}") from errore

    if not isinstance(archivio, dict) or "shinra" not in archivio:
        raise ArchivioNonValido(f"{percorso.name} non e' un archivio di Shinra: manca l'intestazione")
    if not isinstance(archivio["shinra"].get("schema"), int):
        raise ArchivioNonValido(f"{percorso.name} non dichiara di che schema e'")
    archivio.setdefault("tabelle", {})
    archivio.setdefault("configurazione", {})
    return _migra(archivio)


def anteprima(archivio: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Cosa succederebbe a ripristinare questo archivio, senza farlo.

    Ripristinare **sostituisce**: e' la sola cosa che abbia senso per una
    configurazione, perche' fondere due anagrafiche produce una casa che non
    e' ne' quella di prima ne' quella dell'archivio. Ma allora chi preme il
    pulsante deve poter vedere prima cosa perde.
    """
    quadro: dict[str, dict[str, int]] = {}
    for nome in TABELLE:
        if nome not in DEPOSITI:
            continue
        quadro[nome] = {
            "adesso": DEPOSITI[nome].conta(),
            "nell_archivio": len(archivio.get("tabelle", {}).get(nome, [])),
        }
    return quadro


def ripristina(archivio: dict[str, Any]) -> dict[str, int]:
    """Rimette la casa com'era. Sostituisce, non fonde.

    Le tabelle che l'archivio non porta **non** vengono svuotate: un archivio
    scritto da una versione che non conosceva le modalita' non deve
    cancellare le modalita' di chi lo rilegge.
    """
    scritte: dict[str, int] = {}
    for nome in TABELLE:
        if nome not in archivio.get("tabelle", {}) or nome not in DEPOSITI:
            continue
        voci = [riga_pubblica(nome, riga) for riga in archivio["tabelle"][nome]]
        scritte[nome] = DEPOSITI[nome].sostituisci_tutto(voci)
    logger.info("Ripristino: %s", ", ".join(f"{n} {q}" for n, q in scritte.items()) or "niente")
    return scritte


# Il nome che questo modulo da' ai suoi archivi. La rotazione cancella **solo**
# quello che corrisponde a questa forma: e' l'unica cosa che le impedisce di
# portarsi via un file che qualcuno aveva messo li' a mano.
PREFISSO = "shinra-"
SUFFISSO = ".json"
FORMA = f"{PREFISSO}*{SUFFISSO}"


def nome_predefinito(quando: Optional[datetime] = None) -> str:
    momento = (quando or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"{PREFISSO}{momento}{SUFFISSO}"


def cartella_predefinita() -> Path:
    return percorsi.DATI / "salvataggi"


def suoi_archivi(cartella: Path) -> list[Path]:
    """Gli archivi scritti da qui, dal piu' vecchio al piu' recente.

    L'ordine e' quello del nome, non della data di modifica: il nome porta il
    momento in cui l'archivio e' stato scritto, mentre la data di modifica la
    cambia chiunque copi la cartella da qualche parte — e una rotazione che
    sbaglia ordine cancella quello sbagliato.
    """
    if not cartella.is_dir():
        return []
    return sorted((f for f in cartella.glob(FORMA) if f.is_file()), key=lambda f: f.name)


def ruota(cartella: Path, da_conservare: int) -> list[Path]:
    """Toglie di mezzo gli archivi piu' vecchi. Restituisce quelli cancellati.

    Cancellare file automaticamente e' la cosa piu' pericolosa che questo
    modulo faccia, quindi e' la piu' stretta:

    - guarda **solo** dentro la cartella che le viene detta, senza scendere
      nelle sottocartelle;
    - tocca solo i nomi della forma `shinra-*.json`, cioe' quelli che scrive
      lei. Un `note.txt`, un `shinra.db`, un archivio rinominato a mano da
      qualcuno per metterlo al sicuro restano dove sono;
    - con `da_conservare` a zero o meno non cancella niente. Chi vuole
      tenerle tutte lo dice, e non si ritrova senza per una svista.
    """
    if da_conservare <= 0:
        return []
    archivi = suoi_archivi(cartella)
    da_togliere = archivi[: max(0, len(archivi) - da_conservare)]
    for vecchio in da_togliere:
        vecchio.unlink()
    if da_togliere:
        logger.info(
            "Rotazione: tolti %d archivi vecchi, ne restano %d.",
            len(da_togliere),
            da_conservare,
        )
    return da_togliere


def salva_e_ruota() -> Path:
    """Scrive un archivio nella cartella di casa e poi fa spazio.

    In quest'ordine apposta: se la rotazione girasse per prima, un guasto
    nella scrittura lascerebbe una copia in meno e nessuna nuova.
    """
    cartella = cartella_predefinita()
    percorso = cartella / nome_predefinito()
    scrivi(percorso)
    ruota(cartella, impostazioni.settings.salvataggio.da_conservare)
    return percorso


# --------------------------------------------------------------------------
# Il salvataggio che si fa da solo
# --------------------------------------------------------------------------

JOB_SALVATAGGIO = "salvataggio_automatico"


def _gira() -> None:
    """Il giro programmato. Non solleva mai: un backup che fa cadere la casa
    e' peggio di un backup che manca, e chi lo guarda e' il log."""
    try:
        percorso = salva_e_ruota()
        logger.info("Salvataggio automatico in %s", percorso)
    except Exception:
        logger.exception("Il salvataggio automatico non e' riuscito")


class ServizioSalvataggio:
    """Un archivio al giorno, senza che nessuno debba ricordarsene.

    Un backup che bisogna ricordarsi di fare e' un backup che non esiste. Qui
    il costo e' un file JSON da qualche decina di kilobyte — la
    configurazione, non i dati — quindi e' acceso per difetto.
    """

    def __init__(self) -> None:
        self.attivo = False

    def avvia(self) -> bool:
        from shinra.infra.scheduler.motore import scheduler

        configurazione = impostazioni.settings.salvataggio
        if not impostazioni.settings.salvataggio.abilitato:
            logger.info("Salvataggio automatico spento dalla configurazione.")
            return False
        if configurazione.ogni_ore <= 0:
            logger.warning(
                "salvataggio.ogni_ore e' %s: non e' un intervallo, il salvataggio "
                "automatico resta spento.",
                configurazione.ogni_ore,
            )
            return False
        if not scheduler.programma_periodico(JOB_SALVATAGGIO, _gira, ore=configurazione.ogni_ore):
            return False
        self.attivo = True
        logger.info(
            "Salvataggio automatico ogni %g ore, ne conservo %d.",
            configurazione.ogni_ore,
            configurazione.da_conservare,
        )
        return True

    def ferma(self) -> None:
        from shinra.infra.scheduler.motore import scheduler

        scheduler.annulla(JOB_SALVATAGGIO)
        self.attivo = False


servizio_salvataggio = ServizioSalvataggio()
