"""«Dove sono?» in chat (#343) e il meteo per dove ci si trova (#344).

Contano due cose: la frase scatta **solo** se e' proprio quella («dove sono le chiavi?» e' un'altra domanda), e la risposta
e' il nome del luogo, mai le coordinate.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shinra.infra.db.luoghi import luoghi as deposito
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services import luoghi
from shinra.services.intenti import informazioni as modulo
from shinra.services.intenti import instrada
from shinra.services.intenti.base import Richiesta
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile

CASA = (41.902784, 12.496366)
UFFICIO = (45.464200, 9.190000)


@pytest.fixture(autouse=True)
def luoghi_e_stati():
    deposito.sostituisci_tutto([])
    cache_stati.svuota()
    luoghi.registra({"nome": "Casa", "latitudine": CASA[0], "longitudine": CASA[1], "origine": "telefono"})
    luoghi.registra(
        {"nome": "Ufficio", "latitudine": UFFICIO[0], "longitudine": UFFICIO[1], "origine": "telefono"}
    )
    yield
    deposito.sostituisci_tutto([])
    cache_stati.svuota()


def persona(lat, lon):
    cache_stati.aggiorna(
        {
            "entity_id": "person.alessio",
            "state": "home",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "attributes": {"latitude": lat, "longitude": lon},
        }
    )


def chiedi(testo: str, collegata: bool = True, lingua: str = ""):
    profilo = UserProfile(
        id="u1", name="Alessio", lingua=lingua, entita_posizione="person.alessio" if collegata else ""
    )
    return Richiesta(testo=testo, profilo=profilo, memoria=ConversationMemory())


@pytest.mark.parametrize(
    "frase",
    [
        "dove sono?",
        "Dove sono",
        "dove mi trovo adesso?",
        "dimmi dove sono",
        "in che luogo sono?",
        "ma dove sono ora",
    ],
)
async def test_le_frasi_che_chiedono_dove_si_e_scattano(frase):
    persona(*UFFICIO)
    risposta = await instrada(chiedi(frase))
    assert risposta is not None and risposta.testo == "Sei a Ufficio."


@pytest.mark.parametrize(
    "frase",
    ["dove sono le chiavi?", "dove sono i bambini", "dove sono le mie cose", "dove sono finiti i soldi"],
)
async def test_un_altra_domanda_con_le_stesse_parole_non_scatta(frase):
    persona(*UFFICIO)
    risposta = await instrada(chiedi(frase))
    assert risposta is None or "Sei a" not in risposta.testo


async def test_in_inglese_risponde_in_inglese():
    persona(*CASA)
    assert (await instrada(chiedi("where am I?", lingua="en"))).testo == "You are at Casa."
    risposta = await instrada(chiedi("where are my keys?", lingua="en"))
    assert risposta is None or "You are at" not in risposta.testo


async def test_senza_la_posizione_collegata_spiega_come_si_fa():
    persona(*CASA)
    risposta = await instrada(chiedi("dove sono?", collegata=False))
    assert "non è collegata" in risposta.testo and "Impostazioni" in risposta.testo
    assert "Casa" not in risposta.testo, "ha detto un luogo a chi non ha acceso la posizione"


async def test_fuori_da_ogni_luogo_dice_che_si_e_in_giro():
    persona(44.0, 10.5)
    assert "in giro" in (await instrada(chiedi("dove sono?"))).testo


async def test_senza_una_posizione_da_home_assistant_dice_che_non_lo_sa():
    risposta = await instrada(chiedi("dove sono?"))
    assert "Non so dove sei" in risposta.testo and "non conosce" in risposta.testo


async def test_la_risposta_non_contiene_coordinate():
    persona(*CASA)
    risposta = await instrada(chiedi("dove sono?"))
    for cifra in ("41.9", "12.49", "45.46", "9.19"):
        assert cifra not in risposta.testo


# ---------------------------------------------------------- il meteo per dove ci si trova


@pytest.fixture
def meteo(monkeypatch):
    chiamate: list[str] = []

    async def di_un_luogo(nome, latitudine, longitudine, days=2):
        chiamate.append(nome)
        return {
            "success": True,
            "localita": nome,
            "adesso": {"temperatura": "18°C", "condizione": "Sereno"},
            "previsioni": [{"temp_max": 20, "temp_min": 12}],
        }

    monkeypatch.setattr(modulo, "meteo_di_un_luogo", di_un_luogo)
    return chiamate


async def test_il_meteo_e_per_il_luogo_in_cui_si_e(meteo):
    persona(*UFFICIO)
    await instrada(chiedi("che tempo fa oggi"))
    assert meteo == ["Ufficio"]


async def test_il_luogo_nominato_vince_su_quello_in_cui_si_e(meteo):
    persona(*UFFICIO)
    await instrada(chiedi("che tempo fa a casa"))
    assert meteo == ["Casa"]


async def test_in_giro_il_meteo_e_per_la_casa_principale(meteo):
    persona(44.0, 10.5)
    await instrada(chiedi("che tempo fa oggi"))
    assert meteo == ["Casa"]


async def test_senza_posizione_collegata_il_meteo_e_per_la_casa_principale(meteo):
    persona(*UFFICIO)
    await instrada(chiedi("che tempo fa oggi", collegata=False))
    assert meteo == ["Casa"], "ha usato la posizione di chi non l'ha acceso"


# ------------------------------------------------------- dire perche' non si sa


async def test_in_giro_dice_il_luogo_piu_vicino_e_a_quanto():
    persona(UFFICIO[0] + 0.0275, UFFICIO[1])  # ~3,1 km a nord dell'ufficio
    testo = (await instrada(chiedi("dove sono?"))).testo
    assert "Ufficio" in testo and "3,1 km" in testo, testo
    assert "registrato nel punto sbagliato" in testo


async def test_in_inglese_la_distanza_ha_il_punto():
    persona(UFFICIO[0] + 0.0275, UFFICIO[1])
    testo = (await instrada(chiedi("where am I?", lingua="en"))).testo
    assert "3.1 km" in testo and "wrong spot" in testo


async def test_ogni_motivo_del_non_so_ha_la_sua_frase():
    senza = (await instrada(chiedi("dove sono?"))).testo
    assert "non conosce «person.alessio»" in senza and "telefono giusto" in senza

    cache_stati.aggiorna({"entity_id": "person.alessio", "state": "home", "attributes": {}})
    assert "latitudine e longitudine" in (await instrada(chiedi("dove sono?"))).testo

    cache_stati.aggiorna(
        {
            "entity_id": "person.alessio",
            "state": "home",
            "last_updated": datetime.fromtimestamp(0, tz=timezone.utc).isoformat(),
            "attributes": {"latitude": 1.0, "longitude": 2.0},
        }
    )
    assert "ore fa" in (await instrada(chiedi("dove sono?"))).testo
