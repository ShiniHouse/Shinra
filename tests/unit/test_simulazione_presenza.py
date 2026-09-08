"""La casa che finge di essere abitata.

Una luce che si accende alle 20:00 e si spegne alle 23:00 tutte le sere non
dice «c'e' qualcuno»: dice «c'e' un timer». Chi guarda una casa per tre sere
di fila lo capisce, ed e' proprio la persona da cui ci si vorrebbe
difendere.

Provare una funzione fatta di casualita' sembra una contraddizione, e non lo
e': il piano si genera da un seme, quindi e' riproducibile, e cio' che si
verifica sono le proprieta' — quante luci, in che finestra, e soprattutto
che due sere di fila non si somiglino.

Riferimento: issue #23.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.domain import simulazione as dominio

LUCI = [f"light.stanza{n}" for n in range(6)]
TRAMONTO = datetime(2026, 9, 8, 19, 40)


# ------------------------------------------------------------ il piano


def test_lo_stesso_seme_da_lo_stesso_piano():
    """Senza riproducibilita' questa funzione non sarebbe verificabile, e
    deve funzionare mentre nessuno la guarda."""
    assert dominio.pianifica(LUCI, TRAMONTO, seme=7) == dominio.pianifica(LUCI, TRAMONTO, seme=7)


def test_semi_diversi_danno_sere_diverse():
    assert dominio.pianifica(LUCI, TRAMONTO, seme=1) != dominio.pianifica(LUCI, TRAMONTO, seme=2)


@pytest.mark.parametrize("seme", range(12))
def test_non_ripete_lo_schema_della_sera_prima(seme):
    """Il criterio di accettazione della scheda, provato su dodici sere.

    Lo stesso seme e' il caso peggiore, ed e' l'unico che prova qualcosa: due
    semi diversi darebbero due piani diversi da soli, senza che il confronto
    con ieri faccia niente. Con lo stesso seme il primo tentativo esce
    identico a ieri, e solo il controllo interno costringe a ripescarne un
    altro.
    """
    ieri = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    oggi = dominio.pianifica(LUCI, TRAMONTO, seme=seme, ieri=ieri)

    assert dominio._impronta(oggi) != dominio._impronta(ieri)


@pytest.mark.parametrize("seme", range(12))
def test_senza_il_piano_di_ieri_lo_stesso_seme_si_ripete(seme):
    """Il rovescio del test precedente: se non si passa `ieri`, la funzione
    non ha modo di sapere che si sta ripetendo, e infatti si ripete. Serve a
    dimostrare che a fare la differenza e' il confronto, non il caso."""
    prima = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    seconda = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    assert dominio._impronta(seconda) == dominio._impronta(prima)


@pytest.mark.parametrize("seme", range(12))
def test_le_accensioni_sono_poche_ma_non_una_sola(seme):
    """Una luce sola sembra una dimenticanza, tutta la casa una festa."""
    piano = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    assert dominio.MINIME <= len(piano) <= dominio.MASSIME


@pytest.mark.parametrize("seme", range(12))
def test_niente_si_accende_prima_del_tramonto(seme):
    piano = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    assert all(a.accendi_alle > TRAMONTO for a in piano)


@pytest.mark.parametrize("seme", range(12))
def test_tutto_si_spegne_entro_la_notte(seme):
    """Una luce accesa alle quattro del mattino non somiglia a nessuno."""
    piano = dominio.pianifica(LUCI, TRAMONTO, seme=seme)
    limite = TRAMONTO.replace(hour=23, minute=59) + timedelta(hours=1)

    assert all(a.spegni_alle <= limite for a in piano)


@pytest.mark.parametrize("seme", range(12))
def test_ogni_luce_resta_accesa_un_tempo_verosimile(seme):
    piano = dominio.pianifica(LUCI, TRAMONTO, seme=seme)

    assert all(timedelta(minutes=5) <= a.durata <= dominio.DURATA_MASSIMA for a in piano)


@pytest.mark.parametrize("seme", range(12))
def test_le_accensioni_non_si_ammucchiano(seme):
    """Una persona non accende tutte le stanze nello stesso quarto d'ora."""
    piano = dominio.pianifica(LUCI, TRAMONTO, seme=seme)
    inizi = [a.accendi_alle for a in piano]

    assert inizi == sorted(inizi)
    assert (inizi[-1] - inizi[0]) >= timedelta(minutes=45)


def test_una_luce_sola_non_lascia_la_casa_spenta():
    """Con una luce le combinazioni finiscono: si accetta la ripetizione,
    perche' una casa spenta e' il segnale piu' chiaro di tutti."""
    ieri = dominio.pianifica(["light.unica"], TRAMONTO, seme=3)

    oggi = dominio.pianifica(["light.unica"], TRAMONTO, seme=3, ieri=ieri)

    assert oggi != []


def test_senza_luci_non_si_inventa_niente():
    assert dominio.pianifica([], TRAMONTO) == []


# ------------------------------------------------ quando smettere


CASA_ABITATA_STATI = [
    {"entity_id": "person.alessio", "state": "home"},
    {"entity_id": "light.salotto", "state": "off"},
]

CASA_VUOTA_STATI = [
    {"entity_id": "person.alessio", "state": "not_home"},
    {"entity_id": "light.salotto", "state": "off"},
    {"entity_id": "light.cucina", "state": "off"},
    {"entity_id": "light.studio", "state": "off"},
]


async def test_non_parte_se_in_casa_c_e_qualcuno(monkeypatch):
    """Accenderebbe e spegnerebbe le luci addosso alle persone, ed e' il
    modo piu' rapido perche' la funzione venga disattivata per sempre."""
    from shinra.skills.simulazione import ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_ABITATA_STATI))

    esito = await controllo.accendi()

    assert esito["success"] is False
    assert "c'e' qualcuno" in esito["message"]
    assert controllo.attiva is False


async def test_con_la_casa_vuota_parte(monkeypatch):
    """Il rovescio del test precedente: senza, «non parte mai» lo
    passerebbe."""
    from shinra.skills import simulazione as capacita

    controllo = capacita.ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_VUOTA_STATI))
    monkeypatch.setattr(controllo, "_programma", lambda luci, tramonto: len(luci))

    esito = await controllo.accendi()

    assert esito["success"] is True
    assert controllo.attiva is True


async def test_senza_persone_configurate_parte_lo_stesso(monkeypatch):
    """«Casa vuota» dedotta dal nulla non e' una deduzione: chi non ha
    entita' `person` in Home Assistant deve poter usare la simulazione."""
    from shinra.skills.simulazione import ControlloSimulazione

    controllo = ControlloSimulazione()
    senza_persone = [s for s in CASA_VUOTA_STATI if not s["entity_id"].startswith("person.")]
    monkeypatch.setattr(controllo, "_stati", _restituisci(senza_persone))
    monkeypatch.setattr(controllo, "_programma", lambda luci, tramonto: len(luci))

    esito = await controllo.accendi()

    assert esito["success"] is True


async def test_senza_luci_non_si_accende(monkeypatch):
    from shinra.skills.simulazione import ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci([]))

    esito = await controllo.accendi()

    assert esito["success"] is False
    assert "luci" in esito["message"]


def test_il_tramonto_arriva_da_home_assistant():
    from shinra.skills.simulazione import ControlloSimulazione

    stati = [{"entity_id": "sun.sun", "attributes": {"next_setting": "2026-09-08T18:42:00+00:00"}}]

    assert ControlloSimulazione._tramonto(stati).hour in range(24)
    assert ControlloSimulazione._tramonto(stati).minute == 42


def test_senza_sun_sun_si_ripiega_su_un_ora_plausibile():
    from shinra.skills.simulazione import TRAMONTO_DI_RIPIEGO, ControlloSimulazione

    ripiego = ControlloSimulazione._tramonto([])

    assert ripiego.hour == TRAMONTO_DI_RIPIEGO


def test_le_luci_spente_o_irraggiungibili(monkeypatch):
    from shinra.skills.simulazione import ControlloSimulazione

    stati = [
        {"entity_id": "light.buona", "state": "off"},
        {"entity_id": "light.rotta", "state": "unavailable"},
        {"entity_id": "light.ignota", "state": "unknown"},
        {"entity_id": "switch.non_e_una_luce", "state": "off"},
    ]

    assert ControlloSimulazione._luci_disponibili(stati) == ["light.buona"]


def test_il_piano_di_domani_e_nel_pomeriggio():
    from datetime import datetime

    from shinra.skills.simulazione import ORA_DI_RIPIANIFICARE, prossimo_giorno

    domani = prossimo_giorno(datetime(2026, 9, 8, 23, 40))

    assert (domani.day, domani.hour) == (9, ORA_DI_RIPIANIFICARE)


# ------------------------------------------------ chi guarda i rientri


async def test_si_spegne_da_sola_quando_qualcuno_rientra(monkeypatch):
    from shinra.domain.eventi import CASA_ABITATA, Evento
    from shinra.services import simulazione as servizio_modulo

    spenta = []
    monkeypatch.setattr(servizio_modulo.simulazione, "attiva", True)
    monkeypatch.setattr(
        servizio_modulo.simulazione,
        "spegni",
        lambda motivo="": spenta.append(motivo) or _niente(),
    )

    servizio_modulo.ServizioSimulazione()._qualcuno_e_tornato(Evento(tipo=CASA_ABITATA, dati={}))

    assert spenta == ["rientro"]


async def test_se_la_simulazione_e_spenta_il_rientro_non_fa_niente(monkeypatch):
    """Senza questo controllo ogni rientro annullerebbe job che non
    esistono, e il log direbbe «smetto di fingere» a casa gia' normale."""
    from shinra.domain.eventi import CASA_ABITATA, Evento
    from shinra.services import simulazione as servizio_modulo

    spenta = []
    monkeypatch.setattr(servizio_modulo.simulazione, "attiva", False)
    monkeypatch.setattr(
        servizio_modulo.simulazione,
        "spegni",
        lambda motivo="": spenta.append(motivo) or _niente(),
    )

    servizio_modulo.ServizioSimulazione()._qualcuno_e_tornato(Evento(tipo=CASA_ABITATA, dati={}))

    assert spenta == []


def test_il_servizio_si_iscrive_una_volta_sola():
    from shinra.services.simulazione import ServizioSimulazione

    servizio = ServizioSimulazione()
    try:
        assert servizio.avvia() is True
        assert servizio.avvia() is False
    finally:
        servizio.ferma()


def _restituisci(stati):
    async def _finto():
        return stati

    return _finto


async def _niente():
    return None


# ------------------------------------------------ quel che arriva allo scheduler


class SchedulerFinto:
    """Lo scheduler vero scrive su SQLite e fa partire un thread: qui serve
    solo sapere *cosa* gli e' stato chiesto."""

    def __init__(self):
        self.programmati = {}
        self.annullati = []

    def programma_azione(self, identificativo, funzione, argomenti, quando, tolleranza=300):
        self.programmati[identificativo] = (funzione, argomenti, quando)
        return True

    def annulla(self, identificativo):
        self.annullati.append(identificativo)
        return True


@pytest.fixture
def scheduler_finto(monkeypatch):
    from shinra.infra.scheduler import motore

    finto = SchedulerFinto()
    monkeypatch.setattr(motore, "scheduler", finto)
    return finto


async def test_ogni_accensione_diventa_due_job(scheduler_finto, monkeypatch):
    """Una luce che si accende e non si spegne piu' e' peggio di una luce
    spenta: al mattino la casa e' illuminata e la finzione e' finita."""
    from shinra.skills.simulazione import PREFISSO_JOB, ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_VUOTA_STATI))

    await controllo.accendi()

    accensioni = controllo.dettaglio()["accensioni"]
    for voce in accensioni:
        assert f"{PREFISSO_JOB}on_{voce['entity_id']}" in scheduler_finto.programmati
        assert f"{PREFISSO_JOB}off_{voce['entity_id']}" in scheduler_finto.programmati


async def test_si_programma_anche_il_piano_di_domani(scheduler_finto, monkeypatch):
    """Senza, la simulazione durerebbe una sera sola."""
    from shinra.skills.simulazione import JOB_RIPIANIFICA, ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_VUOTA_STATI))

    await controllo.accendi()

    assert JOB_RIPIANIFICA in scheduler_finto.programmati


async def test_spegnere_annulla_tutto_quello_che_era_stato_programmato(scheduler_finto, monkeypatch):
    from shinra.skills.simulazione import JOB_RIPIANIFICA, ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_VUOTA_STATI))
    await controllo.accendi()
    programmati = set(scheduler_finto.programmati)

    await controllo.spegni()

    assert programmati <= set(scheduler_finto.annullati)
    assert JOB_RIPIANIFICA in scheduler_finto.annullati
    assert controllo.attiva is False
    assert controllo.dettaglio()["accensioni"] == []


async def test_ripianificare_a_simulazione_spenta_non_programma_niente(scheduler_finto, monkeypatch):
    """Il job di domani parte anche dopo uno spegnimento a mano, se lo
    scheduler lo aveva gia' scritto su disco: deve accorgersene."""
    from shinra.skills.simulazione import ControlloSimulazione

    controllo = ControlloSimulazione()
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_VUOTA_STATI))

    assert await controllo.pianifica_la_serata() == 0
    assert scheduler_finto.programmati == {}


async def test_ripianificare_non_richiede_che_la_casa_sia_ancora_vuota(scheduler_finto, monkeypatch):
    """Chi rientra fa spegnere la simulazione per la sua strada (il servizio).
    Se il piano di domani chiedesse di nuovo «e' vuota?» a meta' pomeriggio,
    una persona in casa per il pranzo la fermerebbe per sempre."""
    from shinra.skills.simulazione import ControlloSimulazione

    controllo = ControlloSimulazione()
    controllo.attiva = True
    monkeypatch.setattr(controllo, "_stati", _restituisci(CASA_ABITATA_STATI + CASA_VUOTA_STATI))

    assert await controllo.pianifica_la_serata() > 0


# ------------------------------------------------ il tool


async def test_il_tool_dice_che_e_spenta_quando_e_spenta(monkeypatch):
    from shinra.skills import simulazione as capacita

    monkeypatch.setattr(capacita.simulazione, "attiva", False)
    monkeypatch.setattr(capacita.simulazione, "_piano", [])

    esito = await capacita.comanda_simulazione("stato")

    assert esito["success"] is True
    assert "spenta" in esito["message"]


async def test_il_tool_accende_e_spegne(scheduler_finto, monkeypatch):
    from shinra.skills import simulazione as capacita

    monkeypatch.setattr(capacita.simulazione, "_stati", _restituisci(CASA_VUOTA_STATI))
    try:
        acceso = await capacita.comanda_simulazione("attiva")
        assert acceso["success"] is True
        assert capacita.simulazione.attiva is True

        stato = await capacita.comanda_simulazione("verifica")
        assert stato["attiva"] is True

        spento = await capacita.comanda_simulazione("ferma")
        assert spento["success"] is True
    finally:
        capacita.simulazione.attiva = False
        capacita.simulazione._piano = []


async def test_il_rifiuto_arriva_al_modello_come_errore(monkeypatch):
    """Il modello guarda `error`: senza, riferirebbe alla persona che la
    simulazione e' partita mentre non e' partita."""
    from shinra.skills import simulazione as capacita

    monkeypatch.setattr(capacita.simulazione, "_stati", _restituisci(CASA_ABITATA_STATI))

    esito = await capacita.comanda_simulazione("accendi")

    assert esito["success"] is False
    assert esito["error"] == esito["message"]


async def test_un_azione_inventata_non_fa_danni():
    from shinra.skills.simulazione import comanda_simulazione

    esito = await comanda_simulazione("mettila a mezzo servizio")

    assert esito["success"] is False
    assert "non prevista" in esito["error"]
