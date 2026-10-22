"""«Ci penso» (#431, seconda parte): una richiesta lenta della dashboard diventa un lavoro e l'esito arriva dopo, solo a chi lo aveva chiesto.

Si prova con un agente finto (nessun modello): la richiesta veloce risponde subito come sempre; quella lenta risponde «ci sto lavorando», va avanti
senza essere rifatta, consegna l'esito in chat (evento) e un avviso **senza contenuto**; annullare ferma la richiesta; chi non dichiara di poter
aspettare (Alexa, un satellite) aspetta come sempre.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from shinra.api import sicurezza
from shinra.api.app import app
from shinra.config.settings import settings
from shinra.domain import eventi_agente
from shinra.domain import lavori as dominio
from shinra.infra.db import depositi
from shinra.infra.db.lavori import lavori as deposito
from shinra.services import permessi
from shinra.services.agent import agent
from shinra.services.lavori import ServizioLavori, TroppiLavori
from shinra.services.notifiche import servizio_notifiche
from shinra.services.user_manager import UserProfile, user_manager

PIN_DI_PROVA = "482913"
SEGNO = "ZEBRA-VERDE-5521"


@pytest.fixture()
def servizio(monkeypatch):
    monkeypatch.setattr(dominio, "TETTO_MINIMO_SECONDI", 0)
    monkeypatch.setattr(settings.lavori, "tetto_secondi", 5)
    for profilo in ("alessio", "sonia"):
        deposito.dimentica_profilo(profilo)
    yield ServizioLavori()
    for profilo in ("alessio", "sonia"):
        deposito.dimentica_profilo(profilo)


def richiesta_che_dura(secondi, risposta="fatto", flag=None):
    async def avvia():
        try:
            await asyncio.sleep(secondi)
        except asyncio.CancelledError:
            if flag is not None:
                flag.set()
            raise
        return {"response": risposta, "actions": []}

    return avvia


# ------------------------------------------------------------------ il servizio


async def test_una_richiesta_veloce_risponde_subito_come_sempre(servizio):
    risposta, lavoro = await servizio.con_attesa_massima(
        "alessio", "ciao", richiesta_che_dura(0.01, "ciao!"), soglia=1
    )
    assert risposta == {"response": "ciao!", "actions": []} and lavoro is None
    assert servizio.elenco("alessio") == [], "una richiesta veloce non diventa un lavoro"


async def test_una_richiesta_lenta_diventa_un_lavoro_che_continua_senza_essere_rifatta(servizio):
    chiamate = []

    async def avvia():
        chiamate.append(1)
        await asyncio.sleep(0.3)
        return {"response": "ecco la risposta lunga", "actions": []}

    risposta, lavoro = await servizio.con_attesa_massima("alessio", "pensaci", avvia, soglia=0.05)
    assert risposta is None and lavoro["stato"] in (dominio.IN_CODA, dominio.IN_CORSO)
    for _ in range(100):
        finito = servizio.trova("alessio", lavoro["id"])
        if dominio.e_terminale(finito["stato"]):
            break
        await asyncio.sleep(0.02)
    assert finito["stato"] == dominio.FATTO and finito["esito"] == "ecco la risposta lunga"
    assert chiamate == [1], "la richiesta non si rifa: continua quella partita"


async def test_annullare_il_lavoro_ferma_anche_la_richiesta(servizio):
    fermata = asyncio.Event()
    _, lavoro = await servizio.con_attesa_massima(
        "alessio", "lunga", richiesta_che_dura(60, flag=fermata), soglia=0.05
    )
    await asyncio.sleep(0.1)
    assert (await servizio.annulla("alessio", lavoro["id"]))["stato"] == dominio.ANNULLATO
    await asyncio.wait_for(fermata.wait(), 2)


async def test_con_la_soglia_a_zero_si_aspetta_come_prima(servizio):
    risposta, lavoro = await servizio.con_attesa_massima(
        "alessio", "x", richiesta_che_dura(0.1, "dopo"), soglia=0
    )
    assert risposta["response"] == "dopo" and lavoro is None


async def test_se_non_c_e_posto_per_un_altro_lavoro_si_aspetta_invece_di_fallire(servizio, monkeypatch):
    def pieno(*a, **k):
        raise TroppiLavori("troppi")

    monkeypatch.setattr(servizio, "prendi_in_carico", pieno)
    risposta, lavoro = await servizio.con_attesa_massima(
        "alessio", "x", richiesta_che_dura(0.2, "alla fine"), soglia=0.05
    )
    assert risposta["response"] == "alla fine" and lavoro is None, "meglio una risposta lenta che nessuna"


# ------------------------------------------------------------------ i testi e l'evento


def test_i_testi_sono_nella_lingua_della_persona_con_ripiego_italiano():
    assert "lavorando" in dominio.testo("ci_penso", "it")
    assert "working on it" in dominio.testo("ci_penso", "en")
    assert dominio.testo("ci_penso", "fr") == dominio.testo(
        "ci_penso", "it"
    ), "una lingua ignota ripiega sull'italiano"
    assert dominio.testo("ci_penso", "") == dominio.testo("ci_penso", "it")


def test_il_testo_della_fine_dice_l_esito_o_il_perche_mai_un_errore_tecnico():
    fatto = {"stato": dominio.FATTO, "esito": "Le luci sono accese."}
    assert dominio.testo_della_fine(fatto) == "Le luci sono accese."
    assert dominio.testo_della_fine({"stato": dominio.FATTO, "esito": "  "}) == dominio.testo(
        "fatto_senza_testo"
    )
    tetto = dominio.testo_della_fine({"stato": dominio.FALLITO, "motivo": dominio.MOTIVO_TETTO})
    assert "in tempo" in tetto
    assert (
        dominio.testo_della_fine({"stato": dominio.FALLITO, "motivo": "RuntimeError: " + SEGNO}).count(SEGNO)
        == 0
    )


def test_si_consegna_solo_cio_che_la_persona_non_sa_gia():
    assert dominio.da_consegnare(dominio.FATTO) and dominio.da_consegnare(dominio.FALLITO)
    assert not dominio.da_consegnare(dominio.ANNULLATO), "l'ha deciso lei"
    assert not dominio.da_consegnare(dominio.INTERROTTO), "al riavvio non c'e' nessuno ad ascoltare"


def test_l_evento_va_solo_al_profilo_di_chi_ha_chiesto():
    evento = dominio.evento_finito(
        {"proprietario": "sonia", "id": "l_1", "stato": dominio.FATTO, "esito": f"codice {SEGNO}"}, "it"
    )
    assert eventi_agente.per_il_profilo(evento, "sonia") and not eventi_agente.per_il_profilo(
        evento, "alessio"
    )
    per_il_browser = eventi_agente.per_il_browser(evento)
    assert "profilo" not in per_il_browser["dati"], "il proprietario non viaggia verso il browser"
    assert SEGNO in per_il_browser["dati"]["testo"], "ma l'esito si': e' la risposta che si aspettava"


# ------------------------------------------------------------------ la chat vera


@pytest.fixture()
def dashboard(monkeypatch):
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    esistenti = user_manager.get_users()
    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    depositi.utenti.sostituisci_tutto(
        [
            UserProfile(id="alessio", name="Alessio", role="admin").model_dump(),
            UserProfile(id="sonia", name="Sonia", role="adult").model_dump(),
        ]
    )
    for chi in ("alessio", "sonia"):
        user_manager.imposta_pin(chi, PIN_DI_PROVA)
    sicurezza.azzera_stato()
    monkeypatch.setattr(settings.lavori, "soglia_secondi", 0.1)
    monkeypatch.setattr(dominio, "TETTO_MINIMO_SECONDI", 0)
    with TestClient(app) as cliente:
        assert (
            cliente.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": "sonia"}).status_code == 200
        )
        yield cliente
    depositi.utenti.sostituisci_tutto([u.model_dump() for u in esistenti])
    for profilo in ("alessio", "sonia"):
        deposito.dimentica_profilo(profilo)
    settings.security.auth_enabled = era_attiva
    sicurezza.azzera_stato()


def test_la_dashboard_riceve_ci_sto_lavorando_e_l_esito_arriva_dopo_con_un_avviso_senza_contenuto(
    dashboard, monkeypatch
):
    async def lenta(user_text, user_id=None, **k):
        await asyncio.sleep(0.5)
        return {"response": f"risposta lunga con {SEGNO}", "actions": []}

    avvisi = []

    async def cattura(avviso, utente=None):
        avvisi.append((avviso, utente))
        return {}

    monkeypatch.setattr(agent, "process_user_input", lenta)
    monkeypatch.setattr(servizio_notifiche, "avvisa", cattura)
    with dashboard.websocket_connect("/ws/eventi") as canale:
        risposta = dashboard.post(
            "/api/chat", json={"message": "pensaci", "user_id": "sonia", "puo_attendere": True}
        )
        assert risposta.status_code == 200
        corpo = risposta.json()
        assert "lavorando" in corpo["response"] and corpo["lavoro"]["id"], corpo
        # L'esito arriva dal canale degli eventi, in chat.
        evento = None
        for _ in range(20):
            messaggio = canale.receive_json()
            if messaggio.get("tipo") == "lavoro.finito":
                evento = messaggio
                break
        assert evento is not None, "l'evento lavoro.finito non e' arrivato"
        assert SEGNO in evento["dati"]["testo"] and evento["dati"]["stato"] == "fatto"
    # Il lavoro e' leggibile anche dalla rotta.
    lavoro = dashboard.get(f"/api/lavori/{corpo['lavoro']['id']}").json()
    assert lavoro["stato"] == "fatto" and SEGNO in lavoro["esito"]
    # L'avviso dice che e' pronto, mai che cosa.
    assert len(avvisi) == 1 and avvisi[0][1] == "sonia"
    assert (
        SEGNO not in avvisi[0][0].titolo + avvisi[0][0].testo
    ), "l'avviso viaggia verso piu' canali: niente contenuto"


def test_chi_non_dichiara_di_poter_aspettare_aspetta_come_sempre(dashboard, monkeypatch):
    async def lenta(user_text, user_id=None, **k):
        await asyncio.sleep(0.3)
        return {"response": "risposta intera", "actions": []}

    monkeypatch.setattr(agent, "process_user_input", lenta)
    corpo = dashboard.post("/api/chat", json={"message": "pensaci", "user_id": "sonia"}).json()
    assert corpo["response"] == "risposta intera" and "lavoro" not in corpo


def test_con_la_soglia_a_zero_la_funzione_e_spenta(dashboard, monkeypatch):
    async def lenta(user_text, user_id=None, **k):
        await asyncio.sleep(0.3)
        return {"response": "risposta intera", "actions": []}

    monkeypatch.setattr(agent, "process_user_input", lenta)
    monkeypatch.setattr(settings.lavori, "soglia_secondi", 0)
    corpo = dashboard.post(
        "/api/chat", json={"message": "x", "user_id": "sonia", "puo_attendere": True}
    ).json()
    assert corpo["response"] == "risposta intera" and "lavoro" not in corpo


def test_una_richiesta_veloce_non_diventa_un_lavoro(dashboard, monkeypatch):
    async def veloce(user_text, user_id=None, **k):
        return {"response": "ciao", "actions": []}

    monkeypatch.setattr(agent, "process_user_input", veloce)
    corpo = dashboard.post(
        "/api/chat", json={"message": "ciao", "user_id": "sonia", "puo_attendere": True}
    ).json()
    assert corpo["response"] == "ciao" and "lavoro" not in corpo
    assert dashboard.get("/api/lavori").json() == {"lavori": []}
