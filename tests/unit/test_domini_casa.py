"""I quattro domini che si vedevano e non rispondevano.

`lock`, `media_player`, `vacuum` e `fan` erano elencati come comandabili
nella mappa dispositivi, e nessun tool sapeva toccarli. E' il difetto che
erode la fiducia piu' di un errore esplicito, perche' non ha nemmeno un
messaggio da leggere: si chiede, e non succede niente.

Nessun test qui tocca la rete. Cio' che si verifica e' **quale servizio
chiediamo a Home Assistant e con quali parametri** — la parte che si
sbaglia — e soprattutto cosa *non* chiediamo: un `entity_id` inventato dal
modello non deve mai partire.

Riferimento: issue #20, ADR 0004.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.skills import domini_casa, entita

STATI = [
    {
        "entity_id": "lock.porta_ingresso",
        "state": "locked",
        "attributes": {"friendly_name": "Porta d'ingresso"},
    },
    {"entity_id": "media_player.salotto", "state": "playing", "attributes": {"friendly_name": "TV salotto"}},
    {"entity_id": "vacuum.robot", "state": "docked", "attributes": {"friendly_name": "Robottino"}},
    {"entity_id": "fan.camera", "state": "off", "attributes": {"friendly_name": "Ventilatore camera"}},
    {"entity_id": "light.cucina", "state": "on", "attributes": {"friendly_name": "Luce cucina"}},
]


@pytest.fixture
def casa(monkeypatch):
    """Home Assistant che annota invece di eseguire."""
    chiamate: list[tuple[str, str, dict]] = []
    esito = {"success": True}

    class FintoClient:
        async def call_service(self, dominio, servizio, dati=None):
            chiamate.append((dominio, servizio, dati or {}))
            return dict(esito)

        async def stati_correnti(self):
            return list(STATI)

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    # Un alias vero, per provare anche la strada dal nome parlato.
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "porta d'ingresso", "entity_id": "lock.porta_ingresso"}]
    )
    domini_casa.azzera_conferme()
    yield chiamate, esito
    domini_casa.azzera_conferme()


@pytest.fixture
def da_web(monkeypatch):
    """Il contesto di una richiesta che arriva dalla dashboard."""
    from shinra.services import registro

    registro.apri_contesto(attore="alessio", canale="web")
    yield


# ------------------------------------------- l'entita' inventata dal modello


async def test_un_dispositivo_inesistente_non_raggiunge_home_assistant(casa):
    """Il modello inventa `lock.porta_ingresso_principale` perche' e' un nome
    plausibile. Senza controllo la richiesta parte, Home Assistant risponde
    200 e non fa niente, e l'assistente annuncia che la porta e' chiusa
    mentre e' spalancata."""
    chiamate, _ = casa

    esito = await domini_casa.comanda_serratura("lock.inventata", "blocca")

    assert esito["success"] is False
    assert chiamate == []
    assert "Non conosco" in esito["error"]


async def test_l_errore_propone_l_alternativa_giusta(casa):
    esito = await domini_casa.comanda_media("media_player.salotto_tv", "pausa")

    assert esito["success"] is False
    assert "media_player.salotto" in esito["error"]


async def test_il_dominio_sbagliato_e_un_errore_non_un_comando(casa):
    """Mettere in pausa una luce non e' una richiesta da eseguire."""
    chiamate, _ = casa

    esito = await domini_casa.comanda_media("light.cucina", "pausa")

    assert esito["success"] is False
    assert chiamate == []
    assert "light" in esito["error"]


async def test_se_la_casa_non_risponde_il_comando_passa_lo_stesso(monkeypatch):
    """Un controllo che trasforma «non lo so» in «non esiste» impedirebbe di
    comandare la casa proprio quando e' gia' in difficolta'."""

    async def nessuno_stato():
        return []

    monkeypatch.setattr(entita, "stati_noti", nessuno_stato)
    # Un alias vero, per provare anche la strada dal nome parlato.
    depositi.alias.sostituisci_tutto(
        [{"id": "a1", "alias": "porta d'ingresso", "entity_id": "lock.porta_ingresso"}]
    )

    assert await entita.verifica("fan.camera", {"fan"}) == "fan.camera"


# ----------------------------------------------------------- le serrature


async def test_chiudere_una_serratura_non_chiede_conferma(casa, da_web):
    """Chiudere e' l'azione sicura: e' aprire che merita un attrito.

    Passa anche dal nome parlato: «porta d'ingresso» e' un alias, e la
    risoluzione deve avvenire prima della verifica — altrimenti il controllo
    boccerebbe ogni nome che non sia gia' un `entity_id`.
    """
    chiamate, _ = casa

    esito = await domini_casa.comanda_serratura("porta d'ingresso", "blocca")

    assert esito["success"] is True
    assert chiamate == [("lock", "lock", {"entity_id": "lock.porta_ingresso"})]


async def test_il_primo_sblocco_chiede_conferma_e_non_apre(casa, da_web):
    chiamate, _ = casa

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    assert esito["success"] is False
    assert esito["conferma_richiesta"] is True
    assert chiamate == [], "la porta non deve essersi aperta"


async def test_la_seconda_richiesta_entro_un_minuto_apre(casa, da_web):
    chiamate, _ = casa
    await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    assert esito["success"] is True
    assert chiamate == [("lock", "unlock", {"entity_id": "lock.porta_ingresso"})]


async def test_la_conferma_scade(casa, da_web, monkeypatch):
    """Un «si'» detto piu' tardi, per altro, non deve aprire la porta."""
    chiamate, _ = casa
    adesso = [1000.0]
    monkeypatch.setattr(domini_casa.time, "monotonic", lambda: adesso[0])

    await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")
    adesso[0] += domini_casa.ATTESA_CONFERMA + 1

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    assert esito["success"] is False
    assert esito["conferma_richiesta"] is True
    assert chiamate == []


async def test_chiudere_annulla_una_conferma_in_sospeso(casa, da_web):
    """Altrimenti «chiudi... anzi apri» aprirebbe senza chiedere niente."""
    chiamate, _ = casa
    await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")
    await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    assert esito["conferma_richiesta"] is True
    assert ("lock", "unlock", {"entity_id": "lock.porta_ingresso"}) not in chiamate


async def test_dalla_voce_non_si_apre(casa):
    """L'ADR 0004: il canale vocale non distingue chi parla.

    Chiunque si rivolga a un Echo agisce con l'identita' della sessione
    aperta — un ospite, o qualcuno che parla da fuori una finestra, userebbe
    i permessi del padrone di casa. Fino ai profili vocali della v0.4.0, da
    li' si puo' solo chiudere.
    """
    from shinra.services import registro

    chiamate, _ = casa
    registro.apri_contesto(attore="alessio", canale="alexa")

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "sblocca")

    assert esito["success"] is False
    assert chiamate == []
    assert "voce" in esito["error"].lower()


async def test_dalla_voce_si_chiude_eccome(casa):
    from shinra.services import registro

    chiamate, _ = casa
    registro.apri_contesto(attore="alessio", canale="alexa")

    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "blocca")

    assert esito["success"] is True
    assert chiamate == [("lock", "lock", {"entity_id": "lock.porta_ingresso"})]


async def test_lo_stato_di_una_serratura_si_dice_in_italiano(casa, da_web):
    esito = await domini_casa.comanda_serratura("lock.porta_ingresso", "stato")

    assert esito["success"] is True
    assert "chiusa" in esito["message"]


# --------------------------------------------------------- media player


@pytest.mark.parametrize(
    ("azione", "servizio"),
    [
        ("riproduci", "media_play"),
        ("pausa", "media_pause"),
        ("successiva", "media_next_track"),
        ("precedente", "media_previous_track"),
        ("spegni", "turn_off"),
    ],
)
async def test_le_azioni_del_media_player(casa, azione, servizio):
    chiamate, _ = casa

    await domini_casa.comanda_media("media_player.salotto", azione)

    assert chiamate == [("media_player", servizio, {"entity_id": "media_player.salotto"})]


async def test_il_volume_si_dice_in_percentuale_e_si_manda_in_frazione(casa):
    """Le persone dicono «volume al quaranta», Home Assistant vuole 0.4."""
    chiamate, _ = casa

    await domini_casa.comanda_media("media_player.salotto", "volume", volume=40)

    assert chiamate == [
        ("media_player", "volume_set", {"entity_id": "media_player.salotto", "volume_level": 0.4})
    ]


async def test_un_volume_fuori_scala_viene_riportato_dentro(casa):
    chiamate, _ = casa

    await domini_casa.comanda_media("media_player.salotto", "volume", volume=350)

    assert chiamate[0][2]["volume_level"] == 1.0


async def test_il_volume_senza_valore_non_manda_niente(casa):
    chiamate, _ = casa

    esito = await domini_casa.comanda_media("media_player.salotto", "volume")

    assert esito["success"] is False
    assert chiamate == []


# --------------------------------------------------------- aspirapolvere


@pytest.mark.parametrize(
    ("azione", "servizio"),
    [("avvia", "start"), ("ferma", "pause"), ("rientra", "return_to_base"), ("spegni", "stop")],
)
async def test_le_azioni_dell_aspirapolvere(casa, azione, servizio):
    chiamate, _ = casa

    await domini_casa.comanda_aspirapolvere("vacuum.robot", azione)

    assert chiamate == [("vacuum", servizio, {"entity_id": "vacuum.robot"})]


async def test_pulire_una_stanza_manda_il_comando_di_segmento(casa):
    chiamate, _ = casa

    await domini_casa.comanda_aspirapolvere("vacuum.robot", "avvia", stanza="cucina")

    dominio, servizio, dati = chiamate[0]
    assert (dominio, servizio) == ("vacuum", "send_command")
    assert dati["params"] == ["cucina"]


async def test_se_il_robot_non_sa_pulire_a_stanze_lo_si_dice(casa):
    _, esito_finto = casa
    esito_finto["success"] = False

    esito = await domini_casa.comanda_aspirapolvere("vacuum.robot", "avvia", stanza="cucina")

    assert esito["success"] is False
    assert "stanze" in esito["error"]


# ---------------------------------------------------------- ventilatori


async def test_accendere_un_ventilatore_con_la_velocita(casa):
    chiamate, _ = casa

    await domini_casa.comanda_ventilatore("fan.camera", "accendi", velocita=60)

    assert chiamate == [("fan", "turn_on", {"entity_id": "fan.camera", "percentage": 60})]


async def test_l_oscillazione_si_accende_per_difetto(casa):
    chiamate, _ = casa

    await domini_casa.comanda_ventilatore("fan.camera", "oscilla")

    assert chiamate == [("fan", "oscillate", {"entity_id": "fan.camera", "oscillating": True})]


async def test_l_oscillazione_si_puo_spegnere(casa):
    chiamate, _ = casa

    await domini_casa.comanda_ventilatore("fan.camera", "oscilla", oscillazione=False)

    assert chiamate[0][2]["oscillating"] is False


async def test_un_azione_inventata_non_diventa_un_servizio(casa):
    """Il modello propone «turbo» e non deve finire in una chiamata a caso."""
    chiamate, _ = casa

    esito = await domini_casa.comanda_ventilatore("fan.camera", "turbo")

    assert esito["success"] is False
    assert chiamate == []


# ------------------------------------------------------- il registro


def test_ogni_schema_ha_il_suo_gestore():
    """Uno schema senza gestore e' un tool che il modello prova a chiamare e
    che non esiste: l'errore arriva a fine giro, dopo aver fatto sperare."""
    from shinra.skills.registry import TOOL_HANDLERS, TOOLS_SCHEMA

    nomi = {s["function"]["name"] for s in TOOLS_SCHEMA}

    assert sorted(nomi - set(TOOL_HANDLERS)) == []


@pytest.mark.parametrize(
    "nome",
    ["comanda_serratura", "comanda_media", "comanda_aspirapolvere", "comanda_ventilatore"],
)
def test_i_quattro_domini_sono_raggiungibili_dal_modello(nome):
    """Erano visibili nell'interfaccia e comandabili da nessuno."""
    from shinra.skills.registry import TOOL_HANDLERS, TOOLS_SCHEMA

    assert nome in TOOL_HANDLERS
    assert nome in {s["function"]["name"] for s in TOOLS_SCHEMA}
