"""Le regole all'alba e al tramonto: quelle che non sono mai scattate.

Questo file nasce da un difetto trovato **misurando invece di leggere**.
`riprogramma_tutte` chiamava `prossimo_scatto` senza passargli alba e
tramonto; il dominio, che giustamente non li inventa, rispondeva `None`; e il
motore saltava la regola senza dire niente. Risultato: da quando esiste la
issue #27, **nessuna regola del sole e' mai finita nello scheduler**.

Non se n'era accorto nessuno perche' una regola che non scatta e una regola
che non c'e' si somigliano troppo — che e' esattamente la frase scritta in
cima a `domain/regole.py`, e che era vera un livello piu' sotto, dove nessuno
aveva guardato.

Il test che lo tiene fermo e' `test_una_regola_all_alba_finisce_nello_scheduler`.
Gli altri due che contano sono `test_quando_la_casa_si_presenta_si_riprogramma`
(all'avvio la cache e' vuota: senza, il difetto tornerebbe identico a ogni
riavvio) e `test_una_regola_che_non_si_puo_programmare_lo_dice`.

Riferimento: issue #27, issue #28.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.domain import sole as dominio
from shinra.domain.eventi import HA_STATI_PRONTI, HA_STATO_CAMBIATO, Evento
from shinra.infra.db import depositi
from shinra.infra.homeassistant.stati import DOMINI_OSSERVATI, cache_stati
from shinra.infra.scheduler.motore import scheduler
from shinra.services.regole import motore_regole

DOMANI = (datetime.now().astimezone() + timedelta(hours=8)).replace(microsecond=0)

SUN = {
    "entity_id": "sun.sun",
    "state": "below_horizon",
    "attributes": {
        "next_rising": DOMANI.isoformat(),
        "next_setting": (DOMANI + timedelta(hours=12)).isoformat(),
    },
}


@pytest.fixture
def scheduler_finto(monkeypatch):
    programmati: list[tuple[str, datetime]] = []
    monkeypatch.setattr(
        scheduler,
        "programma_azione",
        lambda identificativo, funzione, argomenti, quando: (
            programmati.append((identificativo, quando)) or True
        ),
    )
    monkeypatch.setattr(scheduler, "annulla", lambda *a, **k: True)
    return programmati


@pytest.fixture(autouse=True)
def casa_pulita():
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()
    yield
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()


def _regola(nome: str, tipo: str, **extra) -> str:
    voce = motore_regole.crea(
        {
            "nome": nome,
            "trigger": {"tipo": tipo, **extra},
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    return str(voce["id"])


# ================================================== la lettura di sun.sun


def test_alba_e_tramonto_si_leggono_da_sun_sun():
    letto = dominio.leggi(SUN)

    assert letto.alba == DOMANI
    assert letto.tramonto == DOMANI + timedelta(hours=12)
    assert letto.conosciuto is True


def test_senza_sun_sun_non_si_sa_niente():
    """`None` e non un'ora inventata: un orario inventato e' peggio di uno
    mancante, perche' il mancante si vede e l'inventato no."""
    vuoto = dominio.leggi(None)

    assert vuoto.alba is None and vuoto.tramonto is None
    assert vuoto.conosciuto is False


def test_un_orario_illeggibile_non_diventa_un_orario():
    letto = dominio.leggi({"attributes": {"next_rising": "domani mattina"}})

    assert letto.alba is None


def test_la_z_di_utc_si_capisce():
    """Home Assistant scrive gli istanti con la `Z`, che `fromisoformat` non
    accettava prima di Python 3.11: la casa gira su quello che c'e'."""
    letto = dominio.leggi({"attributes": {"next_setting": "2026-09-10T18:42:00Z"}})

    assert letto.tramonto is not None
    assert letto.tramonto.minute == 42


def test_si_pesca_sun_sun_da_un_elenco_di_stati():
    letto = dominio.dagli_stati([{"entity_id": "light.x", "state": "on"}, SUN])

    assert letto.tramonto is not None


def test_in_un_elenco_senza_sole_non_si_inventa_niente():
    assert dominio.dagli_stati([{"entity_id": "light.x"}]).conosciuto is False


# ============================================ il difetto: mai programmate


def test_una_regola_all_alba_finisce_nello_scheduler(scheduler_finto):
    """Il test che tiene fermo il difetto.

    Prima di questa correzione la risposta era: no. Tre regole attive, una
    sola programmata — quella a orario — e le altre due saltate in silenzio.
    """
    cache_stati.sostituisci([SUN])
    identificativo = _regola("Alba", "alba")

    scheduler_finto.clear()
    motore_regole.riprogramma_tutte()

    assert [i for i, _ in scheduler_finto] == [f"regola_{identificativo}"]


def test_anche_il_tramonto(scheduler_finto):
    cache_stati.sostituisci([SUN])
    identificativo = _regola("Tramonto", "tramonto")

    scheduler_finto.clear()
    motore_regole.riprogramma_tutte()

    assert [i for i, _ in scheduler_finto] == [f"regola_{identificativo}"]


def test_lo_scarto_in_minuti_sposta_l_orario(scheduler_finto):
    """«Mezz'ora prima del tramonto» e' la richiesta piu' comune di tutte, e
    uno scarto ignorato non si vede: la routine parte, solo tardi."""
    cache_stati.sostituisci([SUN])
    _regola("Prima", "tramonto", scarto_minuti=-30)

    scheduler_finto.clear()
    motore_regole.riprogramma_tutte()

    _, quando = scheduler_finto[0]
    assert quando == DOMANI + timedelta(hours=12) - timedelta(minutes=30)


def test_senza_sun_sun_la_regola_non_si_programma(scheduler_finto):
    """Non si ripiega su un'ora plausibile: programmare l'apertura delle
    tapparelle a un orario inventato vorrebbe dire una casa che fa le cose al
    momento sbagliato senza che niente lo spieghi."""
    _regola("Alba", "alba")

    scheduler_finto.clear()
    motore_regole.riprogramma_tutte()

    assert scheduler_finto == []


def test_una_regola_che_non_si_puo_programmare_lo_dice(scheduler_finto):
    """L'unica differenza fra «non e' ancora scattata» e «non scattera' mai».
    Senza, le due si leggono uguali — ed e' il motivo per cui il difetto e'
    rimasto in piedi per due versioni."""
    identificativo = _regola("Alba", "alba")

    motore_regole.riprogramma_tutte()

    assert "non so a che ora sorge" in depositi.regole.per_id(identificativo)["ultimo_esito"]


def test_una_regola_su_evento_non_si_lamenta_del_sole(scheduler_finto):
    """Il messaggio riguarda solo chi dipende dal sole.

    Una regola su evento non finisce **mai** nello scheduler ed e' sanissima:
    aspetta che qualcosa succeda. Scriverle addosso «non so a che ora sorge il
    sole» vorrebbe dire riempire l'elenco delle regole di allarmi falsi, e
    l'allarme vero — quello della regola del sole — si perderebbe fra loro.

    La prima versione di questo test usava una regola a orario e non provava
    niente: quella si programma, quindi non arrivava nemmeno al ramo che
    voleva sorvegliare. L'ho scoperto perche' rompere quel ramo non la faceva
    fallire.
    """
    identificativo = _regola("Su evento", "evento", evento="casa.vuota")

    motore_regole.riprogramma_tutte()

    assert depositi.regole.per_id(identificativo)["ultimo_esito"] == ""


# ==================================== quando si rifanno i conti, e perche'


@pytest.mark.asyncio
async def test_quando_la_casa_si_presenta_si_riprogramma(scheduler_finto):
    """All'avvio la cache degli stati e' vuota: `sun.sun` non c'e' ancora.

    Senza questo, il difetto tornerebbe identico a ogni riavvio — la regola
    resterebbe non programmata fino al primo tramonto utile, cioe' fino a
    dodici ore dopo.
    """
    _regola("Alba", "alba")
    motore_regole.riprogramma_tutte()
    assert scheduler_finto == [], "la cache e' vuota: non si puo' ancora programmare"

    cache_stati.sostituisci([SUN])
    await motore_regole._su_stati_pronti(Evento(tipo=HA_STATI_PRONTI, dati={"quanti": 1}))

    assert len(scheduler_finto) == 1


@pytest.mark.asyncio
async def test_quando_il_sole_cambia_si_riprogramma(scheduler_finto):
    """`sun.sun` cambia stato esattamente all'alba e al tramonto, e sono i due
    momenti in cui `next_rising` e `next_setting` scivolano al giorno dopo.
    Senza, una regola del sole scatterebbe una volta e poi resterebbe ferma
    fino al riavvio."""
    cache_stati.sostituisci([SUN])
    _regola("Alba", "alba")
    scheduler_finto.clear()

    await motore_regole._su_evento(
        Evento(tipo=HA_STATO_CAMBIATO, dati={"entity_id": "sun.sun", "stato": "above_horizon"})
    )

    assert len(scheduler_finto) == 1


@pytest.mark.asyncio
async def test_una_lampadina_qualunque_non_riprogramma_niente(scheduler_finto):
    """Riprogrammare tutto a ogni cambiamento della casa vorrebbe dire
    rifare il giro dello scheduler decine di volte al minuto."""
    cache_stati.sostituisci([SUN])
    _regola("Alba", "alba")
    scheduler_finto.clear()

    await motore_regole._su_evento(
        Evento(tipo=HA_STATO_CAMBIATO, dati={"entity_id": "light.salotto", "stato": "on"})
    )

    assert scheduler_finto == []


def test_il_sole_e_fra_i_domini_che_arrivano_sul_bus():
    """L'altra meta' della riprogrammazione: se `sun` non e' osservato, il
    cambiamento di `sun.sun` non arriva mai al motore e il test qui sopra
    prova qualcosa che in casa non succede."""
    assert "sun" in DOMINI_OSSERVATI


@pytest.mark.asyncio
async def test_il_motore_avviato_ascolta_davvero_gli_stati_pronti(scheduler_finto):
    """Il collegamento, non solo il gestore.

    Provare `_su_stati_pronti` chiamandolo a mano lascia scoperta l'unica
    riga che conta: la sottoscrizione. Senza quella, il gestore e' un metodo
    che nessuno chiamera' mai — ed e' la forma esatta del difetto che questa
    correzione ripara.
    """
    from shinra.domain.eventi import bus

    motore_regole.ferma()
    _regola("Alba", "alba")
    motore_regole.avvia()
    try:
        cache_stati.sostituisci([SUN])
        scheduler_finto.clear()

        await bus.pubblica(Evento(tipo=HA_STATI_PRONTI, dati={"quanti": 1}))

        assert len(scheduler_finto) == 1
    finally:
        motore_regole.ferma()


@pytest.mark.asyncio
async def test_l_istantanea_iniziale_annuncia_che_la_casa_e_pronta(monkeypatch):
    """Chi programma in base al sole deve sapere quando puo' rifare i conti."""
    from shinra.domain import eventi as dominio_eventi
    from shinra.infra.homeassistant.eventi import ConnessioneEventi
    from shinra.infra.homeassistant.stati import CacheStati

    visti: list[Evento] = []
    monkeypatch.setattr(dominio_eventi.bus, "pubblica_senza_attendere", visti.append)

    class FintoCliente:
        async def get_states(self):
            return [SUN]

    connessione = ConnessioneEventi(cache=CacheStati())
    quanti = await connessione.prendi_istantanea(FintoCliente())

    assert quanti == 1
    assert [e.tipo for e in visti] == [HA_STATI_PRONTI]
