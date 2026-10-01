"""Il ciclo dell'agente si racconta, evento per evento (issue #188).

Tre cose da provare: la **sequenza** (un agente vero con un modello finto), la
**riservatezza** (un secondo profilo non vede cosa chiede il primo, e nessun
contenuto viaggia) e la **robustezza** (se il canale e' giu', la risposta
arriva lo stesso).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from shinra.api import sicurezza
from shinra.api.app import app
from shinra.config.settings import settings
from shinra.domain import eventi_agente as ea
from shinra.domain.eventi import bus
from shinra.infra.db import depositi
from shinra.services import agent as modulo_agente
from shinra.services.agent import ShinraAgent
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile, user_manager

FRASE = "alza la tapparella del salotto, la mia password segreta è tartaruga"
RISPOSTA = "Fatto, tapparella alzata."


@pytest.fixture
def raccolta():
    """Tutti gli eventi dell'agente pubblicati sul bus durante la prova."""
    visti: list = []
    annulla = [bus.sottoscrivi(t, visti.append) for t in ea.TIPI]
    yield visti
    for a in annulla:
        a()


@pytest.fixture
def agente(monkeypatch):
    """L'agente vero, con modello e strumenti finti."""
    a = ShinraAgent()
    risposte = [
        {
            "success": True,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "comanda_tapparella",
                            "arguments": {"entity_id": "cover.salotto", "azione": "alza"},
                        }
                    }
                ],
            },
        },
        {"success": True, "message": {"role": "assistant", "content": RISPOSTA}},
    ]

    async def chat(messages, tools=None, **_):
        return risposte.pop(0)

    async def execute_tool(nome, argomenti):
        return {"success": True}

    monkeypatch.setattr(a.ollama, "chat", chat)
    monkeypatch.setattr(modulo_agente, "execute_tool", execute_tool)
    return a


async def _lascia_consegnare() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


def _profilo(nome: str) -> UserProfile:
    return UserProfile(id=nome.lower(), name=nome)


async def _chiedi(agente: ShinraAgent) -> dict:
    return await agente.process_user_input(
        FRASE, user_profile=_profilo("Alessio"), session_memory=ConversationMemory()
    )


async def test_una_richiesta_vera_racconta_la_sequenza(agente, raccolta):
    esito = await _chiedi(agente)
    await _lascia_consegnare()

    assert esito["response"] == RISPOSTA
    assert [e.tipo for e in raccolta] == [
        ea.RICHIESTA_RICEVUTA,
        ea.RICHIESTA_RICEVUTA,  # la seconda: passata al modello, da qui parte il percorso
        ea.SKILL_SCELTA,
        ea.DISPOSITIVO_COMANDATO,
        ea.RISPOSTA_DATA,
    ]
    assert raccolta[1].dati["nodi"] == [ea.NODO_MODELLO] and raccolta[1].dati["al_modello"] is True
    skill, dispositivo = raccolta[2], raccolta[3]
    assert skill.dati["nodi"] == ["strumento:comanda_tapparella"]
    assert dispositivo.dati["nodi"] == ["dispositivo:cover.salotto"]
    assert dispositivo.dati["riuscito"] is True
    assert raccolta[4].dati["nodi"] == [ea.NODO_MODELLO]
    # Una sola richiesta, un solo identificativo, e il proprietario e' chi ha chiesto.
    assert len({e.dati["richiesta"] for e in raccolta}) == 1
    assert {e.dati["profilo"] for e in raccolta} == {"alessio"}


async def test_il_contenuto_della_richiesta_non_viaggia(agente, raccolta):
    await _chiedi(agente)
    await _lascia_consegnare()

    tutto = json.dumps([e.come_json() for e in raccolta], ensure_ascii=False)
    for segreto in ("tartaruga", "password", "tapparella del salotto", "alza", "Fatto"):
        assert segreto not in tutto
    # I nodi sono identificativi, e basta.
    for e in raccolta:
        assert all(":" in n for n in e.dati["nodi"])


async def test_un_errore_del_modello_e_un_evento_senza_il_messaggio(agente, raccolta, monkeypatch):
    async def guasto(messages, tools=None, **_):
        return {"success": False, "error": f"non riesco a leggere: {FRASE}"}

    monkeypatch.setattr(agente.ollama, "chat", guasto)
    esito = await _chiedi(agente)
    await _lascia_consegnare()

    assert esito["success"] is False
    errore = [e for e in raccolta if e.tipo == ea.ERRORE]
    assert len(errore) == 1 and errore[0].dati["motivo"] == ea.MOTIVO_MODELLO
    assert "tartaruga" not in json.dumps(errore[0].come_json())


async def test_se_il_canale_e_giu_la_risposta_arriva_lo_stesso(agente, monkeypatch):
    async def bus_rotto(evento):
        raise RuntimeError("il bus è giù")

    monkeypatch.setattr(bus, "pubblica", bus_rotto)
    esito = await _chiedi(agente)
    await _lascia_consegnare()
    assert esito["response"] == RISPOSTA


async def test_un_ascoltatore_che_solleva_non_ferma_la_risposta(agente):
    def guasto(evento):
        raise RuntimeError("ascoltatore rotto")

    annulla = [bus.sottoscrivi(t, guasto) for t in ea.TIPI]
    try:
        esito = await _chiedi(agente)
        await _lascia_consegnare()
    finally:
        for a in annulla:
            a()
    assert esito["response"] == RISPOSTA


async def test_emettere_non_attende_gli_ascoltatori(agente):
    """Un ascoltatore lentissimo non ritarda la risposta."""
    sbloccato = asyncio.Event()

    async def lento(evento):
        await sbloccato.wait()

    annulla = [bus.sottoscrivi(t, lento) for t in ea.TIPI]
    try:
        esito = await asyncio.wait_for(_chiedi(agente), timeout=2)
    finally:
        sbloccato.set()
        await _lascia_consegnare()
        for a in annulla:
            a()
    assert esito["response"] == RISPOSTA


# ------------------------------------------------------------------ dominio


def test_un_evento_accetta_solo_valori_innocui():
    with pytest.raises(ValueError):
        ea.evento(ea.ERRORE, profilo="a", richiesta="r", motivo="non riesco a leggere la frase")
    with pytest.raises(ValueError):
        ea.evento(ea.SKILL_SCELTA, profilo="a", richiesta="r", testo="accendi la luce")
    with pytest.raises(ValueError):
        ea.evento("agente.inventato", profilo="a", richiesta="r")


def test_il_proprietario_non_arriva_al_browser():
    e = ea.evento(ea.SKILL_SCELTA, profilo="alessio", richiesta="r1", nodi=["strumento:x"])
    fuori = ea.per_il_browser(e)
    assert "profilo" not in fuori["dati"] and fuori["dati"]["nodi"] == ["strumento:x"]


def test_chi_riceve_cosa():
    e = ea.evento(ea.SKILL_SCELTA, profilo="alessio", richiesta="r1")
    assert ea.per_il_profilo(e, "alessio")
    assert not ea.per_il_profilo(e, "sam")
    assert ea.per_il_profilo(e, None)  # senza autenticazione la casa e' di tutti
    orfano = ea.evento(ea.SKILL_SCELTA, profilo=None, richiesta="r2")
    assert not ea.per_il_profilo(orfano, "sam")


# ------------------------------------------------------------ il canale vero


@pytest.fixture
def casa_chiusa():
    era_attiva = settings.security.auth_enabled
    amministratore = user_manager.get_users()[0]
    pin_originale = amministratore.pin
    settings.security.auth_enabled = True
    user_manager.imposta_pin(amministratore.id, "4729")
    sicurezza.azzera_stato()
    yield amministratore
    settings.security.auth_enabled = era_attiva
    utenti = user_manager.get_users()
    for u in utenti:
        if u.id == amministratore.id:
            u.pin = pin_originale
    depositi.utenti.sostituisci_tutto([u.model_dump() for u in utenti])
    sicurezza.azzera_stato()


def test_il_secondo_profilo_non_riceve_gli_eventi_del_primo(casa_chiusa):
    mio = casa_chiusa.id
    di_un_altro = ea.evento(
        ea.SKILL_SCELTA, profilo="un-familiare", richiesta="r1", nodi=["strumento:segreto"]
    )
    mio_evento = ea.evento(ea.SKILL_SCELTA, profilo=mio, richiesta="r2", nodi=["strumento:mio"])

    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"pin": "4729", "user_id": mio}).status_code == 200
        with c.websocket_connect("/ws/eventi") as ws:
            # Prima quello dell'altro, poi il mio: senza il filtro il primo
            # messaggio ricevuto sarebbe il suo.
            c.portal.call(bus.pubblica, di_un_altro)
            c.portal.call(bus.pubblica, mio_evento)
            ricevuto = ws.receive_json()

    assert ricevuto["dati"]["nodi"] == ["strumento:mio"]
    assert "profilo" not in ricevuto["dati"]


async def test_uno_strumento_fallito_e_un_errore_sul_suo_nodo(agente, raccolta, monkeypatch):
    """Il grafo vivo (#189) mostra in rosso lo strumento e il dispositivo che non hanno funzionato."""

    async def fallisce(nome, argomenti):
        return {"success": False, "error": "non risponde"}

    monkeypatch.setattr(modulo_agente, "execute_tool", fallisce)
    await _chiedi(agente)
    await _lascia_consegnare()

    errori = [e for e in raccolta if e.tipo == ea.ERRORE]
    assert len(errori) == 1
    assert errori[0].dati["nodi"] == ["strumento:comanda_tapparella", "dispositivo:cover.salotto"]
    assert errori[0].dati["motivo"] == ea.MOTIVO_STRUMENTO
    assert "non risponde" not in json.dumps(errori[0].come_json())


async def test_il_modello_e_un_nodo_del_grafo_e_usa_gli_strumenti():
    """Gli eventi lo nominano (`agente:modello`): deve esistere, altrimenti non si accende niente."""
    from shinra.services import cervello

    cervello.dimentica_il_modello()
    grafo = await cervello.genera()
    nodi = {n["id"]: n for n in grafo["nodi"]}
    assert ea.NODO_MODELLO in nodi and nodi[ea.NODO_MODELLO]["tipo"] == "agente"
    assert any(c["da"] == ea.NODO_MODELLO and c["tipo"] == "usa" for c in grafo["collegamenti"])
