"""Chiedere al dispositivo cosa sa fare, prima di chiederglielo.

`control_device` sapeva dire `set_temperature` al clima e `open`/`close` alle
tapparelle. Tutto il resto — modalita', ventola, umidita', posizione
intermedia, lamelle — non era esprimibile: «abbassa la tapparella a meta'» e
«metti il condizionatore in deumidificazione» non avevano un modo di
arrivare a Home Assistant.

Il difetto peggiore, pero', non era l'assenza: era cosa sarebbe successo
aggiungendo i comandi senza guardare le capacita'. Un termostato che non
deumidifica, a cui si manda `dry`, non risponde «non so farlo»: non fa
niente. La persona sente «fatto», va a dormire, e la mattina l'umidita' e'
la stessa. Per questo la meta' dei test qui sotto verifica dei **rifiuti**.

Nessun test tocca la rete: si verifica quale servizio chiediamo, con quali
parametri, e soprattutto quando non lo chiediamo affatto.

Riferimento: issue #21.
"""

from __future__ import annotations

import pytest

from shinra.domain import clima as clima_dominio
from shinra.domain import tapparelle as tapparelle_dominio
from shinra.skills import clima, tapparelle

# Un termostato completo, uno che sa solo scaldare, e un condizionatore che
# deumidifica come modalita' ma non imposta un'umidita' obiettivo: sono i tre
# casi veri che si trovano in una casa.
STATI = [
    {
        "entity_id": "climate.salotto",
        "state": "heat",
        "attributes": {
            "friendly_name": "Clima salotto",
            "hvac_modes": ["off", "heat", "cool", "heat_cool", "dry", "fan_only"],
            "fan_modes": ["auto", "low", "medium", "high"],
            "preset_modes": ["comfort", "eco", "sleep"],
            "min_temp": 16,
            "max_temp": 28,
            "supported_features": 1 | 4 | 8 | 16,
            "min_humidity": 30,
            "max_humidity": 70,
            "temperature": 21,
            "current_temperature": 19.5,
            "current_humidity": 55,
            "fan_mode": "auto",
        },
    },
    {
        "entity_id": "climate.caldaia",
        "state": "heat",
        "attributes": {
            "friendly_name": "Caldaia",
            "hvac_modes": ["off", "heat"],
            # Solo temperatura obiettivo: niente ventola, niente umidita'.
            "supported_features": 1,
            "min_temp": 5,
            "max_temp": 30,
            "temperature": 20,
        },
    },
    {
        "entity_id": "cover.salotto",
        "state": "open",
        "attributes": {
            "friendly_name": "Tapparella salotto",
            # apre, chiude, posiziona, ferma, lamelle
            "supported_features": 1 | 2 | 4 | 8 | 128,
            "current_position": 100,
            "current_tilt_position": 50,
        },
    },
    {
        "entity_id": "cover.garage",
        "state": "closed",
        "attributes": {
            "friendly_name": "Basculante garage",
            "supported_features": 1 | 2,  # solo apri e chiudi
        },
    },
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
    return chiamate, esito


# =============================================== i criteri della scheda


async def test_abbassa_la_tapparella_del_salotto_al_quaranta_per_cento(casa):
    """Primo criterio di accettazione, parola per parola."""
    chiamate, _ = casa

    esito = await tapparelle.comanda_tapparella("cover.salotto", "abbassa", posizione=40)

    assert esito["success"] is True
    assert chiamate == [("cover", "set_cover_position", {"entity_id": "cover.salotto", "position": 40})]


async def test_metti_il_clima_in_deumidificazione_al_cinquanta(casa):
    """Secondo criterio: due comandi, perche' in Home Assistant la modalita'
    e l'umidita' obiettivo sono due servizi distinti."""
    chiamate, _ = casa

    modo = await clima.comanda_clima("climate.salotto", "modalita", modalita="deumidificazione")
    grado = await clima.comanda_clima("climate.salotto", "umidita", umidita=50)

    assert modo["success"] and grado["success"]
    assert chiamate == [
        ("climate", "set_hvac_mode", {"entity_id": "climate.salotto", "hvac_mode": "dry"}),
        ("climate", "set_humidity", {"entity_id": "climate.salotto", "humidity": 50}),
    ]


async def test_a_che_temperatura_e_impostato_il_termostato(casa):
    """Terzo criterio. La risposta e' la temperatura OBIETTIVO: quella
    misurata in stanza e' un altro numero, e confonderle e' il modo piu'
    facile di rispondere con sicurezza una cosa sbagliata."""
    esito = await clima.stato_clima("climate.salotto")

    assert esito["success"] is True
    assert esito["temperatura_obiettivo"] == 21
    assert esito["temperatura_misurata"] == 19.5
    assert "21" in esito["message"]
    assert "19.5" in esito["message"]


# =============================================== i rifiuti


async def test_la_caldaia_non_deumidifica_e_lo_dice(casa):
    """Il difetto che questo test esiste per impedire: senza controllo la
    chiamata parte, Home Assistant risponde e non succede niente, e la
    persona crede che l'umidita' stia scendendo."""
    chiamate, _ = casa

    esito = await clima.comanda_clima("climate.caldaia", "modalita", modalita="deumidificazione")

    assert esito["success"] is False
    assert chiamate == []
    assert "non fa deumidificazione" in esito["error"]


async def test_il_rifiuto_dice_cosa_il_termostato_sa_fare(casa):
    """Un rifiuto che non dice l'alternativa costringe a indovinare."""
    esito = await clima.comanda_clima("climate.caldaia", "modalita", modalita="raffrescamento")

    assert "riscaldamento" in esito["message"]
    assert "spento" in esito["message"]
    assert esito["alternative"] == ["spento", "riscaldamento"]


async def test_la_caldaia_non_imposta_un_umidita_obiettivo(casa):
    """Deumidificare e' una modalita', impostare un'umidita' obiettivo e'
    un'altra cosa: molti condizionatori fanno la prima senza la seconda."""
    chiamate, _ = casa

    esito = await clima.comanda_clima("climate.caldaia", "umidita", umidita=50)

    assert esito["success"] is False
    assert chiamate == []


def test_sull_umidita_il_silenzio_vale_come_no():
    """L'opposto della regola sulle modalita', e per un motivo preciso: una
    modalita' negata a torto toglie una funzione che c'e', mentre
    `set_humidity` a un termostato che non la regola e' un errore secco di
    Home Assistant, e la persona si becca un guasto invece di una frase."""
    muto = clima_dominio.capacita({})
    dichiarante = clima_dominio.capacita({"supported_features": clima_dominio.REGOLA_UMIDITA})

    assert muto.regola_umidita is False
    assert dichiarante.regola_umidita is True


@pytest.mark.parametrize("richiesta,atteso", [(10, 30), (30, 30), (55, 55), (70, 70), (90, 70)])
def test_l_umidita_sta_dentro_i_limiti_dichiarati(richiesta, atteso):
    sapute = clima_dominio.capacita({"min_humidity": 30, "max_humidity": 70})

    assert clima_dominio.umidifica(richiesta, sapute) == atteso


async def test_il_garage_non_si_posiziona_a_meta(casa):
    """Un basculante che dichiara solo apri e chiudi: mandargli una
    posizione non lo porta a meta', non fa niente."""
    chiamate, _ = casa

    esito = await tapparelle.comanda_tapparella("cover.garage", "posizione", posizione=50)

    assert esito["success"] is False
    assert chiamate == []
    assert "non sa fermarsi a una posizione precisa" in esito["error"]


async def test_il_garage_non_ha_lamelle(casa):
    chiamate, _ = casa

    esito = await tapparelle.comanda_tapparella("cover.garage", "lamelle", lamelle=30)

    assert esito["success"] is False
    assert chiamate == []


async def test_il_garage_non_si_ferma_a_meta_corsa(casa):
    chiamate, _ = casa

    esito = await tapparelle.comanda_tapparella("cover.garage", "ferma")

    assert esito["success"] is False
    assert chiamate == []


async def test_una_ventola_inventata_non_parte(casa):
    """I nomi delle velocita' li decide l'integrazione: «turbo» e'
    plausibile, e su questo condizionatore non esiste."""
    chiamate, _ = casa

    esito = await clima.comanda_clima("climate.salotto", "ventola", ventola="turbo")

    assert esito["success"] is False
    assert chiamate == []
    assert "low" in esito["message"]


async def test_un_entita_inventata_non_raggiunge_home_assistant(casa):
    chiamate, _ = casa

    esito = await clima.comanda_clima("climate.inventato", "modalita", modalita="caldo")

    assert esito["success"] is False
    assert chiamate == []


# =============================================== il verso della percentuale


@pytest.mark.parametrize(
    "azione,argomenti,atteso",
    [
        ("apri", {}, ("open_cover", {})),
        ("chiudi", {}, ("close_cover", {})),
        ("ferma", {}, ("stop_cover", {})),
        ("posizione", {"posizione": 0}, ("set_cover_position", {"position": 0})),
        ("posizione", {"posizione": 100}, ("set_cover_position", {"position": 100})),
        ("lamelle", {"lamelle": 30}, ("set_cover_tilt_position", {"tilt_position": 30})),
    ],
)
async def test_ogni_azione_chiama_il_servizio_giusto(casa, azione, argomenti, atteso):
    chiamate, _ = casa
    servizio, dati = atteso

    await tapparelle.comanda_tapparella("cover.salotto", azione, **argomenti)

    assert chiamate == [("cover", servizio, {"entity_id": "cover.salotto", **dati})]


async def test_aprire_a_una_percentuale_non_spalanca(casa):
    """«Aprila al 30» e' una posizione, non un'apertura: chi lo dice vuole
    fermarsi al 30, e `open_cover` la porterebbe a 100."""
    chiamate, _ = casa

    await tapparelle.comanda_tapparella("cover.salotto", "apri", posizione=30)

    assert chiamate[0][1] == "set_cover_position"
    assert chiamate[0][2]["position"] == 30


@pytest.mark.parametrize("richiesta,atteso", [(-20, 0), (0, 0), (55, 55), (100, 100), (140, 100)])
def test_la_percentuale_sta_dentro_i_limiti(richiesta, atteso):
    sapute = tapparelle_dominio.capacita({"supported_features": 4})

    assert tapparelle_dominio.posiziona(richiesta, sapute) == atteso


def test_cento_e_aperta_zero_e_chiusa():
    """Il verso che si sbaglia piu' spesso, scritto come test perche' un
    commento non fallisce."""
    assert tapparelle_dominio.riassumi("open", {"current_position": 0}) == "chiusa"
    assert tapparelle_dominio.riassumi("open", {"current_position": 100}).startswith("aperta del tutto")
    assert "40 per cento" in tapparelle_dominio.riassumi("open", {"current_position": 40})


def test_una_tapparella_al_cinque_per_cento_non_e_una_spalancata():
    """Per Home Assistant sono tutte e due `open`, e in casa non sono
    affatto la stessa cosa."""
    poco = tapparelle_dominio.riassumi("open", {"current_position": 5})
    tanto = tapparelle_dominio.riassumi("open", {"current_position": 95})

    assert poco != tanto


def test_senza_posizione_si_dice_solo_aperta_o_chiusa():
    assert tapparelle_dominio.riassumi("closed", {}) == "chiusa"
    assert tapparelle_dominio.riassumi("open", {}) == "aperta"


def test_un_motore_che_non_dichiara_niente_si_prova_lo_stesso():
    """Un'integrazione muta non e' un'integrazione incapace: rifiutare a
    priori toglierebbe la funzione a chi ha un motore vecchio ma
    funzionante."""
    sapute = tapparelle_dominio.capacita({})

    assert sapute.sa_posizionarsi and sapute.sa_fermarsi and sapute.sa_orientare_lamelle


# =============================================== le parole del clima


@pytest.mark.parametrize(
    "detto,atteso",
    [
        ("deumidificazione", "dry"),
        ("deumidifica", "dry"),
        ("secco", "dry"),
        ("riscaldamento", "heat"),
        ("caldo", "heat"),
        ("freddo", "cool"),
        ("aria condizionata", "cool"),
        ("raffrescamento", "cool"),
        ("ventilazione", "fan_only"),
        ("automatico", "heat_cool"),
        ("spento", "off"),
        ("cool", "cool"),
        ("HEAT", "heat"),
        ("mettilo in aria condizionata per favore", "cool"),
    ],
)
def test_le_parole_con_cui_una_persona_chiede_una_modalita(detto, atteso):
    assert clima_dominio.modalita_dalle_parole(detto) == atteso


def test_una_parola_che_non_e_una_modalita():
    assert clima_dominio.modalita_dalle_parole("tiepido come piace a me") is None
    assert clima_dominio.modalita_dalle_parole("") is None


def test_auto_e_heat_cool_sono_la_stessa_idea_con_due_nomi():
    """Le integrazioni ne dichiarano una o l'altra, e chi chiede
    «automatico» non deve sapere quale."""
    solo_auto = clima_dominio.capacita({"hvac_modes": ["off", "auto"]})

    assert clima_dominio.scegli_modalita("automatico", solo_auto) == "auto"

    solo_heat_cool = clima_dominio.capacita({"hvac_modes": ["off", "heat_cool"]})

    assert clima_dominio.scegli_modalita("automatico", solo_heat_cool) == "heat_cool"


def test_un_termostato_muto_si_prova_lo_stesso():
    senza = clima_dominio.capacita({})

    assert clima_dominio.scegli_modalita("deumidificazione", senza) == "dry"


@pytest.mark.parametrize("richiesta,atteso", [(2, 16.0), (16, 16.0), (22, 22.0), (28, 28.0), (35, 28.0)])
def test_la_temperatura_si_accorcia_invece_di_essere_rifiutata(richiesta, atteso):
    """Chi dice «mettilo a 30» con un termostato che arriva a 28 vuole il
    massimo, non un errore."""
    sapute = clima_dominio.capacita({"min_temp": 16, "max_temp": 28})

    assert clima_dominio.tempera(richiesta, sapute) == atteso


async def test_quando_la_temperatura_viene_accorciata_si_dice(casa):
    """Chi ha chiesto trenta gradi e sente «fatto» crede di averne trenta."""
    chiamate, _ = casa

    esito = await clima.comanda_clima("climate.salotto", "temperatura", temperatura=30)

    assert esito["success"] is True
    assert chiamate[0][2]["temperature"] == 28
    assert "massimo" in esito["message"]


async def test_quando_non_viene_accorciata_non_si_dice_niente(casa):
    esito = await clima.comanda_clima("climate.salotto", "temperatura", temperatura=22)

    assert "massimo" not in esito["message"]


def test_min_e_max_scambiati_non_rompono_niente():
    sapute = clima_dominio.capacita({"min_temp": 30, "max_temp": 10})

    assert sapute.temperatura_minima == 10.0
    assert clima_dominio.tempera(20, sapute) == 20.0


async def test_accendere_senza_dire_come_non_lo_mette_su_spento(casa):
    """`off` e' la prima modalita' dichiarata da quasi tutti: sceglierla
    sarebbe una risposta soddisfatta a una richiesta non eseguita."""
    chiamate, _ = casa

    await clima.comanda_clima("climate.salotto", "accendi")

    assert chiamate[0][2]["hvac_mode"] != "off"


async def test_la_ventola_si_riconosce_senza_badare_alle_maiuscole(casa):
    chiamate, _ = casa

    await clima.comanda_clima("climate.salotto", "ventola", ventola="MEDIUM")

    assert chiamate[0][2]["fan_mode"] == "medium"


def test_il_riassunto_distingue_impostata_da_misurata():
    frase = clima_dominio.riassumi("heat", {"temperature": 21, "current_temperature": 19.5})

    assert "impostato a 21" in frase
    assert "in stanza ce ne sono 19.5" in frase


def test_un_preset_a_none_non_finisce_nella_frase():
    """Home Assistant scrive `none` come stringa quando non c'e' preset."""
    assert "none" not in clima_dominio.riassumi("heat", {"preset_mode": "none"})
