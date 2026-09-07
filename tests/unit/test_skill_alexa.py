"""L'adattatore fra Amazon Alexa e l'agente.

Era il secondo modulo meno coperto del progetto — quattordici per cento — ed
e' l'unica porta di Shinra affacciata su Internet. Quello che entra da qui
arriva all'agente e comanda la casa.

Il lavoro di questo modulo e' tradurre: Alexa consegna intenti con slot, e
l'agente vuole una frase in italiano. Sbagliare la traduzione significa che
un comando detto bene non viene eseguito — e a voce non si vede perche'.

Riferimento: issue #18.
"""

from __future__ import annotations

import pytest

from core.archivio import depositi
from integrations.alexa import skill_handler


@pytest.fixture
def agente_finto(monkeypatch):
    """Registra cosa arriva all'agente, senza modello ne' rete."""
    ricevute: list[str] = []
    risposta = {"response": "Fatto."}

    async def finto(user_text, user_id=None, **altro):
        ricevute.append(user_text)
        return dict(risposta)

    monkeypatch.setattr(skill_handler.agent, "process_user_input", finto)
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "sonia", "name": "Sonia", "role": "adult"},
        ]
    )
    return {"ricevute": ricevute, "risposta": risposta}


def _intento(nome: str, slot: dict | None = None, attributi: dict | None = None) -> dict:
    return {
        "request": {"type": "IntentRequest", "intent": {"name": nome, "slots": slot or {}}},
        "session": {"attributes": attributi or {}},
    }


# ------------------------------------------------------------------ apertura


async def test_l_apertura_saluta_e_tiene_aperta_la_sessione(agente_finto):
    """«Alexa, apri Kyra» non deve chiudere subito: chi apre vuole poi dire
    qualcosa."""
    esito = await skill_handler.handle_alexa_request(
        {"request": {"type": "LaunchRequest"}, "session": {"attributes": {}}}
    )

    assert esito["response"]["shouldEndSession"] is False
    assert "Alessio" in esito["response"]["outputSpeech"]["text"]


async def test_stop_chiude_la_sessione(agente_finto):
    esito = await skill_handler.handle_alexa_request(_intento("AMAZON.StopIntent"))

    assert esito["response"]["shouldEndSession"] is True


async def test_l_aiuto_resta_in_ascolto(agente_finto):
    esito = await skill_handler.handle_alexa_request(_intento("AMAZON.HelpIntent"))

    assert esito["response"]["shouldEndSession"] is False


# ------------------------------------------------------------- la traduzione


async def test_turn_on_diventa_una_frase_che_l_agente_capisce(agente_finto):
    await skill_handler.handle_alexa_request(
        _intento("TurnOnIntent", {"device": {"value": "luce della cucina"}})
    )

    assert agente_finto["ricevute"] == ["accendi luce della cucina"]


async def test_turn_off_diventa_spegni(agente_finto):
    await skill_handler.handle_alexa_request(
        _intento("TurnOffIntent", {"device": {"value": "luce della cucina"}})
    )

    assert agente_finto["ricevute"] == ["spegni luce della cucina"]


async def test_la_modalita_diventa_una_frase_di_attivazione(agente_finto):
    await skill_handler.handle_alexa_request(_intento("ActivateModeIntent", {"mode": {"value": "cinema"}}))

    assert agente_finto["ricevute"] == ["modalità cinema"]


async def test_una_domanda_generica_passa_com_e(agente_finto):
    await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "che tempo fa domani"}})
    )

    assert agente_finto["ricevute"] == ["che tempo fa domani"]


@pytest.mark.parametrize(
    "detto,atteso",
    [
        ("accendere il salotto", "accendi il salotto"),
        ("spegnere la cucina", "spegni la cucina"),
    ],
)
async def test_l_infinito_diventa_imperativo(agente_finto, detto, atteso):
    """Alexa consegna spesso l'infinito — «di accendere il salotto» — e
    l'agente riconosce l'imperativo. Senza questa conversione il percorso
    rapido non scatta e il comando finisce al modello."""
    await skill_handler.handle_alexa_request(_intento("GeneralQueryIntent", {"query": {"value": detto}}))

    assert agente_finto["ricevute"] == [atteso]


@pytest.mark.parametrize(
    "detto",
    ["hey kyra accendi il salotto", "kyra di accendere il salotto", "hey kyra puoi accendere il salotto"],
)
def test_il_nome_di_invocazione_viene_tolto(detto):
    """Alexa a volte lascia il nome della skill dentro lo slot: se restasse,
    l'agente riceverebbe «hey kyra accendi...» e non riconoscerebbe il
    comando."""
    pulito = skill_handler.rimuovi_prefisso_invocazione(detto)

    assert not pulito.lower().startswith(("hey", "kyra"))
    assert "salotto" in pulito


def test_che_non_viene_scambiato_per_una_richiesta():
    """«che ore sono» comincia con una parola che somiglia a un preambolo:
    toglierla lascerebbe «ore sono», che non vuol dire niente."""
    assert skill_handler.rimuovi_prefisso_invocazione("che ore sono") == "che ore sono"


# ------------------------------------------------------------- chi sta parlando


async def test_dire_il_proprio_nome_cambia_profilo(agente_finto):
    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "sono Sonia"}})
    )

    assert esito["sessionAttributes"]["user_id"] == "sonia"
    assert "Sonia" in esito["response"]["outputSpeech"]["text"]


async def test_il_profilo_scelto_resta_per_le_richieste_successive(agente_finto, monkeypatch):
    visti: list[str] = []

    async def finto(user_text, user_id=None, **altro):
        visti.append(user_id)
        return {"response": "Fatto."}

    monkeypatch.setattr(skill_handler.agent, "process_user_input", finto)

    await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "accendi la luce"}}, {"user_id": "sonia"})
    )

    assert visti == ["sonia"]


# --------------------------------------------------------------- la risposta


async def test_la_risposta_viene_ripulita_per_la_voce(agente_finto):
    """Markdown ed emoji letti a voce da Alexa sono rumore."""
    agente_finto["risposta"]["response"] = "**Fatto!** Ho acceso la luce 💡"

    esito = await skill_handler.handle_alexa_request(_intento("TurnOnIntent", {"device": {"value": "luce"}}))

    detto = esito["response"]["outputSpeech"]["text"]
    assert "*" not in detto
    assert "💡" not in detto


async def test_una_risposta_che_finisce_con_una_domanda_tiene_aperto(agente_finto):
    """Se l'assistente chiede qualcosa, chiudere la sessione costringerebbe a
    ripetere «Alexa, apri Kyra» per rispondere."""
    agente_finto["risposta"]["response"] = "Quale luce vuoi accendere?"

    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "accendi"}})
    )

    assert esito["response"]["shouldEndSession"] is False


async def test_una_risposta_vuota_non_lascia_alexa_muta(agente_finto):
    agente_finto["risposta"]["response"] = ""

    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "boh"}})
    )

    assert esito["response"]["outputSpeech"]["text"].strip()
