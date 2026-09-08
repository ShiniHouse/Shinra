"""Ogni intento risponde per conto suo, e ha il suo test.

`process_user_input` era lunga duecentocinquanta righe e conteneva, in fila:
intervista, timer, promemoria, modalita', controllo dei dispositivi, meteo,
notizie ed enciclopedia. Non era verificabile a pezzi, e ogni intento nuovo
la allungava. Riferimento: issue #17.

Due difetti di riconoscimento erano gia' noti e sono chiusi qui:
il falso positivo sul meteo e l'estrazione della citta' che spezzava i nomi
composti.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.services.intenti import Richiesta, instrada, intenti
from shinra.services.intenti.casa import ControlloDispositivo, TemperaturaInterna
from shinra.services.intenti.informazioni import Meteo


@pytest.fixture
def casa(monkeypatch):
    """Alias e modalita' configurati, e nessuna chiamata di rete."""
    depositi.alias.sostituisci_tutto(
        [
            {"id": "a1", "alias": "luce cucina", "entity_id": "light.cucina", "room": "Cucina"},
            {"id": "a2", "alias": "clima camera", "entity_id": "climate.camera", "room": "Camera"},
        ]
    )
    depositi.modalita.sostituisci_tutto(
        [
            {
                "id": "m1",
                "name": "Cinema",
                "trigger_phrases": ["modalità cinema", "mettiamo su un film"],
                "enabled": True,
                "actions": [],
            }
        ]
    )

    chiamate: list[tuple[str, dict]] = []
    risposte: dict[str, dict] = {}

    async def finto_execute_tool(nome, argomenti):
        chiamate.append((nome, argomenti))
        return risposte.get(nome, {"success": True})

    for modulo in ("shinra.services.intenti.casa", "shinra.services.intenti.informazioni"):
        monkeypatch.setattr(f"{modulo}.execute_tool", finto_execute_tool)

    return {"chiamate": chiamate, "risposte": risposte}


def _richiesta(testo: str) -> Richiesta:
    from shinra.services.memory import ConversationMemory

    return Richiesta(testo=testo, memoria=ConversationMemory())


# --------------------------------------------------------------- il registro


def test_gli_intenti_sono_ordinati_per_priorita():
    priorita = [i.priorita for i in intenti()]
    assert priorita == sorted(priorita)


def test_ogni_intento_ha_un_nome_suo():
    nomi = [i.nome for i in intenti()]
    assert len(nomi) == len(set(nomi))


def test_aggiungere_un_intento_non_richiede_di_toccare_l_agente():
    """Criterio di accettazione: un intento nuovo si registra, non si
    incastra dentro `process_user_input`."""
    import inspect

    from shinra.services import agent as modulo_agente
    from shinra.services.intenti.base import Intento, Risposta, registra

    class Saluto(Intento):
        nome = "saluto-di-prova"
        priorita = 1

        def applicabile(self, richiesta):
            return "buongiorno kyra" in richiesta.minuscolo

        async def esegui(self, richiesta):
            return Risposta("Buongiorno!")

    sorgente_prima = inspect.getsource(modulo_agente.ShinraAgent.process_user_input)
    registra(Saluto())
    try:
        assert any(i.nome == "saluto-di-prova" for i in intenti())
        assert sorgente_prima == inspect.getsource(modulo_agente.ShinraAgent.process_user_input)
    finally:
        from shinra.services.intenti import base

        base._INTENTI[:] = [i for i in base._INTENTI if i.nome != "saluto-di-prova"]


# ------------------------------------------------- il falso positivo sul meteo


async def test_che_temperatura_c_e_in_salotto_legge_il_sensore(casa):
    """Il difetto: il percorso rapido scattava sulla sola parola
    «temperatura» e interrogava Open-Meteo. Alla domanda sulla stanza si
    rispondeva con la temperatura esterna della citta'. Sbagliata, e detta
    con sicurezza."""
    casa["risposte"]["get_indoor_temperature"] = {
        "success": True,
        "letture": [{"entita": "sensor.salotto", "nome": "Salotto", "valore": "21.4", "unita": "°C"}],
    }

    risposta = await instrada(_richiesta("che temperatura c'è in salotto"))

    strumenti = [nome for nome, _ in casa["chiamate"]]
    assert "get_indoor_temperature" in strumenti
    assert "get_weather" not in strumenti
    assert "21.4" in risposta.testo


async def test_che_temperatura_fa_a_bologna_resta_il_meteo(casa):
    casa["risposte"]["get_weather"] = {
        "success": True,
        "localita": "Bologna (IT)",
        "adesso": {"temperatura": "9 gradi", "condizione": "Sereno"},
        "previsioni": [{"temp_max": 14, "temp_min": 4}],
    }

    risposta = await instrada(_richiesta("che temperatura c'è a Bologna"))

    strumenti = [nome for nome, _ in casa["chiamate"]]
    assert "get_weather" in strumenti
    assert "get_indoor_temperature" not in strumenti
    assert "Bologna" in risposta.testo


async def test_senza_sensori_lo_dice_invece_di_dare_il_meteo(casa):
    """Rispondere con la temperatura di fuori sarebbe peggio che ammettere
    di non saperlo."""
    casa["risposte"]["get_indoor_temperature"] = {"success": True, "letture": []}

    risposta = await instrada(_richiesta("che temperatura c'è in cucina"))

    assert "sensore" in risposta.testo.lower()
    assert "get_weather" not in [nome for nome, _ in casa["chiamate"]]


# ------------------------------------------------------- la citta' composta


@pytest.mark.parametrize(
    "frase,attesa",
    [
        ("che tempo fa a Reggio Emilia", "Reggio Emilia"),
        ("meteo a San Giovanni in Persiceto", "San Giovanni in Persiceto"),
        ("previsioni per Forlì", "Forlì"),
        ("che tempo fa ad Ancona", "Ancona"),
        ("meteo a Castel San Pietro Terme", "Castel San Pietro Terme"),
    ],
)
def test_i_nomi_composti_non_si_spezzano(frase, attesa):
    """L'espressione precedente catturava una parola sola: mezza Italia si
    spezzava a meta', e le esclusioni erano una lista scritta a mano."""
    assert Meteo.citta(frase) == attesa


def test_senza_citta_si_usa_quella_predefinita():
    from shinra.config.settings import settings

    assert Meteo.citta("che tempo fa domani") == (settings.assistant.default_city or "Roma")


async def test_una_citta_inventata_ripiega_sulla_predefinita(casa):
    """Al posto di una lista di parole da escludere scritta a mano, si chiede
    alla geocodifica: se non conosce il nome, si ripiega."""
    chiamate = casa["chiamate"]

    async def secondo_tentativo(nome, argomenti):
        chiamate.append((nome, argomenti))
        if argomenti.get("location") == "Casa Mia":
            return {"success": False, "error": "località non trovata"}
        return {
            "success": True,
            "localita": "Roma (IT)",
            "adesso": {"temperatura": "12 gradi", "condizione": "Nuvoloso"},
            "previsioni": [{"temp_max": 16}],
        }

    import shinra.services.intenti.informazioni as modulo

    modulo.execute_tool = secondo_tentativo
    risposta = await instrada(_richiesta("che tempo fa a Casa Mia"))

    citta_provate = [a.get("location") for _, a in chiamate]
    assert "Casa Mia" in citta_provate
    assert "Roma" in risposta.testo


# --------------------------------------------------------------- dispositivi


async def test_accendi_la_luce_della_cucina(casa):
    risposta = await instrada(_richiesta("accendi la luce cucina"))

    assert casa["chiamate"][0] == ("control_device", {"entity_id": "light.cucina", "action": "turn_on"})
    assert "acceso" in risposta.testo.lower()


async def test_spegni_usa_il_comando_giusto(casa):
    await instrada(_richiesta("spegni la luce cucina"))

    assert casa["chiamate"][0][1]["action"] == "turn_off"


async def test_un_dispositivo_sconosciuto_passa_al_modello(casa):
    """Se l'alias non c'e', l'intento si tira indietro: la frase la
    interpreta il modello, che puo' fare di meglio che sbagliare in fretta."""
    risposta = await instrada(_richiesta("accendi la macchina del caffè"))

    assert risposta is None
    assert casa["chiamate"] == []


async def test_l_azione_finisce_nella_memoria_della_conversazione(casa):
    """Perche' «spegnila» possa funzionare subito dopo."""
    richiesta = _richiesta("accendi la luce cucina")

    await instrada(richiesta)

    conversazione = " ".join(m["content"] for m in richiesta.memoria.get_messages())
    assert "light.cucina" in conversazione


# ---------------------------------------------------------------- modalita'


async def test_una_frase_di_attivazione_avvia_la_modalita(casa):
    risposta = await instrada(_richiesta("mettiamo su un film stasera"))

    assert casa["chiamate"][0] == ("activate_mode", {"mode_name": "Cinema"})
    assert "Cinema" in risposta.testo


async def test_una_modalita_disattivata_non_scatta(casa):
    depositi.modalita.aggiorna("m1", {"enabled": False})

    risposta = await instrada(_richiesta("mettiamo su un film stasera"))

    assert risposta is None


# --------------------------------------------------------------- robustezza


async def test_un_intento_che_esplode_non_blocca_gli_altri(casa, monkeypatch):
    """Al massimo la richiesta finisce al modello: la persona non resta
    comunque senza risposta."""
    monkeypatch.setattr(
        TemperaturaInterna, "applicabile", lambda self, r: (_ for _ in ()).throw(RuntimeError("guasto"))
    )
    casa["risposte"]["control_device"] = {"success": True}

    risposta = await instrada(_richiesta("accendi la luce cucina"))

    assert risposta is not None
    assert "acceso" in risposta.testo.lower()


def test_il_riconoscimento_non_fa_rete(casa):
    """`applicabile` viene chiamata su ogni intento a ogni frase: se una di
    esse contattasse Home Assistant, ogni «ciao» costerebbe una richiesta."""
    richiesta = _richiesta("ciao come stai")

    for intento in intenti():
        intento.applicabile(richiesta)

    assert casa["chiamate"] == []


def test_l_intento_dispositivi_riconosce_solo_i_comandi():
    intento = ControlloDispositivo()

    assert intento.applicabile(_richiesta("accendi la luce"))
    assert not intento.applicabile(_richiesta("com'è il tempo"))
    assert not intento.applicabile(_richiesta("mi accendi una sigaretta è un modo di dire"))
