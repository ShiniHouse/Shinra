"""Verifiche sullo scheduler persistente e sul bus eventi.

Il difetto che questi test presidiano e' quello che ha reso i promemoria
inutili per tutta la v0.1.0: erano scritti su disco e nessuno li rileggeva.
Percio' qui non si controlla che esistano dei metodi, ma che un promemoria
programmato prima di un riavvio sia ancora programmato dopo.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import pytest

from core import consegna
from core import scheduler as modulo_scheduler
from core import timer_engine as modulo_timer
from core.eventi import PROMEMORIA_SCADUTO, TIMER_SCADUTO, BusEventi, Evento, bus
from core.scheduler import (
    PREFISSO_PROMEMORIA,
    PREFISSO_TIMER,
    TOLLERANZA_PROMEMORIA,
    TOLLERANZA_TIMER,
    ServizioScheduler,
)


def _fra(secondi: float) -> float:
    return time.time() + secondi


def _iso_fra(secondi: float) -> str:
    return (datetime.now() + timedelta(seconds=secondi)).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    """Sposta l'archivio dei job e i file di stato in una cartella temporanea.

    Senza questo, eseguire i test sovrascriverebbe i timer veri di casa.
    """
    monkeypatch.setattr(modulo_scheduler, "DATA_DIR", tmp_path)
    monkeypatch.setattr(modulo_scheduler, "ARCHIVIO_JOB", tmp_path / "scheduler.db")
    monkeypatch.setattr(modulo_timer, "DATA_DIR", tmp_path)
    monkeypatch.setattr(modulo_timer, "TIMERS_FILE", tmp_path / "timers.json")
    monkeypatch.setattr(modulo_timer, "REMINDERS_FILE", tmp_path / "reminders.json")
    return tmp_path


@pytest.fixture
async def servizio(archivio):
    # AsyncIOScheduler.start() pretende un event loop gia' in esecuzione:
    # per questo la fixture e i test che la usano sono asincroni.
    s = ServizioScheduler()
    s.avvia()
    yield s
    s.ferma()


# --------------------------------------------------------------- bus eventi


async def test_il_bus_consegna_a_chi_ascolta():
    b = BusEventi()
    ricevuti = []
    b.sottoscrivi(TIMER_SCADUTO, lambda e: ricevuti.append(e))

    consegnati = await b.pubblica(Evento(tipo=TIMER_SCADUTO, dati={"etichetta": "pasta"}))

    assert consegnati == 1
    assert ricevuti[0].dati["etichetta"] == "pasta"


async def test_un_ascoltatore_che_fallisce_non_zittisce_gli_altri():
    """Se l'Echo e' irraggiungibile, la dashboard deve suonare lo stesso."""
    b = BusEventi()
    ricevuti = []

    def rotto(evento):
        raise RuntimeError("Echo irraggiungibile")

    async def sano(evento):
        ricevuti.append(evento)

    b.sottoscrivi(TIMER_SCADUTO, rotto)
    b.sottoscrivi(TIMER_SCADUTO, sano)

    consegnati = await b.pubblica(Evento(tipo=TIMER_SCADUTO))

    assert consegnati == 1  # solo quello sano
    assert len(ricevuti) == 1


async def test_disiscriversi_ferma_le_consegne():
    b = BusEventi()
    ricevuti = []
    annulla = b.sottoscrivi(PROMEMORIA_SCADUTO, lambda e: ricevuti.append(e))
    annulla()

    assert await b.pubblica(Evento(tipo=PROMEMORIA_SCADUTO)) == 0
    assert ricevuti == []


# ------------------------------------------------------------ programmazione


async def test_un_timer_programmato_compare_fra_i_job(servizio):
    assert servizio.programma_timer("timer_abc", "pasta", _fra(3600), "alessio") is True

    identificativi = [j["id"] for j in servizio.job_programmati()]
    assert f"{PREFISSO_TIMER}timer_abc" in identificativi


async def test_annullare_un_timer_ne_rimuove_il_job(servizio):
    servizio.programma_timer("timer_abc", "pasta", _fra(3600), "alessio")

    assert servizio.annulla_timer("timer_abc") is True
    assert servizio.job_programmati() == []


async def test_annullare_un_timer_inesistente_non_solleva(servizio):
    assert servizio.annulla_timer("timer_mai_esistito") is False


async def test_riprogrammare_lo_stesso_timer_non_lo_duplica(servizio):
    servizio.programma_timer("timer_abc", "pasta", _fra(3600), "alessio")
    servizio.programma_timer("timer_abc", "pasta", _fra(7200), "alessio")

    assert len(servizio.job_programmati()) == 1


async def test_un_promemoria_con_orario_illeggibile_non_viene_programmato(servizio):
    assert servizio.programma_promemoria("rem_1", "medicine", "domani pomeriggio", "alessio") is False
    assert servizio.job_programmati() == []


def test_a_scheduler_spento_la_programmazione_fallisce_senza_esplodere(archivio):
    s = ServizioScheduler()
    assert s.attivo is False
    assert s.programma_timer("timer_abc", "pasta", _fra(3600), "alessio") is False
    assert s.job_programmati() == []


# --------------------------------------------------------------- tolleranza


async def test_un_timer_scaduto_da_troppo_non_viene_recuperato(servizio):
    """La pasta e' andata comunque: non ha senso suonare mezz'ora dopo."""
    assert servizio.programma_timer("timer_vecchio", "pasta", _fra(-TOLLERANZA_TIMER - 60), "x") is False


async def test_un_promemoria_scaduto_da_poco_viene_ancora_consegnato(servizio):
    """«Prendi le medicine» resta utile anche con dieci minuti di ritardo."""
    quando = _iso_fra(-600)
    assert -TOLLERANZA_PROMEMORIA < -600  # dentro la tolleranza, per costruzione
    assert servizio.programma_promemoria("rem_recuperabile", "medicine", quando, "x") is True


def test_le_due_tolleranze_sono_diverse_e_ordinate():
    """Se qualcuno le pareggiasse, la distinzione sopra sparirebbe in silenzio."""
    assert TOLLERANZA_TIMER < TOLLERANZA_PROMEMORIA


# --------------------------------------------------------------- persistenza


async def test_un_job_sopravvive_al_riavvio_del_servizio(archivio):
    """Il requisito della issue: un promemoria per le 17:30 scatta anche se
    il servizio e' stato riavviato alle 17:00."""
    primo = ServizioScheduler()
    primo.avvia()
    primo.programma_promemoria("rem_1", "medicine", _iso_fra(3600), "alessio")
    assert len(primo.job_programmati()) == 1
    primo.ferma()

    secondo = ServizioScheduler()
    secondo.avvia()
    try:
        identificativi = [j["id"] for j in secondo.job_programmati()]
        assert f"{PREFISSO_PROMEMORIA}rem_1" in identificativi
    finally:
        secondo.ferma()


async def test_l_archivio_dei_job_e_un_file_su_disco(servizio, archivio):
    servizio.programma_timer("timer_abc", "pasta", _fra(3600), "alessio")
    assert (archivio / "scheduler.db").exists()


# ------------------------------------------------------- scadenza ed eventi


async def test_alla_scadenza_il_timer_viene_marcato_e_l_evento_pubblicato(archivio):
    modulo_timer.timer_engine.save_timers(
        [{"id": "timer_abc", "label": "pasta", "expires_at": _fra(-1), "completed": False}]
    )
    ricevuti = []
    annulla = bus.sottoscrivi(TIMER_SCADUTO, lambda e: ricevuti.append(e))
    try:
        await modulo_scheduler._scade_timer("timer_abc", "pasta", "alessio")
    finally:
        annulla()

    assert modulo_timer.timer_engine.get_timers()[0]["completed"] is True
    assert ricevuti and ricevuti[0].dati["etichetta"] == "pasta"


async def test_alla_scadenza_il_promemoria_viene_marcato_e_l_evento_pubblicato(archivio):
    modulo_timer.timer_engine.save_reminders(
        [{"id": "rem_1", "text": "medicine", "remind_at": _iso_fra(-1), "completed": False}]
    )
    ricevuti = []
    annulla = bus.sottoscrivi(PROMEMORIA_SCADUTO, lambda e: ricevuti.append(e))
    try:
        await modulo_scheduler._scade_promemoria("rem_1", "medicine", "alessio")
    finally:
        annulla()

    assert modulo_timer.timer_engine.get_reminders()[0]["completed"] is True
    assert ricevuti and ricevuti[0].dati["testo"] == "medicine"


# ------------------------------------------------------ ripristino all'avvio


async def test_ripristina_job_riprogramma_solo_cio_che_e_ancora_in_attesa(archivio):
    """Chi aggiorna da una versione senza scheduler ha timer in attesa e
    nessun job: all'avvio vanno ricreati, ma non quelli gia' completati."""
    modulo_scheduler.scheduler.avvia()
    try:
        modulo_timer.timer_engine.save_timers(
            [
                {"id": "t_attivo", "label": "pasta", "expires_at": _fra(3600), "completed": False},
                {"id": "t_finito", "label": "forno", "expires_at": _fra(-99999), "completed": True},
            ]
        )
        modulo_timer.timer_engine.save_reminders(
            [
                {"id": "r_attivo", "text": "medicine", "remind_at": _iso_fra(3600), "completed": False},
                {"id": "r_finito", "text": "spesa", "remind_at": _iso_fra(-99999), "completed": True},
            ]
        )

        contati = modulo_timer.timer_engine.ripristina_job()

        assert contati == {"timer": 1, "promemoria": 1}
        identificativi = {j["id"] for j in modulo_scheduler.scheduler.job_programmati()}
        assert identificativi == {f"{PREFISSO_TIMER}t_attivo", f"{PREFISSO_PROMEMORIA}r_attivo"}
    finally:
        modulo_scheduler.scheduler.ferma()


def test_pulisci_scaduti_toglie_solo_i_completati_vecchi(archivio):
    modulo_timer.timer_engine.save_timers(
        [
            {"id": "vecchio", "expires_at": time.time() - 48 * 3600, "completed": True},
            {"id": "recente", "expires_at": time.time() - 60, "completed": True},
            {"id": "attivo", "expires_at": _fra(3600), "completed": False},
        ]
    )

    rimossi = modulo_timer.timer_engine.pulisci_scaduti(conserva_ore=24)

    rimasti = {t["id"] for t in modulo_timer.timer_engine.get_timers()}
    assert rimossi == 1
    assert rimasti == {"recente", "attivo"}


# ----------------------------------------------------------------- consegna


def test_la_frase_del_timer_nomina_l_etichetta():
    frase = consegna._frase(Evento(tipo=TIMER_SCADUTO, dati={"etichetta": "pasta"}))
    assert "pasta" in frase


def test_la_frase_del_timer_senza_etichetta_non_dice_timer_per_timer():
    frase = consegna._frase(Evento(tipo=TIMER_SCADUTO, dati={"etichetta": "Timer"}))
    assert frase.lower().count("timer") == 1


def test_la_frase_del_promemoria_riporta_il_testo():
    frase = consegna._frase(Evento(tipo=PROMEMORIA_SCADUTO, dati={"testo": "prendere le medicine"}))
    assert "prendere le medicine" in frase


def test_un_evento_sconosciuto_non_produce_frase():
    assert consegna._frase(Evento(tipo="qualcosa.di.ignoto")) == ""


async def test_senza_echo_configurato_l_annuncio_non_tenta_home_assistant(monkeypatch):
    """Nessun Echo in casa non e' un errore: si tace, senza chiamate di rete."""
    monkeypatch.setattr(consegna.settings.home_assistant, "alexa_media_player_entity", "", raising=False)

    chiamate = []

    def non_chiamare():
        chiamate.append(True)
        raise AssertionError("non doveva contattare Home Assistant")

    monkeypatch.setattr("core.ha_client.client_home_assistant", non_chiamare, raising=False)

    await consegna.annuncia_su_echo(Evento(tipo=TIMER_SCADUTO, dati={"etichetta": "pasta"}))
    assert chiamate == []


def test_descrivi_include_la_frase_pronunciata():
    descritto = consegna.descrivi(Evento(tipo=TIMER_SCADUTO, dati={"etichetta": "pasta"}))
    assert set(descritto) >= {"tipo", "dati", "momento", "frase"}
    assert "pasta" in descritto["frase"]


# --------------------------------------------------- la catena intera, viva


def test_un_timer_creato_dall_api_arriva_sul_websocket(archivio, monkeypatch):
    """La prova che chiude la issue.

    Non verifica un pezzo: crea un timer come lo crea la dashboard, aspetta
    che scada davvero e controlla che l'avviso esca dal WebSocket con la
    frase da pronunciare. E' il percorso che per tutta la v0.1.0 non
    esisteva — il timer viveva in un `setInterval` del browser.
    """
    from fastapi.testclient import TestClient

    from config.settings import settings

    monkeypatch.setattr(settings.security, "auth_enabled", False, raising=False)

    from server.app import app

    with TestClient(app) as client, client.websocket_connect("/ws/eventi") as ws:
        creato = client.post(
            "/api/timers",
            json={"label": "pasta", "duration_seconds": 1, "user_id": "alessio"},
        )
        assert creato.status_code == 200

        evento = ws.receive_json()

    assert evento["tipo"] == TIMER_SCADUTO
    assert evento["dati"]["etichetta"] == "pasta"
    assert "pasta" in evento["frase"]
    assert modulo_timer.timer_engine.get_timers()[0]["completed"] is True
