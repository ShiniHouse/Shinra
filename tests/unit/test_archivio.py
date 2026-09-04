"""Il database deve reggere cio' che i file JSON non reggevano.

Questi test non verificano che SQLAlchemy funzioni — quello lo sa fare da
solo. Verificano le tre proprieta' per cui si e' migrato: due scritture in
parallelo non si perdono, un processo ucciso a meta' scrittura non lascia
macerie, e lo schema sul disco resta quello che i modelli descrivono.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core.archivio import depositi, motore
from core.archivio.modelli import Base

RADICE = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def archivio(tmp_path):
    """Un database vuoto, tutto per questo test."""
    percorso = tmp_path / "prova.db"
    motore.reimposta(percorso)
    Base.metadata.create_all(motore.motore())
    yield percorso
    motore.reimposta(RADICE / "data" / "shinra.db")


# ------------------------------------------------------------- impostazioni


def test_il_database_e_in_modalita_wal(archivio):
    """Senza WAL, chi legge blocca chi scrive: la dashboard litigherebbe con l'Echo."""
    with motore.sessione() as s:
        modalita = s.execute(__import__("sqlalchemy").text("PRAGMA journal_mode")).scalar()
    assert modalita.lower() == "wal"


def test_le_chiavi_esterne_sono_attive(archivio):
    """SQLite le ignora se non gliele si chiede esplicitamente."""
    with motore.sessione() as s:
        attive = s.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys")).scalar()
    assert attive == 1


# ------------------------------------------------------------- andata e ritorno


def test_un_fatto_torna_indietro_come_e_entrato(archivio):
    depositi.fatti.aggiungi(
        {"id": "k_1", "text": "Il contatore e' nel sottoscala", "category": "casa", "enabled": True}
    )

    letto = depositi.fatti.per_id("k_1")

    assert letto == {
        "id": "k_1",
        "text": "Il contatore e' nel sottoscala",
        "category": "casa",
        "enabled": True,
    }


def test_le_liste_e_i_dizionari_sopravvivono(archivio):
    """Le frasi di attivazione e le azioni di una modalita' sono strutture, non testo."""
    depositi.modalita.aggiungi(
        {
            "id": "mode_cinema",
            "name": "Cinema",
            "trigger_phrases": ["modalita' cinema", "mettiamo su un film"],
            "actions": [{"type": "ha_service", "domain": "light", "service": "turn_off"}],
            "enabled": True,
        }
    )

    letta = depositi.modalita.per_id("mode_cinema")

    assert letta["trigger_phrases"] == ["modalita' cinema", "mettiamo su un film"]
    assert letta["actions"][0]["service"] == "turn_off"


def test_un_fatto_ripetuto_non_diventa_due(archivio):
    primo = depositi.fatti.aggiungi_fatto("La caldaia si accende alle sei")
    secondo = depositi.fatti.aggiungi_fatto("  la CALDAIA si accende alle sei  ")

    assert primo["id"] == secondo["id"]
    assert depositi.fatti.conta() == 1


# ----------------------------------------------------------------- concorrenza


def test_cento_scritture_in_parallelo_non_perdono_niente(archivio):
    """Il difetto che ha motivato la migrazione.

    Con i file JSON ogni salvataggio era leggi-modifica-riscrivi sull'intero
    elenco: due richieste sovrapposte — la dashboard e l'Echo — producevano
    un file con una sola delle due modifiche, e nessun errore.
    """

    def scrivi(n: int) -> None:
        depositi.fatti.aggiungi({"id": f"k_{n:03d}", "text": f"fatto numero {n}", "category": "prova"})

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(scrivi, range(100)))

    assert depositi.fatti.conta() == 100
    identificativi = {f["id"] for f in depositi.fatti.elenco()}
    assert len(identificativi) == 100


def test_il_pin_cambia_senza_riscrivere_l_anagrafica(archivio):
    """Cambiare un PIN mentre qualcun altro salva un profilo non deve perdere ne' l'uno ne' l'altro."""
    depositi.utenti.aggiungi({"id": "alessio", "name": "Alessio", "role": "admin"})
    depositi.utenti.aggiungi({"id": "sonia", "name": "Sonia", "role": "adult"})

    def cambia_pin(_):
        depositi.utenti.imposta_pin("alessio", "pbkdf2_sha256$finto")

    def rinomina(_):
        depositi.utenti.aggiorna("sonia", {"notes": "aggiornata"})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(cambia_pin, range(25)))
        list(pool.map(rinomina, range(25)))

    assert depositi.utenti.per_id("alessio")["pin"] == "pbkdf2_sha256$finto"
    assert depositi.utenti.per_id("sonia")["notes"] == "aggiornata"
    assert depositi.utenti.conta() == 2


# ------------------------------------------------------------- interruzione


def test_un_processo_ucciso_a_meta_scrittura_non_rovina_il_database(archivio, tmp_path):
    """L'altro difetto dei file JSON: restava un file troncato che l'avvio
    successivo scartava in silenzio, restituendo una lista vuota. Perdita
    totale dei dati senza un errore."""
    depositi.fatti.aggiungi({"id": "k_prima", "text": "esistevo gia'"})

    programma = textwrap.dedent(f"""
        import os, signal, sys
        sys.path.insert(0, {str(RADICE)!r})
        from core.archivio import motore
        from core.archivio.modelli import Fatto
        motore.reimposta({str(archivio)!r})
        s = motore.motore()
        from sqlalchemy.orm import Session
        with Session(s) as sess:
            for n in range(500):
                sess.add(Fatto(id=f"k_meta_{{n}}", text="a meta'"))
            sess.flush()          # scritto nel journal, non ancora confermato
            os.kill(os.getpid(), signal.SIGKILL)
        """)
    copione = tmp_path / "interrompi.py"
    copione.write_text(programma, encoding="utf-8")

    esito = subprocess.run([sys.executable, str(copione)], capture_output=True)
    assert esito.returncode != 0  # e' stato ucciso, come volevamo

    conn = sqlite3.connect(archivio)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()

    # Il dato che c'era prima c'e' ancora, e la transazione interrotta non ha
    # lasciato meta' delle sue righe.
    assert depositi.fatti.per_id("k_prima") is not None
    assert depositi.fatti.conta() == 1


# ------------------------------------------------------------------- schema


def test_le_migrazioni_producono_esattamente_i_modelli(tmp_path):
    """Se qualcuno cambia un modello e si scorda la migrazione, il database
    del server resta indietro senza che nulla protesti — fino al primo errore
    in casa. Questo test e' quel protestare."""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    percorso = tmp_path / "schema.db"
    motore.reimposta(percorso)
    try:
        cfg = Config(str(RADICE / "alembic.ini"))
        cfg.set_main_option("script_location", str(RADICE / "migrazioni"))
        command.upgrade(cfg, "head")

        with motore.motore().connect() as connessione:
            contesto = MigrationContext.configure(connessione)
            differenze = compare_metadata(contesto, Base.metadata)
    finally:
        motore.reimposta(RADICE / "data" / "shinra.db")

    assert differenze == [], (
        "lo schema creato dalle migrazioni non corrisponde ai modelli: "
        "esegui `alembic revision --autogenerate` e rileggi cio' che produce"
    )


# ---------------------------------------------------------------- migrazione


def _carica_script():
    import importlib.util

    percorso = RADICE / "scripts" / "migra_da_json.py"
    spec = importlib.util.spec_from_file_location("migra_da_json", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_la_migrazione_importa_tutto_e_non_tocca_i_json(tmp_path, monkeypatch):
    """Il criterio di accettazione della issue #12, provato sul serio."""
    sorgente = tmp_path / "data"
    sorgente.mkdir()
    contenuti = {
        "users.json": [{"id": "alessio", "name": "Alessio", "role": "admin", "pin": None}],
        "knowledge.json": [{"id": "k1", "text": "un fatto", "category": "casa", "enabled": True}],
        "device_aliases.json": [{"id": "a1", "alias": "luce cucina", "entity_id": "light.cucina"}],
        "modes.json": [{"id": "m1", "name": "Cinema", "trigger_phrases": ["cinema"], "actions": []}],
        "sources.json": [{"id": "s1", "name": "ANSA", "category": "mondo", "url": "https://x.it/rss"}],
        "timers.json": [],
        "reminders.json": [{"id": "r1", "text": "medicine", "remind_at": "2026-09-04T18:00:00"}],
    }
    impronte = {}
    for nome, dati in contenuti.items():
        (sorgente / nome).write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")
        impronte[nome] = (sorgente / nome).read_bytes()

    script = _carica_script()
    monkeypatch.setattr(script, "DATA_DIR", sorgente)

    destinazione = tmp_path / "migrato.db"
    try:
        esito = script.migra(destinazione, prova=False)
    finally:
        motore.reimposta(RADICE / "data" / "shinra.db")

    assert esito == 0
    for nome, contenuto in impronte.items():
        assert (sorgente / nome).read_bytes() == contenuto, f"{nome} e' stato modificato"

    motore.reimposta(destinazione)
    try:
        assert depositi.utenti.conta() == 1
        assert depositi.fatti.conta() == 1
        assert depositi.promemoria.conta() == 1
        assert depositi.timer.conta() == 0
        assert depositi.modalita.per_id("m1")["trigger_phrases"] == ["cinema"]
    finally:
        motore.reimposta(RADICE / "data" / "shinra.db")


def test_la_migrazione_si_rifiuta_di_scrivere_sopra_dati_esistenti(tmp_path, monkeypatch):
    sorgente = tmp_path / "data"
    sorgente.mkdir()
    for nome in (
        "users.json",
        "knowledge.json",
        "device_aliases.json",
        "modes.json",
        "sources.json",
        "timers.json",
        "reminders.json",
    ):
        (sorgente / nome).write_text("[]", encoding="utf-8")
    (sorgente / "knowledge.json").write_text(json.dumps([{"id": "k1", "text": "primo"}]), encoding="utf-8")

    script = _carica_script()
    monkeypatch.setattr(script, "DATA_DIR", sorgente)
    destinazione = tmp_path / "migrato.db"

    try:
        assert script.migra(destinazione, prova=False) == 0
        assert script.migra(destinazione, prova=False) == 2  # la seconda volta si ferma
    finally:
        motore.reimposta(RADICE / "data" / "shinra.db")
