"""I tool dell'energia, e la cosa che devono rifiutarsi di fare.

Il criterio di accettazione della scheda che vale piu' degli altri: **senza
sensori di energia il sistema lo dice, invece di inventare un numero.** La
strada facile — rispondere zero — e' anche la peggiore, perche' chi chiede
quanto ha consumato e sente «zero» crede di non aver consumato niente. Meta'
di questi test verificano quel rifiuto.

L'altra meta' verifica il campionamento: i contatori di Home Assistant
salgono e non si azzerano mai, tranne quando si azzerano, e un sensore
`unavailable` non e' un contatore a zero.

Riferimento: issue #24.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shinra.config.settings import settings
from shinra.domain import energia as dominio
from shinra.domain import fasce
from shinra.infra.db import depositi
from shinra.services import energia as servizio_modulo
from shinra.skills import energia

STATI = [
    {
        "entity_id": "sensor.casa_energia",
        "state": "1234.5",
        "attributes": {
            "friendly_name": "Energia totale",
            "device_class": "energy",
            "state_class": "total_increasing",
            "unit_of_measurement": "kWh",
        },
    },
    {
        "entity_id": "sensor.lavatrice_energia",
        "state": "88.0",
        "attributes": {
            "friendly_name": "Energia lavatrice",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    },
    {
        "entity_id": "sensor.frigo_potenza",
        "state": "120",
        "attributes": {"friendly_name": "Frigorifero", "device_class": "power"},
    },
    {
        "entity_id": "sensor.temperatura_salotto",
        "state": "21.5",
        "attributes": {"device_class": "temperature"},
    },
    {
        "entity_id": "light.salotto",
        "state": "on",
        "attributes": {"friendly_name": "Luce salotto"},
    },
]


@pytest.fixture
def casa(monkeypatch):
    class FintoClient:
        async def call_service(self, dominio_ha, servizio, dati=None):
            return {"success": True}

        async def stati_correnti(self):
            return list(STATI)

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: FintoClient())
    return STATI


@pytest.fixture
def tariffa_fissa(monkeypatch):
    """Una bioraria dichiarata, per non dipendere dalle stime."""
    monkeypatch.setattr(settings.energia, "tipo", "bioraria")
    monkeypatch.setattr(settings.energia, "prezzo_punta", 0.35)
    monkeypatch.setattr(settings.energia, "prezzo_fuori_punta", 0.20)
    return settings.energia


# ============================================ riconoscere i sensori giusti


def test_i_contatori_di_energia_non_sono_le_potenze_istantanee(casa):
    """Un sensore `power` dice quanti watt assorbe adesso, un sensore
    `energy` quanti kilowattora ha totalizzato. Sommare i primi darebbe un
    numero senza significato."""
    assert energia.sensori_energia(STATI) == [
        "sensor.casa_energia",
        "sensor.lavatrice_energia",
    ]
    assert energia.sensori_potenza(STATI) == ["sensor.frigo_potenza"]


def test_una_temperatura_non_e_energia(casa):
    assert "sensor.temperatura_salotto" not in energia.sensori_energia(STATI)


def test_un_sensore_di_energia_a_misura_istantanea_non_e_un_contatore():
    """`measurement` su una device_class `energy` esiste e non e' cumulativo:
    sommarlo darebbe un totale inventato."""
    strani = [
        {
            "entity_id": "sensor.strano",
            "state": "3",
            "attributes": {"device_class": "energy", "state_class": "measurement"},
        }
    ]

    assert energia.sensori_energia(strani) == []


# ============================================ il criterio: non inventare


async def test_senza_letture_lo_dice_invece_di_rispondere_zero(casa):
    """Il criterio di accettazione della scheda. Rispondere «zero
    kilowattora» a chi non ha ancora sensori e' il modo piu' rapido per far
    perdere fiducia a un conto in bolletta."""
    esito = await energia.consumo_energia("oggi")

    assert esito["success"] is False
    assert "kwh" not in esito
    assert "non ho ancora letture" in esito["error"].lower()


async def test_il_rifiuto_spiega_anche_perche_potrebbe_essere_presto(casa):
    """Il primo consumo si sa dopo due letture: chi ha appena installato non
    deve credere che sia rotto."""
    esito = await energia.consumo_energia("oggi")

    assert "dopo un'ora" in esito["error"]


async def test_con_letture_di_altri_sensori_il_rifiuto_dice_quali(casa):
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 1.0, fasce.F1)

    esito = await energia.consumo_energia("oggi", entity_id="sensor.inesistente")

    assert esito["success"] is False
    assert "sensor.casa_energia" in esito["error"]


async def test_letture_senza_consumo_non_sono_un_errore(casa):
    """Contatori fermi sono un fatto, non un'assenza di dati: la casa non ha
    consumato. E' l'unico caso in cui «zero» e' la risposta giusta."""
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 0.0, fasce.F1)
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 0.0, fasce.F1)

    esito = await energia.consumo_energia("oggi")

    assert esito["success"] is True
    assert esito["kwh"] == 0.0
    assert "nessun consumo" in esito["message"]


async def test_senza_sensore_di_potenza_non_si_stima_il_costo(casa):
    """«Quanto mi costa tenere accesa la luce del salotto» non ha risposta se
    nessuno misura quanto assorbe. Inventarne una sarebbe peggio."""
    esito = await energia.costo_dispositivo("light.salotto")

    assert esito["success"] is False
    assert "non misura la potenza" in esito["error"]
    assert "sensor.frigo_potenza" in esito["error"]


async def test_un_dispositivo_che_non_esiste(casa):
    esito = await energia.costo_dispositivo("sensor.inventato")

    assert esito["success"] is False


# ============================================ le risposte vere


async def test_quanto_ho_consumato_oggi(casa, tariffa_fissa):
    """Il criterio della scheda: kilowattora e costo stimato."""
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 2.0, fasce.F1)
    depositi.letture_energia.registra("sensor.casa_energia", 102.0, 3.0, fasce.F3)

    esito = await energia.consumo_energia("oggi")

    assert esito["success"] is True
    assert esito["kwh"] == 5.0
    assert esito["costo"] == round(2 * 0.35 + 3 * 0.20, 2)
    assert esito["stimato"] is False


async def test_il_consumo_e_diviso_per_fascia(casa, tariffa_fissa):
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 2.0, fasce.F1)
    depositi.letture_energia.registra("sensor.casa_energia", 102.0, 3.0, fasce.F3)

    esito = await energia.consumo_energia("oggi")

    assert esito["per_fascia"][fasce.F1] == 2.0
    assert esito["per_fascia"][fasce.F3] == 3.0


async def test_senza_tariffa_configurata_il_costo_si_dichiara_stimato(casa, monkeypatch):
    """Un ordine di grandezza spacciato per un conto in bolletta e' peggio di
    nessun conto."""
    monkeypatch.setattr(settings.energia, "tipo", "monoraria")
    monkeypatch.setattr(settings.energia, "prezzo_kwh", 0.0)
    monkeypatch.setattr(settings.energia, "prezzo_punta", 0.0)
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 2.0, fasce.F1)
    depositi.letture_energia.registra("sensor.casa_energia", 102.0, 1.0, fasce.F1)

    esito = await energia.consumo_energia("oggi")

    assert esito["stimato"] is True
    assert "stima" in esito["message"]


async def test_lo_storico_si_interroga_per_periodo(casa, tariffa_fissa):
    """Il criterio della scheda: giorno, settimana e mese."""
    adesso = datetime.now(timezone.utc)
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 1.0, fasce.F1, adesso)
    depositi.letture_energia.registra("sensor.casa_energia", 90.0, 9.0, fasce.F1, adesso - timedelta(days=10))

    oggi = await energia.consumo_energia("oggi")
    mese = await energia.consumo_energia("mese")

    assert oggi["kwh"] == 1.0
    assert mese["kwh"] == 10.0


async def test_una_lettura_dell_ultimo_istante_rientra_in_oggi(casa, tariffa_fissa, monkeypatch):
    """Il difetto della issue #101, in forma deterministica.

    L'estremo superiore di «oggi» era l'istante della domanda, e il filtro
    usa il minore stretto: una lettura con `momento` uguale a quell'istante
    spariva. Capitava per davvero — lo scheduler campiona i contatori e
    qualcuno chiede «quanto ho consumato oggi» — ma si vedeva solo dove
    l'orologio e' grosso abbastanza da restituire due volte lo stesso valore.

    Qui l'orologio e' fermo per costruzione, cosi' il caso peggiore e'
    l'unico caso: le due letture portano *lo stesso* istante che la domanda
    leggera' come «adesso».
    """
    fermo = datetime.now(timezone.utc)

    class OrologioFermo:
        @staticmethod
        def now(tz=None):
            return fermo.astimezone(tz) if tz else fermo

    monkeypatch.setattr(energia, "datetime", OrologioFermo)
    depositi.letture_energia.registra("sensor.casa_energia", 100.0, 2.0, fasce.F1, fermo)
    depositi.letture_energia.registra("sensor.casa_energia", 102.0, 3.0, fasce.F3, fermo)

    esito = await energia.consumo_energia("oggi")

    assert esito["success"] is True
    assert esito["kwh"] == 5.0, "una lettura dell'ultimo istante non deve sparire"


def test_ogni_periodo_si_chiude_su_una_mezzanotte():
    """La regola che rende impossibile il difetto, non solo improbabile.

    Finche' un estremo superiore e' «adesso», qualunque lettura registrata
    nello stesso tick e' a rischio; con una mezzanotte, nessuna lo e'.
    """
    for periodo in ("oggi", "ieri", "settimana", "mese"):
        _, a, _ = energia._intervallo(periodo)
        locale = a.astimezone(fasce.FUSO)
        assert (locale.hour, locale.minute, locale.second, locale.microsecond) == (
            0,
            0,
            0,
            0,
        ), f"«{periodo}» si chiude alle {locale.time()}, non a mezzanotte"


def test_oggi_comincia_e_finisce_dove_deve():
    """Da questa mezzanotte alla prossima.

    Il confronto e' fra date e non fra durate: nei due giorni all'anno in cui
    cambia l'ora, una giornata italiana dura ventitre' o venticinque ore, e
    un test che pretendesse esattamente ventiquattro sarebbe rosso il giorno
    sbagliato.
    """
    da, a, _ = energia._intervallo("oggi")
    inizio = da.astimezone(fasce.FUSO)
    fine = a.astimezone(fasce.FUSO)
    oggi = datetime.now(fasce.FUSO).date()

    assert inizio.date() == oggi
    assert fine.date() == oggi + timedelta(days=1)


async def test_quanto_mi_costa_tenere_acceso_questo(casa, tariffa_fissa):
    """120 watt per un'ora sono 0,12 kWh."""
    esito = await energia.costo_dispositivo("sensor.frigo_potenza")

    assert esito["success"] is True
    assert esito["watt"] == 120
    assert esito["costo_orario"] == round(0.12 * energia.tariffa_configurata().prezzo(esito["fascia"]), 3)


async def test_in_che_fascia_siamo_adesso(casa):
    esito = await energia.fascia_corrente()

    assert esito["success"] is True
    assert esito["fascia"] in fasce.FASCE
    assert esito["prossima"] != esito["fascia"]


# ============================================ il campionamento


async def test_la_prima_lettura_di_un_contatore_non_e_un_consumo(casa):
    """Dice a che punto e', non quanto e' passato: contarla come consumo
    attribuirebbe a quest'ora tutto lo storico del dispositivo."""
    quante = await servizio_modulo.servizio_energia.campiona()

    assert quante == 2
    righe = depositi.letture_energia.fra(
        datetime.now(timezone.utc) - timedelta(hours=1), datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert all(r["consumo"] == 0.0 for r in righe)
    assert {r["valore"] for r in righe} == {1234.5, 88.0}


async def test_la_seconda_lettura_produce_il_consumo(casa, monkeypatch):
    await servizio_modulo.servizio_energia.campiona()

    piu_avanti = [dict(s) for s in STATI]
    piu_avanti[0]["state"] = "1237.0"

    class Dopo:
        async def stati_correnti(self):
            return piu_avanti

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: Dopo())
    await servizio_modulo.servizio_energia.campiona()

    ultima = depositi.letture_energia.ultima("sensor.casa_energia")

    assert ultima["consumo"] == 2.5


def test_un_contatore_azzerato_non_produce_consumo_negativo():
    """Dispositivo riavviato: la differenza sarebbe -1200."""
    precedente = {"valore": 1234.5}

    assert servizio_modulo._differenza(precedente, 3.0) == 3.0


def test_un_salto_indietro_piccolo_vale_zero():
    assert servizio_modulo._differenza({"valore": 100.0}, 99.0) == 0.0


def test_senza_precedente_il_consumo_e_zero():
    assert servizio_modulo._differenza(None, 1234.5) == 0.0


async def test_un_sensore_non_disponibile_viene_saltato(casa, monkeypatch):
    """Uno zero in mezzo a un contatore cumulativo diventerebbe un
    azzeramento, e il conto della giornata salterebbe."""
    rotti = [dict(s) for s in STATI]
    rotti[0]["state"] = "unavailable"

    class Rotto:
        async def stati_correnti(self):
            return rotti

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: Rotto())

    quante = await servizio_modulo.servizio_energia.campiona()

    assert quante == 1
    assert depositi.letture_energia.ultima("sensor.casa_energia") is None


async def test_senza_contatori_non_si_scrive_niente(casa, monkeypatch):
    class Spoglia:
        async def stati_correnti(self):
            return [{"entity_id": "light.salotto", "state": "on", "attributes": {}}]

    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: Spoglia())

    assert await servizio_modulo.servizio_energia.campiona() == 0


def test_lo_storico_si_pulisce():
    """Una casa che scrive ogni ora fa quasi novemila righe l'anno per
    sensore."""
    vecchia = datetime.now(timezone.utc) - timedelta(days=500)
    depositi.letture_energia.registra("sensor.casa_energia", 1.0, 0.0, fasce.F1, vecchia)
    depositi.letture_energia.registra("sensor.casa_energia", 2.0, 1.0, fasce.F1)

    tolte = depositi.letture_energia.pulisci(datetime.now(timezone.utc) - timedelta(days=400))

    assert tolte == 1
    assert depositi.letture_energia.ultima("sensor.casa_energia")["valore"] == 2.0


# ============================================ la tariffa dalla configurazione


def test_la_tariffa_bioraria_arriva_dalla_configurazione(tariffa_fissa):
    t = energia.tariffa_configurata()

    assert t.tipo == dominio.BIORARIA
    assert t.prezzo(fasce.F1) == 0.35
    assert t.prezzo(fasce.F3) == 0.20


def test_senza_prezzi_si_ripiega_e_si_dichiara(monkeypatch):
    monkeypatch.setattr(settings.energia, "tipo", "bioraria")
    monkeypatch.setattr(settings.energia, "prezzo_punta", 0.0)
    monkeypatch.setattr(settings.energia, "prezzo_kwh", 0.0)

    assert energia.tariffa_configurata().stimata is True
