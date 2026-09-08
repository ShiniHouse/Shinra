"""Chi ha fatto cosa in casa, e com'e' andata.

Shinra comanda luci, prese e clima — e presto serrature e allarme — e fino
alla v0.2.0 non restava traccia di niente: alla domanda «chi ha spento il
riscaldamento alle tre di notte?» non c'era risposta. Riferimento: issue #15.

Il test piu' importante di questo file non e' quello che verifica che una
voce venga scritta: e' `test_i_segreti_non_finiscono_mai_nel_registro`. Un
registro che copia dentro di se' il token di Home Assistant e' peggio del
non averlo, perche' raddoppia i posti da cui quel token puo' uscire.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from shinra.infra.db.modelli import VoceRegistro
from shinra.infra.db.motore import sessione
from shinra.services import registro


@pytest.fixture(autouse=True)
def contesto_pulito():
    registro.apri_contesto(attore="alessio", canale="web")
    yield


def _voci() -> list[dict]:
    return registro.voci(limite=100)


# ------------------------------------------------------------- i segreti


@pytest.mark.parametrize(
    "campo",
    ["token", "ha_token", "admin_pin", "pin", "password", "api_key", "Authorization", "session_secret"],
)
def test_i_segreti_non_finiscono_mai_nel_registro(campo):
    """Si guarda il nome del campo, non il contenuto: un token e' una stringa
    qualunque e riconoscerlo dal testo sarebbe un indovinello. Il nome invece
    lo sappiamo sempre."""
    oscurato = registro.oscura({campo: "valore-vero-e-segreto"})

    assert oscurato[campo] == registro.MASCHERA
    assert "valore-vero-e-segreto" not in json.dumps(oscurato)


def test_i_segreti_sono_oscurati_anche_in_fondo_a_una_struttura():
    dati = {"parametri": {"config": [{"home_assistant": {"token": "abc123"}}]}}

    assert "abc123" not in json.dumps(registro.oscura(dati))


def test_cio_che_non_e_segreto_resta_leggibile():
    """Oscurare tutto sarebbe facile e inutile: il registro deve dire quale
    luce e' stata accesa."""
    oscurato = registro.oscura({"entity_id": "light.cucina", "action": "turn_on"})

    assert oscurato == {"entity_id": "light.cucina", "action": "turn_on"}


async def test_un_tool_chiamato_con_un_segreto_non_lo_scrive(monkeypatch):
    from shinra.skills import registry

    async def finto(**argomenti):
        return {"success": True}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)
    await registry.execute_tool("control_device", {"entity_id": "light.cucina", "token": "SEGRETO"})

    assert "SEGRETO" not in json.dumps(_voci())


# --------------------------------------------------------- azioni di casa


async def test_ogni_azione_domotica_lascia_una_voce(monkeypatch):
    from shinra.skills import registry

    async def finto(**argomenti):
        return {"success": True}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)
    await registry.execute_tool("control_device", {"entity_id": "light.cucina", "action": "turn_on"})

    voce = _voci()[0]
    assert voce["azione"] == "tool.control_device"
    assert voce["esito"] == registro.ESITO_OK
    assert voce["dettagli"]["parametri"]["entity_id"] == "light.cucina"
    assert voce["attore"] == "alessio"
    assert voce["canale"] == "web"
    assert voce["durata_ms"] is not None


async def test_un_comando_fallito_non_risulta_riuscito(monkeypatch):
    """I tool segnalano i guasti restituendoli, non sollevandoli. Senza
    controllarlo, un comando fallito comparirebbe nel registro come riuscito:
    il modo peggiore di avere un registro."""
    from shinra.skills import registry

    async def finto(**argomenti):
        return {"success": False, "error": "Home Assistant irraggiungibile"}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)
    await registry.execute_tool("control_device", {"entity_id": "light.cucina"})

    voce = _voci()[0]
    assert voce["esito"] == registro.ESITO_ERRORE
    assert "irraggiungibile" in voce["dettagli"]["errore"]


async def test_un_tool_che_solleva_e_registrato_e_non_propaga(monkeypatch):
    from shinra.skills import registry

    async def finto(**argomenti):
        raise RuntimeError("connessione persa")

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)
    esito = await registry.execute_tool("control_device", {"entity_id": "light.cucina"})

    assert esito["success"] is False
    assert _voci()[0]["esito"] == registro.ESITO_ERRORE


async def test_un_tool_inesistente_lascia_traccia():
    """Un modello che inventa un tool e' un'informazione utile, non rumore."""
    await __import__("shinra.skills.registry", fromlist=["x"]).execute_tool("tool_inventato", {})

    assert _voci()[0]["azione"] == "tool.tool_inventato"
    assert _voci()[0]["esito"] == registro.ESITO_ERRORE


# ------------------------------------------------------------ correlazione


async def test_le_azioni_di_uno_stesso_turno_hanno_lo_stesso_filo(monkeypatch):
    """«Accendi le luci di sotto» puo' produrre tre comandi: senza un filo
    comune sembrano tre eventi scollegati avvenuti nello stesso secondo."""
    from shinra.skills import registry

    async def finto(**argomenti):
        return {"success": True}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)
    for entita in ("light.salotto", "light.cucina", "light.ingresso"):
        await registry.execute_tool("control_device", {"entity_id": entita})

    correlazioni = {v["correlazione"] for v in _voci()}
    assert len(correlazioni) == 1


async def test_due_richieste_diverse_hanno_fili_diversi(monkeypatch):
    from shinra.skills import registry

    async def finto(**argomenti):
        return {"success": True}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto)

    registro.apri_contesto(attore="alessio", canale="web")
    await registry.execute_tool("control_device", {"entity_id": "light.cucina"})
    registro.apri_contesto(attore="sonia", canale="alexa")
    await registry.execute_tool("control_device", {"entity_id": "light.salotto"})

    voci = _voci()
    assert voci[0]["correlazione"] != voci[1]["correlazione"]
    assert {v["attore"] for v in voci} == {"alessio", "sonia"}
    assert {v["canale"] for v in voci} == {"web", "alexa"}


# ---------------------------------------------------------------- pulizia


def test_la_pulizia_toglie_solo_le_voci_vecchie():
    registro.registra("azione.recente")
    with sessione() as s:
        s.add(
            VoceRegistro(
                momento=datetime.now(timezone.utc) - timedelta(days=200),
                azione="azione.antica",
                esito=registro.ESITO_OK,
            )
        )

    rimosse = registro.pulisci(giorni=90)

    azioni = {v["azione"] for v in _voci()}
    assert rimosse == 1
    assert azioni == {"azione.recente"}


def test_conservare_tutto_significa_non_cancellare_niente():
    registro.registra("azione.qualunque")
    with sessione() as s:
        s.add(
            VoceRegistro(
                momento=datetime.now(timezone.utc) - timedelta(days=3650),
                azione="azione.di-dieci-anni-fa",
                esito=registro.ESITO_OK,
            )
        )

    assert registro.pulisci(giorni=0) == 0
    assert len(_voci()) == 2


# -------------------------------------------------------------- robustezza


def test_un_guasto_del_registro_non_ferma_la_casa(monkeypatch):
    """Se la scrittura fallisce si va avanti: un difetto nel registro non
    deve impedire di spegnere una luce."""

    def rotto():
        raise RuntimeError("disco pieno")

    monkeypatch.setattr("shinra.infra.db.motore.sessione", rotto)

    registro.registra("azione.qualunque")  # non deve sollevare


# ------------------------------------------------------------ log in JSON


def test_il_log_strutturato_porta_con_se_la_correlazione():
    import logging

    ctx = registro.apri_contesto(attore="alessio", canale="alexa")
    record = logging.LogRecord("Shinra.Prova", logging.INFO, __file__, 1, "acceso il salotto", None, None)

    riga = json.loads(registro.FormatoJson().format(record))

    assert riga["correlazione"] == ctx.correlazione
    assert riga["attore"] == "alessio"
    assert riga["canale"] == "alexa"
    assert riga["messaggio"] == "acceso il salotto"


# ------------------------------------------------------ chi puo' consultarlo


def test_l_amministratore_legge_il_registro(cliente_autenticato):
    registro.registra("tool.control_device", dettagli={"parametri": {"entity_id": "light.cucina"}})

    risposta = cliente_autenticato.get("/api/registro")

    assert risposta.status_code == 200
    assert any(v["azione"] == "tool.control_device" for v in risposta.json())


def test_un_familiare_non_amministratore_non_lo_legge():
    """Non e' formalita': queste righe dicono a che ora qualcuno rientra,
    quando accende le luci, quando esce. Sono i movimenti della famiglia."""
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.infra.db import depositi
    from shinra.services.user_manager import user_manager

    with TestClient(app) as client:
        depositi.utenti.salva({"id": "sonia", "name": "Sonia", "role": "adult"})
        user_manager.imposta_pin("sonia", "112233")
        sicurezza.azzera_stato()

        entrata = client.post("/api/auth/login", json={"pin": "112233", "user_id": "sonia"})
        assert entrata.status_code == 200

        assert client.get("/api/registro").status_code == 403
        assert client.get("/api/registro/azioni").status_code == 403


def test_senza_sessione_il_registro_non_si_apre(cliente_autenticato):
    cliente_autenticato.post("/api/auth/logout")

    assert cliente_autenticato.get("/api/registro").status_code == 401


def test_un_accesso_rifiutato_finisce_nel_registro_senza_il_pin_provato():
    """Un registro che raccoglie i PIN sbagliati e' un elenco di quasi-PIN
    giusti: la cosa piu' pericolosa che si possa scrivere su un disco."""
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.services.user_manager import user_manager

    with TestClient(app) as client:
        utente = user_manager.get_users()[0]
        user_manager.imposta_pin(utente.id, "482913")
        sicurezza.azzera_stato()

        client.post("/api/auth/login", json={"pin": "482911", "user_id": utente.id})

    voci = registro.voci(limite=50)
    rifiuti = [v for v in voci if v["azione"] == "accesso.rifiutato"]
    assert rifiuti, "un accesso rifiutato deve lasciare traccia"
    assert "482911" not in json.dumps(voci)
