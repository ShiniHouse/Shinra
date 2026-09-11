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

from shinra.infra.db import depositi, importazione, motore
from shinra.infra.db.modelli import Base

RADICE = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def archivio(tmp_path):
    """Un database vuoto, tutto per questo test."""
    percorso = tmp_path / "prova.db"
    importazione.crea_vuoto(percorso)
    yield percorso


# --------------------------------------------------------- il log dell'hub


def test_applicare_le_migrazioni_non_riconfigura_il_logging(archivio):
    """Il difetto per cui in produzione l'hub non raccontava piu' niente.

    `migrazioni/env.py` chiamava `fileConfig(alembic.ini)` sempre. Quel file
    porta il logger radice a WARNING e, per difetto, **spegne uno per uno**
    tutti i logger gia' esistenti. Da riga di comando e' innocuo: quel
    processo fa solo migrazioni. Ma le migrazioni girano anche all'avvio
    dell'applicazione, prima di tutto il resto — e da li' in poi ogni riga
    INFO dell'hub spariva.

    Non si notava perche' gli avvisi continuavano a passare: il journal
    sembrava funzionante, e mancava solo tutto quello che serviva a capire.
    Il microfono che non trascriveva e' stato diagnosticato al buio per
    questo: «Carico il modello di trascrizione» veniva scritto e buttato via.
    """
    import logging

    radice = logging.getLogger()
    livello_prima = radice.level
    radice.setLevel(logging.INFO)
    spia = logging.getLogger("Shinra.ProvaDelLog")

    try:
        assert spia.isEnabledFor(logging.INFO), "il test parte da uno stato che non prova niente"

        importazione.applica_migrazioni()

        assert not spia.disabled, "le migrazioni hanno spento un logger dell'applicazione"
        assert radice.level == logging.INFO, "le migrazioni hanno abbassato il livello del radice"
        assert spia.isEnabledFor(logging.INFO), "l'INFO dell'hub non arriva piu' da nessuna parte"
    finally:
        radice.setLevel(livello_prima)
        spia.disabled = False


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
        from shinra.infra.db import importazione, motore
        from shinra.infra.db.modelli import Fatto
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
    cfg = Config(str(RADICE / "alembic.ini"))
    cfg.set_main_option("script_location", str(RADICE / "migrazioni"))
    command.upgrade(cfg, "head")

    with motore.motore().connect() as connessione:
        contesto = MigrationContext.configure(connessione)
        differenze = compare_metadata(contesto, Base.metadata)

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

    from shinra.infra.db import importazione

    script = _carica_script()
    monkeypatch.setattr(importazione, "DATA_DIR", sorgente)

    destinazione = tmp_path / "migrato.db"
    esito = script.migra(destinazione, prova=False)

    assert esito == 0
    for nome, contenuto in impronte.items():
        assert (sorgente / nome).read_bytes() == contenuto, f"{nome} e' stato modificato"

    motore.reimposta(destinazione)
    assert depositi.utenti.conta() == 1
    assert depositi.fatti.conta() == 1
    assert depositi.promemoria.conta() == 1
    assert depositi.timer.conta() == 0
    assert depositi.modalita.per_id("m1")["trigger_phrases"] == ["cinema"]


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

    from shinra.infra.db import importazione

    script = _carica_script()
    monkeypatch.setattr(importazione, "DATA_DIR", sorgente)
    destinazione = tmp_path / "migrato.db"

    assert script.migra(destinazione, prova=False) == 0
    assert script.migra(destinazione, prova=False) == 2  # la seconda volta si ferma


# ------------------------------------------------------------- primo avvio


def test_al_primo_avvio_i_dati_di_esempio_finiscono_nel_database(tmp_path, monkeypatch):
    """Un'installazione nuova deve trovarsi una casa d'esempio funzionante,
    senza che nessuno lanci niente a mano."""
    import shutil as _shutil

    from shinra.api import app as modulo_app
    from shinra.infra import data_store as modulo_dati
    from shinra.infra.db import importazione

    cartella = tmp_path / "data"
    cartella.mkdir()
    _shutil.copytree(RADICE / "data" / "examples", cartella / "examples")

    monkeypatch.setattr(modulo_dati, "DATA_DIR", cartella)
    monkeypatch.setattr(modulo_dati, "EXAMPLES_DIR", cartella / "examples")
    monkeypatch.setattr(importazione, "DATA_DIR", cartella)
    motore.reimposta(tmp_path / "nuovo.db")

    modulo_app._prepara_archivio()

    assert depositi.utenti.conta() >= 1
    assert depositi.fonti.conta() >= 1
    # E i file JSON esistono: sono il backup, e la sorgente se si ricomincia.
    assert (cartella / "users.json").exists()


def test_un_riavvio_non_riporta_indietro_cio_che_e_stato_cancellato(tmp_path, monkeypatch):
    """`importa_se_vuoto` importa solo su un database completamente vuoto.

    Senza questa condizione, ogni riavvio del servizio rimetterebbe dentro i
    profili e i fatti cancellati dalle impostazioni: l'utente li toglie, il
    servizio riparte, e sono di nuovo li'.
    """
    from shinra.infra.db import importazione

    cartella = tmp_path / "data"
    cartella.mkdir()
    (cartella / "knowledge.json").write_text(
        json.dumps([{"id": "k_vecchio", "text": "cancellato dall'utente"}]), encoding="utf-8"
    )
    monkeypatch.setattr(importazione, "DATA_DIR", cartella)

    # Il database di questo test non e' vuoto: la fixture lo riempie con la
    # casa d'esempio, esattamente come lo sarebbe quello di una casa vera.
    assert not importazione.archivio_vuoto()

    assert importazione.importa_se_vuoto() == {}
    assert depositi.fatti.per_id("k_vecchio") is None


def test_l_esportazione_rende_i_dati_leggibili_senza_shinra(tmp_path):
    """Il JSON resta il formato di backup: si apre con un editor, anche fra
    dieci anni e senza avere Shinra installato."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("esporta_json", RADICE / "scripts" / "esporta_json.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    depositi.fatti.aggiungi({"id": "k_1", "text": "La caldaia e' in bagno"})

    destinazione = tmp_path / "esportazione"
    scritti = script.esporta(destinazione)

    assert scritti["knowledge.json"] >= 1
    contenuto = json.loads((destinazione / "knowledge.json").read_text(encoding="utf-8"))
    assert any(f["text"] == "La caldaia e' in bagno" for f in contenuto)


# --------------------------------- le funzioni di prima, dopo la migrazione


@pytest.mark.parametrize(
    "rotta",
    [
        "/api/users",
        "/api/knowledge",
        "/api/sources",
        "/api/aliases",
        "/api/modes",
        "/api/timers",
        "/api/reminders",
    ],
)
def test_le_rotte_di_lettura_rispondono_dal_database(rotta, cliente_autenticato):
    """Criterio di accettazione della issue #12: dopo la migrazione tutto
    funziona come prima. Queste sono le sette rotte che leggono lo stato."""
    risposta = cliente_autenticato.get(rotta)

    assert risposta.status_code == 200
    assert isinstance(risposta.json(), list)


def test_creare_e_cancellare_un_fatto_dalle_rotte(cliente_autenticato):
    """E le scritture: una riga alla volta, senza riscrivere l'elenco."""
    quanti_prima = len(cliente_autenticato.get("/api/knowledge").json())

    creato = cliente_autenticato.post(
        "/api/knowledge", json={"text": "Il gatto mangia alle 19", "category": "casa"}
    )
    assert creato.status_code == 200
    identificativo = creato.json()["item"]["id"]
    assert identificativo  # generato, non dedotto dal conteggio

    assert len(cliente_autenticato.get("/api/knowledge").json()) == quanti_prima + 1

    assert cliente_autenticato.delete(f"/api/knowledge/{identificativo}").json()["success"] is True
    assert len(cliente_autenticato.get("/api/knowledge").json()) == quanti_prima


def test_gli_identificativi_non_si_ripetono_dopo_una_cancellazione(cliente_autenticato):
    """Le rotte generavano `k_{len(elenco)+1}`: cancellata una voce, il
    conteggio torna su un numero gia' usato e il salvataggio successivo
    sovrascrive un altro record invece di crearne uno. In silenzio."""
    primo = cliente_autenticato.post("/api/knowledge", json={"text": "primo fatto"}).json()["item"]["id"]
    cliente_autenticato.delete(f"/api/knowledge/{primo}")
    secondo = cliente_autenticato.post("/api/knowledge", json={"text": "secondo fatto"}).json()["item"]["id"]

    assert secondo != primo
    testi = {f["text"] for f in cliente_autenticato.get("/api/knowledge").json()}
    assert "secondo fatto" in testi
