"""Configurazione comune della suite di test.

La suite gira sul pacchetto installato (`pip install -e ".[dev]"`), non sui
file: e' il motivo per cui il codice sta sotto `src/` (issue #16). Se
`src/shinra/` fosse raggiungibile dalla cartella di lavoro, i test
proverebbero i sorgenti invece di cio' che si installa davvero — e le due
cose possono differire, per esempio quando `pyproject.toml` dimentica un
pacchetto.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent

_MODELLO: Path | None = None


def _archivio_modello(tmp_path_factory) -> Path:
    """Un database gia' pronto, costruito una volta sola per tutta la suite."""
    global _MODELLO
    if _MODELLO is None:
        from shinra.infra.db import importazione, motore

        _MODELLO = tmp_path_factory.mktemp("modello") / "modello.db"
        importazione.crea_vuoto(_MODELLO)
        importazione.importa(importazione.leggi_tutto(RADICE / "data" / "examples"))

        # Il database e' in modalita' WAL: finche' non si fa il checkpoint,
        # parte delle scritture vive nel file `.db-wal` accanto. Copiare solo
        # il `.db` produce un database a cui mancano pezzi — e' successo:
        # dopo una migrazione che ricrea una tabella, quella tabella
        # semplicemente non c'era. E' lo stesso motivo per cui deploy.sh non
        # fa il backup con tar.
        with motore.motore().connect() as connessione:
            connessione.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
        motore.reimposta(_MODELLO)
    return _MODELLO


@pytest.fixture(autouse=True)
def archivio_isolato(tmp_path_factory):
    """Ogni test parte da un database suo, vuoto e appena creato.

    Senza questo, la suite scriverebbe in `data/shinra.db` — che su una
    macchina vera contiene l'anagrafica, i timer e la conoscenza di una
    famiglia. Un test che sbaglia non deve poter cancellare i dati di casa,
    e non deve nemmeno poterli leggere per caso e passare per quello.

    Il database di prova viene riempito con i file di `data/examples/`: sono
    la casa di esempio, quella che vede anche chi installa Shinra per la
    prima volta.
    """
    from shinra.infra.db import motore

    percorso = tmp_path_factory.mktemp("archivio") / "prova.db"
    # Costruire schema e dati di esempio a ogni test costa quasi mezzo minuto
    # sull'intera suite. Si costruiscono una volta e poi si copia il file:
    # SQLite e' un file, copiarlo e' l'operazione piu' veloce che ci sia.
    shutil.copyfile(_archivio_modello(tmp_path_factory), percorso)
    motore.reimposta(percorso)
    yield percorso
    motore.reimposta(percorso)


PIN_DI_PROVA = "482913"


@pytest.fixture
def cliente_autenticato():
    """Un client HTTP che e' entrato in casa, come fa la dashboard.

    Spegnere `settings.security.auth_enabled` da dentro il test non funziona
    e per un motivo giusto: se manca `config/config.yaml`, l'avvio genera il
    segreto di sessione, salva la configurazione e la rilegge — riportando il
    valore a quello scritto su disco. Il test passava sulla copia di lavoro,
    dove quel file c'e', e falliva in CI, dove non c'e'. Autenticarsi davvero
    e' anche piu' fedele a cio' che succede in casa.
    """
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.services.user_manager import user_manager

    with TestClient(app) as client:
        utente = user_manager.get_users()[0]
        user_manager.imposta_pin(utente.id, PIN_DI_PROVA)
        sicurezza.azzera_stato()
        entrato = client.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": utente.id})
        assert entrato.status_code == 200, entrato.text
        yield client
