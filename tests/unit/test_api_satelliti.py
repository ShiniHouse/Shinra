"""Un punto di ascolto che dice dove si trova, e il comando che ne tiene conto.

Qui si prova la catena intera, che e' l'unica cosa che conta davvero: la
dashboard si annuncia come satellite di una stanza, manda una frase, e la
frase finisce sul dispositivo di **quella** stanza. Il dominio sa gia'
scegliere; questo file prova che quello che sa arrivi fino in fondo.

Il test piu' importante e'
`test_la_stessa_frase_da_due_satelliti_si_esegue_una_volta_sola`: e' il
criterio della scheda, e riguarda il caso — due dispositivi accesi insieme —
che in casa si scopre rotto solo quando fa male.

Riferimento: issue #33.
"""

from __future__ import annotations

import pytest

from shinra.domain import contesto as dominio_contesto
from shinra.infra.db import depositi
from shinra.services.satelliti import registro_satelliti


@pytest.fixture(autouse=True)
def casa_con_tre_luci():
    registro_satelliti.svuota()
    depositi.alias.sostituisci_tutto(
        [
            {"id": "a1", "alias": "luce cucina", "entity_id": "light.cucina", "room": "Cucina"},
            {"id": "a2", "alias": "luce salotto", "entity_id": "light.salotto", "room": "Salotto"},
            {"id": "a3", "alias": "luce bagno", "entity_id": "light.bagno", "room": "Bagno"},
        ]
    )
    yield
    registro_satelliti.svuota()
    depositi.alias.sostituisci_tutto([])


@pytest.fixture
def agente_finto(monkeypatch):
    """Cattura cosa arriva all'agente, senza chiamare nessun modello."""
    visti: list[dict] = []

    async def finto(user_text, user_id=None, **altro):
        visti.append(
            {
                "testo": user_text,
                "stanza": dominio_contesto.stanza_corrente(),
            }
        )
        return {"response": "fatto"}

    from shinra.api import app as modulo_app

    monkeypatch.setattr(modulo_app.agent, "process_user_input", finto)
    return visti


# ================================================== annunciarsi e sparire


def test_un_satellite_si_annuncia_con_la_sua_stanza(cliente_autenticato):
    risposta = cliente_autenticato.post(
        "/api/satelliti", json={"id": "telefono", "nome": "Telefono", "stanza": "Cucina"}
    )

    assert risposta.status_code == 200
    assert risposta.json()["stanza"] == "Cucina"


def test_un_satellite_senza_identificativo_non_si_annuncia(cliente_autenticato):
    risposta = cliente_autenticato.post("/api/satelliti", json={"id": "  ", "stanza": "Cucina"})

    assert risposta.status_code == 400


def test_l_elenco_dice_chi_ascolta_e_da_dove(cliente_autenticato):
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})
    cliente_autenticato.post("/api/satelliti", json={"id": "s2", "stanza": "Salotto"})

    satelliti = cliente_autenticato.get("/api/satelliti").json()["satelliti"]

    assert {s["stanza"] for s in satelliti} == {"Cucina", "Salotto"}


def test_riannunciarsi_cambia_stanza_invece_di_aggiungere(cliente_autenticato):
    """Il telefono che si sposta dalla cucina al salotto e' lo stesso
    telefono: due voci nell'elenco vorrebbero dire due punti di ascolto dove
    ce n'e' uno."""
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Salotto"})

    satelliti = cliente_autenticato.get("/api/satelliti").json()["satelliti"]

    assert len(satelliti) == 1
    assert satelliti[0]["stanza"] == "Salotto"


# ============================================ la stanza arriva al comando


def test_la_stanza_del_satellite_arriva_fino_all_agente(cliente_autenticato, agente_finto):
    """Se si ferma per strada, tutto il resto e' inutile: il dominio sa
    scegliere e nessuno gli dice da dove si parla."""
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})

    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s1"})

    assert agente_finto[0]["stanza"] == "Cucina"


def test_senza_satellite_non_si_dichiara_nessuna_stanza(cliente_autenticato, agente_finto):
    """La dashboard che non si e' dichiarata satellite deve continuare a
    funzionare come prima, senza ereditare la stanza di nessun altro."""
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})

    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce"})

    assert agente_finto[0]["stanza"] == ""


def test_un_satellite_sconosciuto_non_si_inventa_una_stanza(cliente_autenticato, agente_finto):
    """Attribuire un comando alla stanza sbagliata accende la luce di qualcun
    altro: peggio che non attribuirlo a nessuna."""
    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "mai_visto"})

    assert agente_finto[0]["stanza"] == ""


# ================================================ due orecchie, una bocca


def test_la_stessa_frase_da_due_satelliti_si_esegue_una_volta_sola(cliente_autenticato, agente_finto):
    """Il criterio della scheda.

    Due telefoni sullo stesso tavolo sentono la stessa cosa. Se rispondessero
    in due, la casa direbbe tutto due volte e accenderebbe la luce due volte
    — che per una luce non si nota e per una serranda si'.
    """
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})
    cliente_autenticato.post("/api/satelliti", json={"id": "s2", "stanza": "Cucina"})

    prima = cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s1"})
    seconda = cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s2"})

    assert prima.status_code == 200 and seconda.status_code == 200
    assert seconda.json()["gia_in_carico"] is True
    assert len(agente_finto) == 1, "la richiesta e' stata eseguita due volte"


def test_due_frasi_diverse_si_eseguono_tutte_e_due(cliente_autenticato, agente_finto):
    """Chi ha sentito un'altra cosa non deve essere zittito."""
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})
    cliente_autenticato.post("/api/satelliti", json={"id": "s2", "stanza": "Salotto"})

    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s1"})
    cliente_autenticato.post("/api/chat", json={"message": "che ore sono", "satellite": "s2"})

    assert len(agente_finto) == 2


@pytest.fixture
def casa_muta(monkeypatch):
    """Home Assistant sostituito: si guarda **quale servizio** chiediamo."""
    chiamate: list[tuple[str, str, dict]] = []

    class FintoClient:
        async def call_service(self, dominio, servizio, dati=None):
            chiamate.append((dominio, servizio, dati or {}))
            return {"success": True}

    from shinra.skills import ha_tools

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: FintoClient())
    return chiamate


@pytest.mark.asyncio
async def test_accendi_la_luce_dalla_cucina_accende_quella_della_cucina(casa_muta):
    """Il criterio principale della scheda, provato fino al servizio chiamato.

    La catena e' lunga — contesto della richiesta, risoluzione dell'alias,
    dominio delle stanze, tool — e ogni anello ha il suo test. Questo prova
    che sono attaccati: e' l'unica cosa che chi parla nota.
    """
    from shinra.skills import ha_tools

    dominio_contesto.apri_contesto(canale="web")
    dominio_contesto.dichiara_stanza("Cucina")

    await ha_tools.control_device("luce", "turn_on")

    assert casa_muta[0][2]["entity_id"] == "light.cucina"


@pytest.mark.asyncio
async def test_dal_salotto_la_stessa_frase_accende_un_altra_luce(casa_muta):
    """La prova che la stanza conta davvero, e non che «cucina» vinca sempre."""
    from shinra.skills import ha_tools

    dominio_contesto.apri_contesto(canale="web")
    dominio_contesto.dichiara_stanza("Salotto")

    await ha_tools.control_device("luce", "turn_on")

    assert casa_muta[0][2]["entity_id"] == "light.salotto"


@pytest.mark.asyncio
async def test_senza_stanza_accendi_la_luce_chiede_quale(casa_muta):
    """Prima ne accendeva una a caso, senza dire niente. Chiedere costa due
    secondi; indovinare costa la fiducia di chi ascolta."""
    from shinra.skills import ha_tools

    dominio_contesto.apri_contesto(canale="web")
    dominio_contesto.dichiara_stanza("")

    esito = await ha_tools.control_device("luce", "turn_on")

    assert esito["success"] is False
    assert "Quale?" in esito["message"]
    assert casa_muta == [], "ha acceso qualcosa invece di chiedere"


def test_lo_stesso_satellite_che_ripete_viene_eseguito_due_volte(cliente_autenticato, agente_finto):
    """Se qualcuno dice due volte «accendi la luce» allo stesso telefono, sono
    due richieste: scambiarle per un'eco perderebbe la seconda in silenzio."""
    cliente_autenticato.post("/api/satelliti", json={"id": "s1", "stanza": "Cucina"})

    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s1"})
    cliente_autenticato.post("/api/chat", json={"message": "accendi la luce", "satellite": "s1"})

    assert len(agente_finto) == 2
