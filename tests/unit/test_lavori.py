"""I lavori in background («ci penso», #431, ADR 0013): le regole del gioco, il servizio, la privacy e il riavvio.

Si prova con funzioni finte (nessun modello): conta che un lavoro rispetti il tetto, la coda a uno alla volta, l'annullo, che non lo
veda nessuno tranne chi l'ha chiesto, e che un riavvio non faccia finta di sapere come era finito.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from shinra.api import sicurezza
from shinra.api.app import app
from shinra.config.settings import settings
from shinra.domain import lavori as dominio
from shinra.infra.db import depositi
from shinra.infra.db.lavori import lavori as deposito
from shinra.services import permessi
from shinra.services.lavori import LavoroNonTrovato, ServizioLavori, TroppiLavori
from shinra.services.user_manager import UserProfile, user_manager

PIN_DI_PROVA = "482913"
SEGNO = "ZEBRA-GIALLO-4417"

# ------------------------------------------------------------------ il dominio


def test_gli_stati_finali_non_tornano_indietro():
    for finale in (dominio.FATTO, dominio.FALLITO, dominio.ANNULLATO, dominio.INTERROTTO):
        assert dominio.e_terminale(finale)
        assert not any(dominio.puo_passare(finale, a) for a in dominio.STATI)
    assert dominio.puo_passare(dominio.IN_CODA, dominio.IN_CORSO)
    assert not dominio.puo_passare(dominio.IN_CORSO, dominio.IN_CODA), "un lavoro in corso non torna in coda"
    assert not dominio.puo_passare(dominio.IN_CODA, dominio.FATTO), "non si finisce senza essere partiti"


@pytest.mark.parametrize(
    ("scritto", "usato"),
    [(900, 900), (1, 10), (0, 10), (-5, 10), (10**9, 3600), ("boh", 3600), (None, 3600)],
)
def test_il_tetto_sta_sempre_fra_dieci_secondi_e_un_ora(scritto, usato):
    assert dominio.tetto_valido(scritto) == usato


def test_l_avanzamento_sale_e_basta():
    assert dominio.avanzamento_valido(0, 40) == 40
    assert dominio.avanzamento_valido(40, 10) == 40
    assert dominio.avanzamento_valido(40, 500) == 100
    assert dominio.avanzamento_valido(40, -3) == 40


# ------------------------------------------------------------------ il servizio


@pytest.fixture()
def servizio(monkeypatch):
    monkeypatch.setattr(dominio, "TETTO_MINIMO_SECONDI", 0)  # nei test un tetto di decimi di secondo
    monkeypatch.setattr(settings.lavori, "tetto_secondi", 5)
    depositi_puliti()
    yield ServizioLavori()
    depositi_puliti()


def depositi_puliti():
    for profilo in ("alessio", "sonia"):
        deposito.dimentica_profilo(profilo)


async def finito(servizio, proprietario, identificativo, secondi=5):
    """Aspetta che il lavoro sia terminale."""
    fine = asyncio.get_running_loop().time() + secondi
    while asyncio.get_running_loop().time() < fine:
        lavoro = servizio.trova(proprietario, identificativo)
        if dominio.e_terminale(lavoro["stato"]):
            return lavoro
        await asyncio.sleep(0.01)
    raise AssertionError("il lavoro non e' finito in tempo")


async def test_un_lavoro_riuscito_consegna_l_esito_e_l_avanzamento(servizio):
    consegnati = []

    async def alla_fine(lavoro):
        consegnati.append(lavoro)

    servizio.alla_fine(alla_fine)

    async def funzione(avanza):
        avanza(40, "consulto la casa")
        await asyncio.sleep(0.01)
        avanza(10, "controllo")  # l'avanzamento non scende, la fase si aggiorna
        assert deposito.trova(creato_id["id"])["avanzamento"] == 40
        return "Fatto: le luci sono accese."

    creato_id: dict = {}
    creato = servizio.prendi_in_carico("alessio", "prepara la sera", funzione)
    creato_id["id"] = creato["id"]
    assert creato["stato"] == dominio.IN_CODA and creato["richiesta"] == "prepara la sera"
    lavoro = await finito(servizio, "alessio", creato["id"])
    assert lavoro["stato"] == dominio.FATTO and lavoro["esito"] == "Fatto: le luci sono accese."
    assert lavoro["avanzamento"] == 100 and lavoro["fase"] == "controllo"
    assert [c["id"] for c in consegnati] == [creato["id"]], "l'esito si consegna una volta sola"


async def test_un_lavoro_che_supera_il_tetto_e_fallito_e_la_funzione_viene_fermata(servizio, monkeypatch):
    monkeypatch.setattr(settings.lavori, "tetto_secondi", 1)  # il minimo dei test e' zero: un secondo basta
    ferma = asyncio.Event()

    async def senza_fine(avanza):
        try:
            await asyncio.sleep(60)
        finally:
            ferma.set()
        return "mai"

    creato = servizio.prendi_in_carico("alessio", "un compito infinito", senza_fine)
    lavoro = await finito(servizio, "alessio", creato["id"])
    assert (
        lavoro["stato"] == dominio.FALLITO
        and lavoro["motivo"] == dominio.MOTIVO_TETTO
        and lavoro["esito"] == ""
    )
    assert ferma.is_set(), "la funzione deve ricevere la cancellazione, non restare viva dietro le quinte"


async def test_un_errore_non_fa_cadere_il_servizio_e_non_si_racconta_in_chiaro(servizio):
    async def guasta(avanza):
        raise RuntimeError(f"password del database: {SEGNO}")

    creato = servizio.prendi_in_carico("alessio", "x", guasta)
    lavoro = await finito(servizio, "alessio", creato["id"])
    assert lavoro["stato"] == dominio.FALLITO
    assert (
        SEGNO not in lavoro["motivo"] and SEGNO not in lavoro["esito"]
    ), "il dettaglio tecnico resta nel log"


async def test_i_lavori_pesanti_vanno_uno_alla_volta(servizio):
    ordine: list[str] = []

    async def lavoro_di(nome):
        async def f(avanza):
            ordine.append(f"inizio {nome}")
            await asyncio.sleep(0.05)
            ordine.append(f"fine {nome}")
            return nome

        return f

    a = servizio.prendi_in_carico("alessio", "a", await lavoro_di("a"))
    b = servizio.prendi_in_carico("alessio", "b", await lavoro_di("b"))
    await finito(servizio, "alessio", a["id"])
    await finito(servizio, "alessio", b["id"])
    assert ordine == ["inizio a", "fine a", "inizio b", "fine b"], "mai due insieme"


async def test_annullare_un_lavoro_in_corso_lo_ferma_e_lo_dice(servizio):
    partito = asyncio.Event()

    async def lungo(avanza):
        partito.set()
        await asyncio.sleep(60)
        return "mai"

    creato = servizio.prendi_in_carico("alessio", "lungo", lungo)
    await asyncio.wait_for(partito.wait(), 2)
    annullato = await servizio.annulla("alessio", creato["id"])
    assert annullato["stato"] == dominio.ANNULLATO
    # Annullare di nuovo non cambia niente e non solleva.
    assert (await servizio.annulla("alessio", creato["id"]))["stato"] == dominio.ANNULLATO


async def test_annullare_un_lavoro_ancora_in_coda_non_lo_fa_mai_partire(servizio):
    fatte = []

    async def primo(avanza):
        await asyncio.sleep(0.2)
        return "primo"

    async def secondo(avanza):
        fatte.append("partito")
        return "secondo"

    a = servizio.prendi_in_carico("alessio", "a", primo)
    b = servizio.prendi_in_carico("alessio", "b", secondo)
    await asyncio.sleep(0.02)  # il primo e' in corso, il secondo aspetta il turno
    assert (await servizio.annulla("alessio", b["id"]))["stato"] == dominio.ANNULLATO
    await finito(servizio, "alessio", a["id"])
    assert fatte == [], "un lavoro annullato in coda non deve partire"


async def test_un_lavoro_finito_non_si_annulla(servizio):
    async def breve(avanza):
        return "ok"

    creato = servizio.prendi_in_carico("alessio", "x", breve)
    await finito(servizio, "alessio", creato["id"])
    assert (await servizio.annulla("alessio", creato["id"]))["stato"] == dominio.FATTO


async def test_non_si_puo_riempire_la_coda(servizio):
    async def lenta(avanza):
        await asyncio.sleep(0.3)
        return "ok"

    for _ in range(5):
        servizio.prendi_in_carico("alessio", "x", lenta)
    with pytest.raises(TroppiLavori):
        servizio.prendi_in_carico("alessio", "una di troppo", lenta)
    # Sonia ha la sua coda: quella di Alessio non le toglie posto.
    servizio.prendi_in_carico("sonia", "mia", lenta)
    await servizio.ferma()


# ------------------------------------------------------------------ il riavvio, onesto


def test_al_riavvio_i_lavori_a_meta_diventano_interrotti_e_non_si_riprendono(servizio):
    in_coda = deposito.crea("alessio", "mai partito", "chat", 900)
    in_corso = deposito.crea("alessio", "a meta'", "chat", 900)
    deposito.passa_a(in_corso["id"], dominio.IN_CORSO, deposito.trova(in_corso["id"])["creato_il"])
    finito_prima = deposito.crea("alessio", "gia' finito", "chat", 900)
    deposito.passa_a(finito_prima["id"], dominio.IN_CORSO, finito_prima["creato_il"])
    deposito.passa_a(finito_prima["id"], dominio.FATTO, finito_prima["creato_il"], esito="ok")

    assert servizio.riconcilia() == 2
    assert deposito.trova(in_coda["id"])["stato"] == dominio.INTERROTTO
    interrotto = deposito.trova(in_corso["id"])
    assert interrotto["stato"] == dominio.INTERROTTO and "riavviato" in interrotto["motivo"]
    assert deposito.trova(finito_prima["id"])["stato"] == dominio.FATTO, "un lavoro finito non si tocca"
    assert servizio.riconcilia() == 0


async def test_lo_spegnimento_interrompe_non_annulla(servizio):
    partito = asyncio.Event()

    async def lungo(avanza):
        partito.set()
        await asyncio.sleep(60)
        return "mai"

    creato = servizio.prendi_in_carico("alessio", "lungo", lungo)
    await asyncio.wait_for(partito.wait(), 2)
    await servizio.ferma()
    assert (
        servizio.trova("alessio", creato["id"])["stato"] == dominio.INTERROTTO
    ), "non e' stato lui a volerlo"


# ------------------------------------------------------------------ la privacy


async def test_un_lavoro_non_si_vede_ne_si_annulla_da_un_altro_profilo(servizio):
    async def breve(avanza):
        return f"il codice e' {SEGNO}"

    creato = servizio.prendi_in_carico("sonia", f"ricordami {SEGNO}", breve)
    await finito(servizio, "sonia", creato["id"])
    with pytest.raises(LavoroNonTrovato):
        servizio.trova("alessio", creato["id"])
    with pytest.raises(LavoroNonTrovato):
        await servizio.annulla("alessio", creato["id"])
    assert servizio.elenco("alessio") == []
    assert [lv["id"] for lv in servizio.elenco("sonia")] == [creato["id"]]


async def test_il_registro_dice_che_e_nato_e_come_e_finito_mai_cosa_si_e_chiesto(servizio):
    from shinra.services import registro

    async def breve(avanza):
        return f"risposta con {SEGNO}"

    creato = servizio.prendi_in_carico("sonia", f"richiesta con {SEGNO}", breve)
    await finito(servizio, "sonia", creato["id"])
    righe = registro.elenca(ore=1) if hasattr(registro, "elenca") else []
    testo = repr(righe)
    assert SEGNO not in testo, "il testo di una richiesta o di un esito non deve finire nel registro"


async def test_dimentica_tutto_di_me_toglie_i_lavori(servizio):
    from shinra.services import ricordi

    async def breve(avanza):
        return "ok"

    a = servizio.prendi_in_carico("sonia", "mia", breve)
    altro = servizio.prendi_in_carico("alessio", "di alessio", breve)
    await finito(servizio, "sonia", a["id"])
    await finito(servizio, "alessio", altro["id"])
    # Il servizio di prova non e' quello dell'applicazione: si prova direttamente il suo gesto, e la cancellazione nel deposito.
    assert servizio.dimentica_profilo("sonia") == 1
    assert deposito.del_profilo("sonia") == [] and len(deposito.del_profilo("alessio")) == 1
    assert hasattr(ricordi, "dimentica_tutto_di_me")


# ------------------------------------------------------------------ le rotte, con due persone vere


@pytest.fixture()
def due_persone():
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    esistenti = user_manager.get_users()
    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    depositi.utenti.sostituisci_tutto(
        [
            UserProfile(id="alessio", name="Alessio", role="admin").model_dump(),
            UserProfile(id="sonia", name="Sonia", role="adult").model_dump(),
        ]
    )
    for chi in ("alessio", "sonia"):
        user_manager.imposta_pin(chi, PIN_DI_PROVA)
    sicurezza.azzera_stato()
    depositi_puliti()
    with TestClient(app) as per_alessio, TestClient(app) as per_sonia:
        for cliente, chi in ((per_alessio, "alessio"), (per_sonia, "sonia")):
            assert (
                cliente.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": chi}).status_code == 200
            )
        # Dopo l'avvio: all'avvio un lavoro rimasto a meta' diventa «interrotto», ed e' giusto cosi'.
        lavoro = deposito.crea("sonia", f"una richiesta con {SEGNO}", "chat", 900)
        deposito.passa_a(lavoro["id"], dominio.IN_CORSO, lavoro["creato_il"])
        yield per_alessio, per_sonia, lavoro["id"]
    depositi.utenti.sostituisci_tutto([u.model_dump() for u in esistenti])
    depositi_puliti()
    settings.security.auth_enabled = era_attiva
    sicurezza.azzera_stato()


def test_il_proprietario_vede_il_suo_lavoro_e_un_altro_no_da_nessuna_rotta(due_persone):
    per_alessio, per_sonia, lavoro = due_persone
    # La prova della prova: il proprietario, con le stesse richieste, vede il segno.
    assert SEGNO in per_sonia.get("/api/lavori").text
    assert SEGNO in per_sonia.get(f"/api/lavori/{lavoro}").text
    # L'altro non lo vede da nessuna parte.
    assert SEGNO not in per_alessio.get("/api/lavori").text
    assert per_alessio.get("/api/lavori").json() == {"lavori": []}
    assert per_alessio.get(f"/api/lavori/{lavoro}").status_code == 404
    assert per_alessio.post(f"/api/lavori/{lavoro}/annulla").status_code == 404
    assert (
        deposito.trova(lavoro)["stato"] == dominio.IN_CORSO
    ), "un tentativo altrui non deve aver toccato il lavoro"


def test_il_proprietario_lo_annulla_dalla_rotta(due_persone):
    _, per_sonia, lavoro = due_persone
    risposta = per_sonia.post(f"/api/lavori/{lavoro}/annulla")
    assert risposta.status_code == 200 and risposta.json()["stato"] == dominio.ANNULLATO


def test_senza_accesso_nessuno_vede_i_lavori():
    prima = settings.security.auth_enabled
    settings.security.auth_enabled = True
    try:
        with TestClient(app) as anonimo:
            assert anonimo.get("/api/lavori").status_code in (401, 403)
    finally:
        settings.security.auth_enabled = (
            prima  # com'era: lasciarla spenta farebbe fallire i test che vengono dopo
        )
