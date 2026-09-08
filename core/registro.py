"""Il registro delle azioni: chi ha fatto cosa in casa, e com'e' andata.

Shinra comanda luci, prese e clima — e presto serrature e allarme — e fino
alla v0.2.0 non ne restava traccia da nessuna parte. Alla domanda «chi ha
spento il riscaldamento alle tre di notte?» non c'era risposta: i log
finivano sullo standard output, senza rotazione e senza un filo che legasse
fra loro le righe di una stessa richiesta.

Tre cose stanno insieme qui dentro:

- **Il contesto della richiesta**, in una `ContextVar`. Chi ha parlato, da
  quale canale e con quale identificativo di correlazione seguono la
  richiesta lungo tutta la catena delle chiamate, senza dover aggiungere tre
  parametri a ogni funzione fino ai tool. Una ContextVar e' locale al task
  asincrono: due richieste in parallelo non si mescolano.

- **La scrittura delle voci**, che oscura sempre i segreti. Un registro che
  copia dentro di se' un token di Home Assistant e' peggio del non averlo.

- **Il log applicativo in JSON con rotazione**, che porta con se' la stessa
  correlazione: dal registro si passa al log e viceversa.

Riferimento: issue #15.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from core import percorsi

logger = logging.getLogger("Shinra.Registro")

CARTELLA_LOG = percorsi.LOG
FILE_LOG = CARTELLA_LOG / "shinra.jsonl"

# Nomi di campo il cui contenuto non va mai scritto da nessuna parte. Il
# confronto e' per sottostringa e senza maiuscole: `ha_token`, `admin_pin` e
# `Authorization` cadono tutti qui dentro.
PAROLE_SEGRETE = (
    "token",
    "pin",
    "password",
    "passwd",
    "secret",
    "segreto",
    "authorization",
    "api_key",
    "apikey",
    "credential",
)
MASCHERA = "***"

ESITO_OK = "ok"
ESITO_ERRORE = "errore"
ESITO_NEGATO = "negato"


@dataclass
class ContestoRichiesta:
    correlazione: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    attore: Optional[str] = None
    canale: str = ""


_contesto: ContextVar[Optional[ContestoRichiesta]] = ContextVar("contesto_richiesta", default=None)


def contesto() -> ContestoRichiesta:
    """Il contesto della richiesta in corso, creandone uno se manca.

    Manca, per esempio, in uno script eseguito a mano: le sue azioni vanno
    comunque registrate, con una correlazione tutta loro.
    """
    corrente = _contesto.get()
    if corrente is None:
        corrente = ContestoRichiesta()
        _contesto.set(corrente)
    return corrente


def apri_contesto(attore: Optional[str] = None, canale: str = "") -> ContestoRichiesta:
    nuovo = ContestoRichiesta(attore=attore, canale=canale)
    _contesto.set(nuovo)
    return nuovo


def imposta_attore(attore: Optional[str]) -> None:
    """L'identita' spesso si scopre a meta' strada.

    Alexa consegna l'identificativo dentro gli attributi di sessione, e
    l'agente risolve il profilo solo dopo aver ricevuto il testo: il
    contesto nasce anonimo e viene completato quando si sa chi ha parlato.
    """
    if attore:
        contesto().attore = attore


# --------------------------------------------------------------- segreti


def oscura(valore: Any, nome_campo: str = "") -> Any:
    """Sostituisce con `***` tutto cio' che somiglia a un segreto.

    Si guarda il nome del campo, non il contenuto: un token e' una stringa
    qualunque, e riconoscerlo dal testo sarebbe un indovinello. Il nome
    invece lo sappiamo sempre.
    """
    if any(parola in nome_campo.lower() for parola in PAROLE_SEGRETE):
        return MASCHERA if valore not in (None, "", [], {}) else valore
    if isinstance(valore, dict):
        return {c: oscura(v, str(c)) for c, v in valore.items()}
    if isinstance(valore, (list, tuple)):
        return [oscura(v, nome_campo) for v in valore]
    return valore


# ------------------------------------------------------------- scrittura


def registra(
    azione: str,
    esito: str = ESITO_OK,
    dettagli: Optional[dict[str, Any]] = None,
    durata_ms: Optional[int] = None,
    attore: Optional[str] = None,
    canale: Optional[str] = None,
) -> None:
    """Scrive una voce. Non solleva mai.

    Un guasto nel registro non deve impedire di spegnere una luce: se la
    scrittura fallisce, resta nel log applicativo e si va avanti.
    """
    ctx = contesto()
    try:
        from core.archivio.modelli import VoceRegistro
        from core.archivio.motore import sessione

        with sessione() as s:
            s.add(
                VoceRegistro(
                    attore=attore or ctx.attore,
                    canale=canale or ctx.canale,
                    azione=azione,
                    dettagli=oscura(dettagli or {}),
                    esito=esito,
                    durata_ms=durata_ms,
                    correlazione=ctx.correlazione,
                )
            )
    except Exception as e:
        logger.error("Voce di registro non scritta (%s): %s", azione, e)


@contextmanager
def traccia(
    azione: str, dettagli: Optional[dict[str, Any]] = None, canale: Optional[str] = None
) -> Iterator[dict]:
    """Registra un'operazione misurandone la durata, riuscita o fallita.

    Il blocco riceve un dizionario in cui puo' aggiungere dettagli scoperti
    strada facendo, e puo' scrivere `esito` per correggere il verdetto —
    serve ai tool, che segnalano gli errori restituendoli invece che
    sollevandoli.
    """
    inizio = time.perf_counter()
    stato: dict[str, Any] = {"esito": ESITO_OK, "dettagli": dict(dettagli or {})}
    try:
        yield stato
    except Exception as e:
        stato["esito"] = ESITO_ERRORE
        stato["dettagli"]["errore"] = str(e)
        raise
    finally:
        registra(
            azione,
            esito=stato["esito"],
            dettagli=stato["dettagli"],
            durata_ms=int((time.perf_counter() - inizio) * 1000),
            canale=canale,
        )


# ------------------------------------------------------------- lettura


def voci(
    limite: int = 100,
    attore: Optional[str] = None,
    azione: Optional[str] = None,
    canale: Optional[str] = None,
    esito: Optional[str] = None,
    correlazione: Optional[str] = None,
    dal: Optional[datetime] = None,
    al: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Le voci piu' recenti, filtrate. E' cio' che risponde a «chi ha acceso cosa»."""
    from sqlalchemy import select

    from core.archivio.modelli import VoceRegistro
    from core.archivio.motore import sessione

    query = select(VoceRegistro).order_by(VoceRegistro.momento.desc(), VoceRegistro.id.desc())
    if attore:
        query = query.where(VoceRegistro.attore == attore)
    if azione:
        query = query.where(VoceRegistro.azione == azione)
    if canale:
        query = query.where(VoceRegistro.canale == canale)
    if esito:
        query = query.where(VoceRegistro.esito == esito)
    if correlazione:
        query = query.where(VoceRegistro.correlazione == correlazione)
    if dal:
        query = query.where(VoceRegistro.momento >= dal)
    if al:
        query = query.where(VoceRegistro.momento <= al)
    query = query.limit(max(1, min(limite, 1000)))

    with sessione() as s:
        return [
            {
                "id": v.id,
                "momento": v.momento.isoformat(),
                "attore": v.attore,
                "canale": v.canale,
                "azione": v.azione,
                "dettagli": v.dettagli,
                "esito": v.esito,
                "durata_ms": v.durata_ms,
                "correlazione": v.correlazione,
            }
            for v in s.scalars(query).all()
        ]


def pulisci(giorni: int) -> int:
    """Cancella le voci piu' vecchie del periodo di conservazione.

    Con `giorni <= 0` non cancella niente: e' il modo di dire «conserva tutto».
    """
    if giorni <= 0:
        return 0

    from sqlalchemy import delete

    from core.archivio.modelli import VoceRegistro
    from core.archivio.motore import sessione

    limite = datetime.now(timezone.utc) - timedelta(days=giorni)
    with sessione() as s:
        esito = s.execute(delete(VoceRegistro).where(VoceRegistro.momento < limite))
        quante = esito.rowcount or 0  # type: ignore[attr-defined]
    if quante:
        logger.info("Registro: %d voci oltre i %d giorni rimosse.", quante, giorni)
    return quante


# --------------------------------------------------- log applicativo JSON


class FormatoJson(logging.Formatter):
    """Una riga di log = un oggetto JSON, con la correlazione della richiesta."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = _contesto.get()
        voce = {
            "momento": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "livello": record.levelname,
            "origine": record.name,
            "messaggio": record.getMessage(),
        }
        if ctx is not None:
            voce["correlazione"] = ctx.correlazione
            if ctx.attore:
                voce["attore"] = ctx.attore
            if ctx.canale:
                voce["canale"] = ctx.canale
        if record.exc_info:
            voce["eccezione"] = self.formatException(record.exc_info)
        return json.dumps(voce, ensure_ascii=False)


def configura_log_json(megabyte: int = 5, copie: int = 5) -> Optional[Path]:
    """Aggiunge il file di log strutturato, senza toccare quello a schermo.

    Con la rotazione, perche' un log che riempie il disco di casa spegne
    l'assistente nel modo piu' stupido possibile.
    """
    try:
        CARTELLA_LOG.mkdir(parents=True, exist_ok=True)
        radice = logging.getLogger()
        if any(getattr(h, "_shinra_json", False) for h in radice.handlers):
            return FILE_LOG
        gestore = logging.handlers.RotatingFileHandler(
            FILE_LOG, maxBytes=megabyte * 1024 * 1024, backupCount=copie, encoding="utf-8"
        )
        gestore.setFormatter(FormatoJson())
        gestore._shinra_json = True  # type: ignore[attr-defined]
        radice.addHandler(gestore)
        return FILE_LOG
    except OSError as e:
        logger.error("Log JSON non attivato: %s", e)
        return None
