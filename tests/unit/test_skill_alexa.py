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

from typing import Any

import pytest

from shinra.channels.alexa import skill_handler
from shinra.infra.db import depositi


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
    assert "online" in esito["response"]["outputSpeech"]["text"].lower()


async def test_l_apertura_non_saluta_per_nome_chi_non_e_riconosciuto(agente_finto):
    """Prima qui si salutava il primo profilo dell'elenco — l'amministratore —
    chiunque avesse aperto la skill. Diceva a un ospite come si chiama il
    padrone di casa, e faceva credere a chi ascoltava di essere stato
    riconosciuto. Riferimento: issue #48.

    Il saluto non deve contenere **nessun** nome, non solo non contenere
    quello dell'amministratore: la prima versione di questo test verificava
    solo la seconda cosa, e restava verde davanti a un saluto che diceva
    «buongiorno, Voce non riconosciuta».
    """
    esito = await skill_handler.handle_alexa_request(
        {"request": {"type": "LaunchRequest"}, "session": {"attributes": {}}}
    )

    detto = esito["response"]["outputSpeech"]["text"]
    assert "," not in detto.split(".")[0], f"il saluto nomina qualcuno: {detto!r}"
    assert "Alessio" not in detto


async def test_l_apertura_saluta_per_nome_chi_e_riconosciuto(agente_finto):
    """L'altra meta': riconoscere serve a qualcosa, e si sente."""
    depositi.voci_sentite.segna_passaggio("amzn1.person.ALESSIO")
    depositi.voci_sentite.associa("amzn1.person.ALESSIO", "alessio")

    esito = await skill_handler.handle_alexa_request(
        {
            "request": {"type": "LaunchRequest"},
            "session": {"attributes": {}},
            "context": {"System": {"person": {"personId": "amzn1.person.ALESSIO"}}},
        }
    )

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


async def test_dire_il_proprio_nome_non_cambia_piu_profilo(agente_finto):
    """Qui c'era il contrario: «sono Sonia» e da quel momento la sessione era
    Sonia, senza nessuna prova. Un'identita' che si ottiene dicendola non e'
    un'identita', e rende priva di senso ogni riga scritta sui permessi del
    canale vocale. Riferimento: issue #48."""
    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "sono Sonia"}})
    )

    assert esito["sessionAttributes"].get("user_id") is None
    assert agente_finto["ricevute"] == [], "la frase non deve nemmeno arrivare all'agente"
    assert "profili vocali" in esito["response"]["outputSpeech"]["text"]


async def test_il_rifiuto_spiega_come_farsi_riconoscere(agente_finto):
    """Un rifiuto che non dice cosa fare si ripete: chi non capisce riprova, e
    dopo tre volte conclude che l'impianto e' rotto."""
    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "parla con Alessio"}})
    )

    detto = esito["response"]["outputSpeech"]["text"]
    assert "impostazioni" in detto
    assert esito["response"]["shouldEndSession"] is False, "chi ha chiesto vuole dire dell'altro"


async def test_sono_stanco_non_e_un_cambio_di_profilo(agente_finto):
    """«sono» davanti a un aggettivo non e' una dichiarazione di identita': se
    lo fosse, la casa risponderebbe una spiegazione sui profili vocali a chi
    dice di essere stanco."""
    await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "sono stanco"}})
    )

    assert agente_finto["ricevute"] == ["sono stanco"]


async def test_cambia_utente_in_ilaria_non_diventa_laria(agente_finto):
    """La preposizione va tolta come parola intera. Toglierla come insieme di
    caratteri faceva di «Ilaria» una «laria», che non e' il nome di nessuno —
    e la frase sarebbe finita all'agente come una domanda qualunque."""
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "ilaria", "name": "Ilaria", "role": "adult"},
        ]
    )

    esito = await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "cambia utente in Ilaria"}})
    )

    assert agente_finto["ricevute"] == []
    assert "profili vocali" in esito["response"]["outputSpeech"]["text"]


async def test_l_agente_non_riceve_il_profilo_dell_amministratore_da_sconosciuti(agente_finto, monkeypatch):
    """Il buco piu' silenzioso dei tre: l'agente, senza un profilo, ripiega sul
    primo dell'elenco. Una voce sconosciuta otteneva cosi' la memoria di
    conversazione e il tono dell'amministratore."""
    visti: list[Any] = []

    async def finto(user_text, user_id=None, user_profile=None, **altro):
        visti.append(user_profile)
        return {"response": "Fatto."}

    monkeypatch.setattr(skill_handler.agent, "process_user_input", finto)

    await skill_handler.handle_alexa_request(
        _intento("GeneralQueryIntent", {"query": {"value": "accendi la luce"}}, {"user_id": "alessio"})
    )

    assert len(visti) == 1
    profilo = visti[0]
    assert profilo is not None, "senza profilo l'agente ripiega sull'amministratore"
    assert profilo.id != "alessio"
    assert profilo.role == "guest"


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
