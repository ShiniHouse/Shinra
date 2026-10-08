"""Due persone nella stessa casa, due lingue (issue #36).

Il criterio di accettazione della scheda: *«Due utenti con lingue diverse
ricevono risposte nella propria lingua»*. Prima la lingua era una per
installazione; adesso e' del profilo, e quando il profilo non ne ha una si
ricade su quella dell'installazione.

I test usano gli intenti veri e l'agente vero, con la rete finta: l'unica cosa
che cambia da una prova all'altra e' il profilo di chi parla.
"""

from __future__ import annotations

import pytest

from shinra.config.prompt_templates import get_system_prompt
from shinra.infra.db import depositi
from shinra.infra.lingue import lingue_disponibili, schemi
from shinra.services.intenti import Richiesta, instrada
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile


@pytest.fixture
def casa(monkeypatch):
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "kitchen light", "entity_id": "light.cucina", "room": "Kitchen"}]
    )
    depositi.modalita.sostituisci_tutto([])

    chiamate: list[tuple[str, dict]] = []
    risposte: dict[str, dict] = {}

    async def finto_execute_tool(nome, argomenti):
        chiamate.append((nome, argomenti))
        return risposte.get(nome, {"success": True})

    for modulo in ("shinra.services.intenti.casa", "shinra.services.intenti.informazioni"):
        monkeypatch.setattr(f"{modulo}.execute_tool", finto_execute_tool)
    return {"chiamate": chiamate, "risposte": risposte}


def _profilo(nome: str, lingua: str = "") -> UserProfile:
    return UserProfile(id=nome.lower(), name=nome, lingua=lingua)


def _richiesta(testo: str, profilo: UserProfile | None) -> Richiesta:
    return Richiesta(testo=testo, profilo=profilo, memoria=ConversationMemory())


# -------------------------------------------------------------- gli intenti


async def test_la_stessa_azione_riceve_risposta_nella_lingua_di_chi_la_chiede(casa):
    """Due persone comandano la stessa luce: ciascuna sente la propria lingua."""
    casa["risposte"]["control_device"] = {"success": True}
    alessio = _profilo("Alessio", "it")
    sam = _profilo("Sam", "en")

    # Alessio e' italiano, la luce ha un nome inglese solo perche' l'alias e' uno.
    it = await instrada(_richiesta("accendi kitchen light", alessio))
    en = await instrada(_richiesta("turn on the kitchen light", sam))

    assert it is not None and en is not None
    assert it.testo == "Kitchen light acceso."
    assert en.testo == "Kitchen light is on."


async def test_ognuno_capisce_solo_la_propria_lingua(casa):
    """Gli schemi sono per persona: l'inglese non accende niente a un profilo
    italiano, e viceversa. Se funzionasse, vorrebbe dire che gli schemi sono
    ancora globali."""
    alessio = _profilo("Alessio", "it")
    sam = _profilo("Sam", "en")

    assert await instrada(_richiesta("turn on the kitchen light", alessio)) is None
    assert await instrada(_richiesta("accendi kitchen light", sam)) is None
    assert (
        casa["chiamate"] == []
    ), "un comando e' partito per una frase che non era nella lingua di chi l'ha detta"


async def test_il_meteo_risponde_nella_lingua_del_profilo(casa):
    casa["risposte"]["get_weather"] = {
        "success": True,
        "localita": "Bologna",
        "adesso": {"temperatura": "18", "condizione": "Sereno"},
        "previsioni": [{"temp_max": 22, "temp_min": 11, "condizione": "Sereno"}],
    }

    it = await instrada(_richiesta("che meteo fa a Bologna", _profilo("Alessio", "it")))
    en = await instrada(_richiesta("what's the weather in Bologna", _profilo("Sam", "en")))

    assert it.testo.startswith("A Bologna attualmente")
    assert en.testo.startswith("In Bologna it is currently")
    # La citta' si estrae con lo schema della lingua di chi parla.
    assert ("get_weather", {"location": "Bologna", "days": 2}) in casa["chiamate"]


async def test_un_profilo_senza_lingua_segue_l_installazione(casa, monkeypatch):
    """Chi non ha mai scelto non cambia: la sua lingua e' quella configurata."""
    from shinra.config import settings as impostazioni

    anonimo = _profilo("Anna")  # lingua vuota
    assert await instrada(_richiesta("turn on the kitchen light", anonimo)) is None

    monkeypatch.setattr(impostazioni.settings.assistant, "language", "en")
    risposta = await instrada(_richiesta("turn on the kitchen light", anonimo))
    assert risposta is not None and risposta.testo == "Kitchen light is on."


async def test_una_lingua_che_non_esiste_ripiega_sull_italiano(casa):
    """Un refuso nel profilo non deve rendere muta la casa."""
    refuso = _profilo("Gian", "klingon")
    risposta = await instrada(_richiesta("accendi kitchen light", refuso))
    assert risposta is not None and risposta.testo == "Kitchen light acceso."


# ------------------------------------------------------------- il prompt


def test_il_prompt_di_sistema_e_nella_lingua_del_profilo():
    it = get_system_prompt(
        lingua=schemi("it"), user_profile=_profilo("Alessio", "it"), default_city="Bologna"
    )
    en = get_system_prompt(lingua=schemi("en"), user_profile=_profilo("Sam", "en"), default_city="Bologna")

    assert it.startswith("Sei ") and "assistente domestico" in it and "REGOLE SUI TOOL" in it
    assert en.startswith("You are ") and "intelligent home assistant" in en and "TOOL RULES" in en
    assert "REGOLE SUI TOOL" not in en, "il prompt inglese porta ancora un pezzo italiano"
    assert "You are talking to Sam" in en
    # I nomi degli strumenti sono gli stessi in ogni lingua: sono codice.
    for strumento in ("get_weather", "control_device", "comanda_clima"):
        assert strumento in it and strumento in en


def test_la_data_nel_prompt_non_dipende_dal_locale_del_sistema():
    from datetime import datetime

    mercoledi = datetime(2026, 9, 30, 21, 40)
    assert schemi("it").data_e_ora(mercoledi) == "mercoledì 30 settembre 2026, ore 21:40"
    assert schemi("en").data_e_ora(mercoledi) == "Wednesday, September 30, 2026, 21:40"


# -------------------------------------------------------------- l'agente


async def test_il_rifiuto_per_un_argomento_vietato_e_nella_lingua_del_profilo(monkeypatch):
    from shinra.services.agent import agent

    bambina_it = UserProfile(
        id="bimba", name="Bimba", age_group="child", restricted_topics=["guerra"], lingua="it"
    )
    bambino_en = UserProfile(id="kid", name="Kid", age_group="child", restricted_topics=["war"], lingua="en")

    it = await agent.process_user_input("parlami della guerra", user_profile=bambina_it)
    en = await agent.process_user_input("tell me about the war", user_profile=bambino_en)

    assert it["response"].startswith("Di questo preferisco non parlare")
    assert en["response"].startswith("I'd rather not talk about that")


# ------------------------------------------------ le lingue hanno le stesse chiavi


def test_ogni_lingua_ha_le_stesse_frasi_e_gli_stessi_pezzi_di_prompt():
    """Aggiungere una frase al codice senza aggiungerla a tutte le lingue
    e' il modo in cui una lingua resta indietro. Il caricatore lo dice per
    nome; questa guardia lo dice per tutte quelle che esistono."""
    assert {"it", "en"} <= set(lingue_disponibili())
    riferimento = schemi("it")
    for lingua in lingue_disponibili():
        s = schemi(lingua)
        assert set(s.messaggi) == set(riferimento.messaggi), f"{lingua}: frasi diverse dall'italiano"
        assert set(s.prompt) == set(riferimento.prompt), f"{lingua}: pezzi di prompt diversi dall'italiano"
        assert len(s.giorni) == 7 and len(s.mesi) == 12, f"{lingua}: calendario incompleto"


def test_le_frasi_hanno_gli_stessi_segnaposto_in_ogni_lingua():
    """«{nome} acceso.» con un segnaposto in meno e' una frase che perde il
    nome della luce senza dirlo: si vede solo parlando."""
    import string

    def segnaposto(testo: str) -> set[str]:
        return {c for _, c, _, _ in string.Formatter().parse(testo) if c}

    riferimento = schemi("it")
    for lingua in lingue_disponibili():
        s = schemi(lingua)
        for chiave, frase in s.messaggi.items():
            assert segnaposto(frase) == segnaposto(
                riferimento.messaggi[chiave]
            ), f"{lingua}.messaggi.{chiave}"
        for chiave, frase in s.prompt.items():
            assert segnaposto(frase) == segnaposto(riferimento.prompt[chiave]), f"{lingua}.prompt.{chiave}"


# ------------------------------------------------- il profilo e l'interfaccia


def test_le_lingue_si_chiedono_al_server(cliente_autenticato):
    risposta = cliente_autenticato.get("/api/lingue")

    assert risposta.status_code == 200
    visto = risposta.json()
    assert {v["codice"] for v in visto["lingue"]} >= {"it", "en"}
    assert {v["nome"] for v in visto["lingue"]} >= {"italiano", "English"}
    assert visto["installazione"] in {v["codice"] for v in visto["lingue"]}


def test_la_lingua_del_profilo_si_salva_e_si_rilegge(cliente_autenticato):
    """Dal form al database e ritorno: se una colonna o un campo mancasse, la
    lingua scelta tornerebbe vuota al caricamento successivo, senza errori."""
    corpo = {"id": "sam", "name": "Sam", "role": "adult", "lingua": "en"}
    assert cliente_autenticato.post("/api/users", json=corpo).status_code == 200

    profili = {p["id"]: p for p in cliente_autenticato.get("/api/users").json()}
    assert profili["sam"]["lingua"] == "en"

    # E tornare a «come la casa» vuol dire svuotarla, non cancellarla: il
    # campo esiste sempre.
    corpo["lingua"] = ""
    assert cliente_autenticato.post("/api/users", json=corpo).status_code == 200
    profili = {p["id"]: p for p in cliente_autenticato.get("/api/users").json()}
    assert profili["sam"]["lingua"] == ""
