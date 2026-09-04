"""Il motore del database: un file SQLite, aperto come si deve.

Prima tutto lo stato viveva in sei file JSON riscritti per intero a ogni
modifica, senza lock e senza sostituzione atomica. Due richieste in parallelo
— la dashboard e l'Echo, che e' lo scenario normale di casa — potevano
perdere una modifica; un'interruzione a meta' scrittura lasciava un file
troncato che all'avvio successivo veniva scartato in silenzio, restituendo
una lista vuota. Perdita totale dei dati senza un solo messaggio d'errore.

Vedi docs/adr/0002-sqlite-al-posto-dei-file-json.md
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("Shinra.Archivio")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ARCHIVIO = DATA_DIR / "shinra.db"

_motore: Optional[Engine] = None
_crea_sessione: Optional[sessionmaker] = None


def _applica_pragma(connessione, _record) -> None:
    """Le impostazioni che rendono SQLite adatto a due scrittori.

    Sono quattro, e ognuna copre un guasto visto o previsto:

    - `journal_mode=WAL`: chi legge non blocca chi scrive. Senza, la
      dashboard che si aggiorna ogni pochi secondi litiga con l'Echo che
      salva un timer.
    - `busy_timeout`: se il database e' occupato, aspetta invece di
      arrendersi. E' la differenza fra una richiesta lenta e una fallita.
    - `synchronous=NORMAL`: con WAL e' sicuro contro il crash del processo,
      che e' lo scenario reale (un `systemctl restart` di troppo). FULL
      proteggerebbe in piu' dal blackout, al prezzo di un fsync per
      transazione: su una scheda con SD, si sente.
    - `foreign_keys=ON`: SQLite le ignora se non glielo si chiede. Un
      promemoria non deve poter appartenere a un utente cancellato.
    """
    cursore = connessione.cursor()
    cursore.execute("PRAGMA journal_mode=WAL")
    cursore.execute("PRAGMA busy_timeout=5000")
    cursore.execute("PRAGMA synchronous=NORMAL")
    cursore.execute("PRAGMA foreign_keys=ON")
    cursore.close()


def percorso_archivio() -> Path:
    return ARCHIVIO


def motore() -> Engine:
    """Il motore condiviso, creato alla prima richiesta."""
    global _motore, _crea_sessione
    if _motore is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _motore = create_engine(
            f"sqlite:///{ARCHIVIO}",
            # SQLite di suo vieta di usare una connessione da un thread
            # diverso da quello che l'ha aperta. FastAPI esegue le dipendenze
            # sincrone in un pool di thread: senza questo, meta' delle
            # richieste fallirebbe.
            connect_args={"check_same_thread": False},
            future=True,
        )
        event.listen(_motore, "connect", _applica_pragma)
        _crea_sessione = sessionmaker(bind=_motore, expire_on_commit=False, future=True)
        logger.info("Archivio aperto: %s", ARCHIVIO)
    return _motore


def reimposta(percorso: Optional[Path] = None) -> None:
    """Chiude il motore e, se richiesto, ne apre uno su un altro file.

    Serve ai test e allo script di migrazione, che scrive su un database
    nuovo senza toccare quello in uso.
    """
    global _motore, _crea_sessione, ARCHIVIO
    if _motore is not None:
        _motore.dispose()
    _motore = None
    _crea_sessione = None
    if percorso is not None:
        ARCHIVIO = Path(percorso)


@contextmanager
def sessione() -> Iterator[Session]:
    """Una transazione: o va a buon fine per intero, o non lascia traccia.

    E' la proprieta' che i file JSON non avevano. Un errore a meta' di un
    salvataggio non lascia piu' meta' dei dati scritti.
    """
    motore()
    assert _crea_sessione is not None
    s = _crea_sessione()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
