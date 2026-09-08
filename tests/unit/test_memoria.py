"""Ogni persona ha la sua conversazione.

Fino alla v0.2.0 ce n'era una sola per tutta la casa: la chat del salotto,
quella del telefono e ogni richiesta ad Alexa scrivevano nella stessa
cronologia. Il contesto di un adulto finiva nella sessione di un bambino, e
due persone che parlavano insieme si confondevano a vicenda.

Il parametro `session_memory` esisteva gia' in `process_user_input`. Non lo
passava nessuno: il difetto era una riga mancante (REL-03, issue #13).
"""

from __future__ import annotations

import time

import pytest

from shinra.services.memory import ConversationMemory, GestoreMemorie, gestore_memorie


@pytest.fixture(autouse=True)
def memorie_pulite():
    gestore_memorie.azzera()
    yield
    gestore_memorie.azzera()


# ------------------------------------------------------- azioni nel contesto


def test_un_azione_eseguita_lascia_traccia_di_cosa_ha_toccato():
    """Il corpo di `add_tool_interaction` era `pass`. Conseguenza in casa:
    «accendi la luce della cucina» seguito da «spegnila» non poteva
    funzionare, perche' quale luce non era scritto da nessuna parte."""
    m = ConversationMemory()
    m.add_tool_interaction(
        "control_device", {"entity_id": "light.cucina", "action": "turn_on"}, {"success": True}
    )

    contenuto = m.get_messages()[-1]["content"]
    assert "light.cucina" in contenuto
    assert "control_device" in contenuto


def test_un_azione_fallita_e_registrata_come_tale():
    """Se il comando non e' andato a buon fine, l'assistente non deve
    raccontare all'utente che l'ha fatto."""
    m = ConversationMemory()
    m.add_tool_interaction(
        "control_device", {"entity_id": "light.cucina"}, {"error": "Home Assistant irraggiungibile"}
    )

    assert "non riuscita" in m.get_messages()[-1]["content"]


# ------------------------------------------------------------- separazione


def test_due_persone_hanno_conversazioni_diverse():
    alessio = gestore_memorie.per_utente("alessio")
    sonia = gestore_memorie.per_utente("sonia")

    alessio.add_user_message("dove ho messo le chiavi")

    assert sonia.get_messages() == []
    assert alessio is not sonia


def test_la_stessa_persona_ritrova_la_sua_conversazione():
    """E' il criterio della continuita' fra canali: si chiede all'Echo in
    cucina e si continua dal telefono in salotto."""
    dall_echo = gestore_memorie.per_utente("alessio")
    dall_echo.add_user_message("accendi la luce della cucina")

    dal_telefono = gestore_memorie.per_utente("alessio")

    assert dal_telefono is dall_echo
    assert dal_telefono.get_messages()[0]["content"] == "accendi la luce della cucina"


def test_il_nome_utente_non_e_sensibile_a_maiuscole_e_spazi():
    """Alexa e la dashboard non scrivono l'identificativo allo stesso modo."""
    assert gestore_memorie.per_utente("Alessio") is gestore_memorie.per_utente("  alessio ")


def test_chi_non_si_e_identificato_finisce_nella_conversazione_ospite():
    assert gestore_memorie.per_utente(None) is gestore_memorie.per_utente("")


# ---------------------------------------------------------------- pulizia


def test_una_conversazione_ferma_da_troppo_viene_liberata():
    g = GestoreMemorie()
    vecchia = g.per_utente("alessio")
    vecchia.ultimo_uso = time.time() - (31 * 60)

    assert g.pulisci() == 1
    assert g.attive() == {}


def test_una_conversazione_scaduta_riparte_pulita():
    g = GestoreMemorie()
    prima = g.per_utente("alessio")
    prima.add_user_message("un discorso di mezz'ora fa")
    prima.ultimo_uso = time.time() - (31 * 60)

    dopo = g.per_utente("alessio")

    assert dopo.get_messages() == []


def test_oltre_il_tetto_esce_la_conversazione_ferma_da_piu_tempo():
    """Gli ospiti non registrati creano un profilo ciascuno: senza tetto, un
    processo che gira per mesi cresce senza motivo."""
    g = GestoreMemorie(massime=3)
    for nome in ("uno", "due", "tre"):
        g.per_utente(nome)
        time.sleep(0.01)
    g.per_utente("uno")  # torna a parlare: non e' piu' la piu' vecchia

    g.per_utente("quattro")

    attive = set(g.attive())
    assert len(attive) == 3
    assert "due" not in attive
    assert {"uno", "tre", "quattro"} == attive


def test_dimenticare_una_persona_non_tocca_le_altre():
    gestore_memorie.per_utente("alessio").add_user_message("ciao")
    gestore_memorie.per_utente("sonia").add_user_message("ciao")

    assert gestore_memorie.dimentica("alessio") is True
    assert set(gestore_memorie.attive()) == {"sonia"}


def test_il_conteggio_dei_messaggi_non_cresce_all_infinito():
    m = ConversationMemory(max_history=3)
    for i in range(50):
        m.add_user_message(f"messaggio {i}")

    assert len(m.get_messages()) <= 6


# ------------------------------------------- dall'agente, il percorso vero


@pytest.fixture
def casa_finta(monkeypatch):
    """Un alias configurato e nessuna rete: solo il percorso rapido dell'agente."""
    from shinra.infra.db import depositi
    from shinra.services.agent import agent

    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "luce cucina", "entity_id": "light.cucina", "room": "Cucina"}]
    )
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "sonia", "name": "Sonia", "role": "adult"},
        ]
    )

    eseguiti = []

    async def finto_execute_tool(nome, argomenti):
        eseguiti.append((nome, argomenti))
        return {"success": True}

    async def niente_riepilogo():
        return ""

    monkeypatch.setattr("shinra.services.agent.execute_tool", finto_execute_tool)
    monkeypatch.setattr(agent.ha, "get_relevant_entities_summary", niente_riepilogo)
    return eseguiti


async def test_l_agente_scrive_nella_conversazione_di_chi_ha_parlato(casa_finta):
    """Il difetto REL-03 per intero: due persone, due schede, nessuna
    contaminazione. Prima finivano nella stessa cronologia globale."""
    from shinra.services.agent import agent

    await agent.process_user_input("accendi la luce cucina", user_id="alessio")

    assert gestore_memorie.per_utente("alessio").get_messages() != []
    assert gestore_memorie.per_utente("sonia").get_messages() == []


async def test_dopo_accendi_la_memoria_sa_quale_luce_e_accesa(casa_finta):
    """La condizione perche' «spegnila» possa funzionare: nella cronologia
    deve restare scritto `light.cucina`, non solo «acceso»."""
    from shinra.services.agent import agent

    await agent.process_user_input("accendi la luce cucina", user_id="alessio")

    conversazione = " ".join(m["content"] for m in gestore_memorie.per_utente("alessio").get_messages())
    assert "light.cucina" in conversazione
    assert "turn_on" in conversazione


async def test_una_richiesta_da_alexa_non_entra_nella_chat_di_un_altro(casa_finta):
    """Criterio di accettazione: la voce in cucina non deve comparire nella
    scheda che qualcun altro ha aperta in salotto."""
    from shinra.services.agent import agent

    await agent.process_user_input("accendi la luce cucina", user_id="alessio")  # da Alexa
    prima_di_sonia = len(gestore_memorie.per_utente("sonia").get_messages())

    await agent.process_user_input("accendi la luce cucina", user_id="sonia")  # dalla dashboard

    assert prima_di_sonia == 0
    assert len(gestore_memorie.per_utente("alessio").get_messages()) == 3  # utente, azione, risposta


async def test_una_memoria_passata_esplicitamente_ha_la_precedenza(casa_finta):
    """Chi vuole una conversazione separata — un test, un canale futuro — la
    passa e vince sul gestore."""
    from shinra.services.agent import agent

    mia = ConversationMemory()

    await agent.process_user_input("accendi la luce cucina", user_id="alessio", session_memory=mia)

    assert mia.get_messages() != []
    assert gestore_memorie.per_utente("alessio").get_messages() == []


# ------------------------------------------------- perche' non si ripeta


def test_nessun_modulo_si_costruisce_una_memoria_tutta_sua():
    """Il difetto era un singleton globale in `core/memory.py`.

    Se domani qualcuno ne crea un altro — in una rotta, in un canale nuovo —
    il problema torna identico e senza sintomi visibili. L'unico posto da cui
    si prende una conversazione e' `gestore_memorie.per_utente()`.
    """
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent.parent
    colpevoli = []
    for percorso in (radice / "src" / "shinra").rglob("*.py"):
        if percorso.name == "memory.py" or "__pycache__" in percorso.parts:
            continue
        if "ConversationMemory(" in percorso.read_text(encoding="utf-8"):
            colpevoli.append(str(percorso.relative_to(radice)))

    assert colpevoli == [], (
        f"{colpevoli} si costruisce una ConversationMemory per conto suo: "
        "le conversazioni si prendono da gestore_memorie.per_utente()"
    )
