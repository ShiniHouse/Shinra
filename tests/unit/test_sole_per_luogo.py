"""Alba e tramonto per il luogo giusto, e il luogo di chi parla nel prompt (#344).

«A che ora tramonta?» risponde per il luogo nominato, poi per dove si trova chi parla, poi per la casa principale; non ruba le
frasi del meteo ne' quelle che creano una regola («accendi la luce all'alba»). Nel prompt va il nome del luogo, mai le coordinate,
e nel contesto della richiesta (non nel prompt di sistema, che deve restare uguale fra una richiesta e l'altra).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from shinra.config.prompt_templates import get_contesto_della_richiesta, get_system_prompt
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.infra.homeassistant.stati import cache_stati
from shinra.infra.lingue import schemi
from shinra.services import luoghi
from shinra.services.agent import ShinraAgent
from shinra.services.intenti import informazioni as modulo
from shinra.services.intenti import instrada
from shinra.services.intenti.base import Richiesta
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile
from shinra.skills import weather

CASA = (41.902784, 12.496366)
MARE = (44.123456, 12.234567)


@pytest.fixture(autouse=True)
def due_luoghi():
    deposito.sostituisci_tutto([])
    cache_stati.svuota()
    luoghi.registra({"nome": "Casa", "latitudine": CASA[0], "longitudine": CASA[1], "origine": "telefono"})
    luoghi.registra(
        {"nome": "Casa al mare", "latitudine": MARE[0], "longitudine": MARE[1], "origine": "telefono"}
    )
    yield
    deposito.sostituisci_tutto([])
    cache_stati.svuota()


@pytest.fixture
def sole(monkeypatch):
    chiamate: list[str] = []

    async def di_un_luogo(nome, latitudine, longitudine, days=2):
        chiamate.append(nome)
        alba, tramonto = ("06:12", "19:45") if "mare" in nome else ("06:41", "18:12")
        return {
            "success": True,
            "localita": nome,
            "sole": {"alba": alba, "tramonto": tramonto},
            "adesso": {"temperatura": "18°C", "condizione": "Sereno"},
            "previsioni": [{"temp_max": 20, "temp_min": 12}],
        }

    monkeypatch.setattr(modulo, "meteo_di_un_luogo", di_un_luogo)
    return chiamate


def _richiesta(testo: str, profilo=None) -> Richiesta:
    return Richiesta(testo=testo, profilo=profilo, memoria=ConversationMemory())


# ------------------------------------------------------------------ l'intento


async def test_a_che_ora_tramonta_risponde_per_il_luogo_nominato(sole):
    risposta = await instrada(_richiesta("a che ora tramonta nella casa al mare"))
    assert sole == ["Casa al mare"]
    assert "19:45" in risposta.testo and "06:12" in risposta.testo and "Casa al mare" in risposta.testo


async def test_senza_luogo_nominato_vale_la_casa_principale(sole):
    risposta = await instrada(_richiesta("a che ora tramonta oggi"))
    assert sole == ["Casa"] and "18:12" in risposta.testo


async def test_due_luoghi_due_risposte_diverse(sole):
    a = await instrada(_richiesta("quando sorge il sole a casa al mare"))
    b = await instrada(_richiesta("quando sorge il sole"))
    assert "06:12" in a.testo and "06:41" in b.testo


async def test_dove_si_trova_chi_parla_vince_sulla_casa(sole):
    cache_stati.aggiorna(
        {
            "entity_id": "person.alessio",
            "state": "not_home",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "attributes": {"latitude": MARE[0], "longitude": MARE[1]},
        }
    )
    profilo = UserProfile(id="u1", name="Alessio", entita_posizione="person.alessio")
    await instrada(_richiesta("a che ora tramonta", profilo))
    assert sole == ["Casa al mare"]


@pytest.mark.parametrize(
    "frase",
    [
        "che tempo fa oggi",
        "accendi la luce all'alba",
        "crea una regola che alza le tapparelle all'alba",
        "chiama Albano",
    ],
)
async def test_non_ruba_le_frasi_che_non_sono_sue(sole, frase):
    richiesta = _richiesta(frase)
    assert not modulo.Sole().applicabile(richiesta)


@pytest.mark.parametrize(
    "frase",
    [
        "a che ore tramonta il sole?",
        "A che ore sorge il sole",
        "tramonta il sole oggi?",
        "a che ora tramonta",
    ],
)
async def test_si_riconoscono_anche_i_modi_di_dire_che_si_sentono_davvero(sole, frase):
    """«A che ore tramonta il sole?» (con «ore») e' la frase scritta davvero sul server il 2026-10-20, e non scattava."""
    assert modulo.Sole().applicabile(_richiesta(frase))


async def test_il_meteo_non_ruba_le_frasi_del_sole(sole):
    risposta = await instrada(_richiesta("a che ora tramonta oggi"))
    assert "attualmente" not in risposta.testo, "ha risposto con il meteo invece che con alba e tramonto"


async def test_se_la_frase_chiede_tempo_e_tramonto_vince_il_sole(sole):
    risposta = await instrada(_richiesta("che tempo fa e a che ora tramonta"))
    assert "18:12" in risposta.testo and "attualmente" not in risposta.testo


async def test_senza_dati_del_sole_non_inventa_una_risposta(monkeypatch):
    async def senza(nome, latitudine, longitudine, days=2):
        return {"success": True, "localita": nome, "adesso": {}, "previsioni": []}

    monkeypatch.setattr(modulo, "meteo_di_un_luogo", senza)
    assert await modulo.Sole().esegui(_richiesta("a che ora tramonta")) is None


async def test_in_inglese_risponde_nella_lingua_di_chi_chiede(sole):
    profilo = UserProfile(id="u2", name="Alex", lingua="en")
    richiesta = Richiesta(testo="what time is sunset today", profilo=profilo, memoria=ConversationMemory())
    risposta = await instrada(richiesta)
    assert "sun" in risposta.testo and "18:12" in risposta.testo


# ------------------------------------------------------------------ Open-Meteo


async def test_il_meteo_porta_alba_e_tramonto_all_ora_del_posto():
    risposte = {
        "current": {"weather_code": 0, "temperature_2m": 18},
        "daily": {
            "time": ["2026-10-20"],
            "weather_code": [0],
            "temperature_2m_max": [20],
            "temperature_2m_min": [12],
            "precipitation_probability_max": [0],
            "sunrise": ["2026-10-20T06:41"],
            "sunset": ["2026-10-20T18:12"],
        },
    }

    def risposta(richiesta):
        assert "timezone=auto" in str(
            richiesta.url
        ), "senza il fuso del posto l'ora di alba e tramonto e' quella sbagliata"
        return httpx.Response(200, json=risposte)

    async with httpx.AsyncClient(transport=httpx.MockTransport(risposta)) as cliente:
        esito = await weather._meteo(cliente, 41.9, 12.49, "Casa", 1)
    assert esito["sole"] == {"alba": "06:41", "tramonto": "18:12"}


# ------------------------------------------------------------------ il prompt


def test_il_luogo_di_chi_parla_sta_nel_contesto_della_richiesta_non_nel_prompt_di_sistema():
    lingua = schemi("it")
    assert "Casa al mare" in get_contesto_della_richiesta(lingua, luogo="Casa al mare")
    assert "Chi parla si trova" not in get_contesto_della_richiesta(lingua)
    assert get_system_prompt(lingua) == get_system_prompt(lingua), "il prompt di sistema deve essere stabile"
    assert "Casa al mare" not in get_system_prompt(lingua)


def test_nel_prompt_mai_le_coordinate():
    contesto = get_contesto_della_richiesta(schemi("it"), luogo="Casa al mare")
    for cifra in ("44.12", "12.23"):
        assert cifra not in contesto


def test_l_agente_dice_il_nome_del_luogo_di_chi_parla():
    cache_stati.aggiorna(
        {
            "entity_id": "person.alessio",
            "state": "not_home",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "attributes": {"latitude": MARE[0], "longitude": MARE[1]},
        }
    )
    assert (
        ShinraAgent._luogo_di(UserProfile(id="u1", name="A", entita_posizione="person.alessio"))
        == "Casa al mare"
    )
    assert (
        ShinraAgent._luogo_di(UserProfile(id="u1", name="A")) == ""
    ), "senza posizione collegata non si dice niente"
    assert ShinraAgent._luogo_di(None) == ""


async def test_l_agente_mette_il_luogo_nel_contesto_della_richiesta(monkeypatch):
    """Il contesto che l'agente costruisce porta il luogo: se `process_user_input` smettesse di passarlo, qui si vede."""
    sorgente = __import__("inspect").getsource(ShinraAgent.process_user_input)
    assert "luogo=self._luogo_di(profile)" in sorgente
