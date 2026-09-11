"""La rotta che riceve l'audio del microfono.

Esiste perche' fino alla issue #31 quell'audio andava a Google. Adesso arriva
qui e non esce.

Riferimento: issue #31.
"""

from __future__ import annotations

import asyncio
import io

import pytest
from fastapi.testclient import TestClient

from shinra.api import routes_voce as rotte_voce
from shinra.api.app import app
from shinra.domain import trascrizione as dominio
from shinra.services import trascrizione as servizio_modulo


@pytest.fixture
def con_motore(monkeypatch):
    """Il motore c'e', il modello e' gia' in memoria, e trascrive a comando.

    «Installato» e «caricato» sono due cose diverse e il difetto del 524 sta
    proprio nello scarto fra le due: la libreria c'era da subito, i pesi no.
    """
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: True)
    monkeypatch.setattr(
        servizio_modulo.whisper, "trascrivi", lambda audio, modello, lingua: "accendi la luce"
    )
    return monkeypatch


def _file(byte: bytes = b"\x00" * 512, tipo: str = "audio/webm"):
    return {"audio": ("comando.webm", io.BytesIO(byte), tipo)}


def test_lo_stato_richiede_una_sessione():
    """Dice cosa gira sul server di casa: non e' per chiunque passi."""
    with TestClient(app) as client:
        assert client.get("/api/voce/stato").status_code == 401


def test_trascrivere_richiede_una_sessione():
    with TestClient(app) as client:
        assert client.post("/api/voce/trascrivi", files=_file()).status_code == 401


def test_lo_stato_dice_che_l_audio_resta_in_casa(cliente_autenticato, con_motore):
    stato = cliente_autenticato.get("/api/voce/stato").json()

    assert stato["in_casa"] is True
    assert stato["pronto"] is True


def test_senza_la_libreria_lo_stato_dice_come_installarla(cliente_autenticato, monkeypatch):
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: False)

    stato = cliente_autenticato.get("/api/voce/stato").json()

    assert stato["pronto"] is False
    assert "faster-whisper" in stato["spiegazione"]


def test_una_registrazione_torna_come_testo(cliente_autenticato, con_motore):
    risposta = cliente_autenticato.post(
        "/api/voce/trascrivi", files=_file(), data={"tipo": "audio/webm;codecs=opus"}
    )

    assert risposta.status_code == 200
    assert risposta.json() == {"testo": "accendi la luce", "vuota": False}


def test_un_caricamento_etichettato_json_non_si_puo_leggere(cliente_autenticato, con_motore):
    """La causa, misurata, del microfono che non ha mai trascritto niente.

    La pagina mandava il file con le intestazioni di sempre, e fra quelle
    c'era `Content-Type: application/json`. Il corpo restava multipart, ma
    l'etichetta diceva altro: senza il «boundary» non c'e' modo di sapere
    dove finisce un pezzo e comincia l'altro, e il campo `audio` risulta
    mancante.

    Questo test non difende un comportamento che vogliamo: fissa la causa.
    Se un giorno il framework accettasse un multipart etichettato male,
    fallirebbe qui — e sarebbe giusto accorgersene, perche' vorrebbe dire
    che la guardia scritta nella pagina non serve piu' a niente.
    """
    risposta = cliente_autenticato.post(
        "/api/voce/trascrivi",
        files=_file(),
        headers={"Content-Type": "application/json"},
    )

    assert risposta.status_code == 422

    # E cosi' il rifiuto non e' una frase ma un elenco: e' il motivo per cui
    # la dashboard mostrava «[object Object]» invece di una spiegazione.
    dettaglio = risposta.json()["detail"]
    assert isinstance(dettaglio, list)
    assert any("audio" in str(voce.get("loc", "")) for voce in dettaglio)


def test_finche_i_pesi_si_caricano_la_rotta_risponde_subito(cliente_autenticato, monkeypatch):
    """Il difetto del 524, dal lato del server.

    Al primo avvio i pesi di Whisper si scaricano, e possono volerci minuti.
    Finche' quel caricamento avveniva dentro la richiesta, la richiesta
    restava aperta per tutto il tempo — e qualunque cosa stia davanti al
    server la tagliava molto prima: Cloudflare a cento secondi, con un 524
    che non spiega niente e non suggerisce di riprovare.

    Adesso la rotta risponde subito che il modello si sta preparando, e nel
    frattempo lo mette in moto. E' un rifiuto che scade da solo.
    """
    avviati: list[str] = []

    def prepara(nome):
        avviati.append(nome)
        return True

    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)
    monkeypatch.setattr(servizio_modulo.whisper, "prepara", prepara)

    def non_si_deve_arrivare_qui(audio, modello, lingua):
        raise AssertionError("il modello e' stato fatto girare dentro la richiesta")

    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", non_si_deve_arrivare_qui)

    risposta = cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert risposta.status_code == 409
    assert "preparando" in risposta.json()["detail"]
    assert avviati, "la rotta rifiuta e basta: il modello non si carichera' mai"


def test_la_trascrizione_non_gira_sul_filo_che_serve_la_casa(cliente_autenticato, monkeypatch):
    """Un difetto che nessuna schermata mostra, e che si vede solo dal fatto
    che ogni tanto la casa non risponde.

    La rotta e' `async`. Far girare il modello li' dentro ferma il filo che
    serve **tutte** le richieste: per i secondi della trascrizione l'hub non
    risponde a niente — non la dashboard, non Alexa, non gli eventi della
    casa. Una frase detta al microfono non deve poter spegnere la casa per il
    tempo in cui viene capita.

    Il test non misura il tempo — sarebbe una prova che passa o fallisce a
    seconda di quanto e' carica la macchina — ma guarda **dove** gira il
    modello: `asyncio.get_running_loop()` solleva se nel filo corrente non
    c'e' un ciclo di eventi, e nel filo del ciclo no.
    """
    visto: dict[str, bool] = {}

    def finto(audio, modello, lingua):
        try:
            asyncio.get_running_loop()
            visto["sul_filo_del_ciclo"] = True
        except RuntimeError:
            visto["sul_filo_del_ciclo"] = False
        return "accendi la luce"

    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: True)
    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", finto)

    risposta = cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert risposta.status_code == 200
    assert visto, "il modello non e' stato chiamato: il test non guarda piu' niente"
    assert not visto["sul_filo_del_ciclo"], "la trascrizione blocca il filo che serve la casa"


def test_all_avvio_il_modello_si_mette_in_carico_da_solo(monkeypatch):
    """Il rimedio vero: pagare il caricamento quando non aspetta nessuno.

    Senza questo, il primo che parla trova il modello freddo e si prende il
    rifiuto «sto preparando» — corretto, ma inutile: il modello comincerebbe
    a caricarsi solo perche' qualcuno ha provato, e nessuno avrebbe pensato a
    premere il microfono a vuoto per prepararlo.
    """
    chiamate: list[bool] = []

    def prepara():
        chiamate.append(True)
        return False

    monkeypatch.setattr(servizio_modulo.servizio_trascrizione, "prepara", prepara)

    with TestClient(app):
        pass

    assert chiamate, "l'avvio non prepara il modello: lo paghera' il primo che parla"


def test_l_avvio_scrive_nel_log_come_sta_la_voce(monkeypatch):
    """Un ramo che non fa niente in silenzio costa ore.

    Quando in casa il microfono non trascriveva, dal log non si poteva dire
    se la preparazione non fosse partita o fosse partita e morta: la riga
    c'era solo nel caso in cui partiva. Ho passato mezz'ora a ragionare per
    esclusione su un'informazione che il servizio aveva e non scriveva.

    Adesso lo stato della voce finisce nel log a ogni avvio, anche — anzi,
    soprattutto — quando non c'e' niente da preparare.
    """
    from shinra.api import app as applicazione

    righe: list[str] = []

    class LoggerFinto:
        def info(self, messaggio, *argomenti):
            righe.append(messaggio % argomenti if argomenti else messaggio)

        def __getattr__(self, _nome):
            return lambda *a, **k: None

    monkeypatch.setattr(applicazione, "logger", LoggerFinto())

    with TestClient(app):
        pass

    voce = [r for r in righe if r.startswith("Voce:")]
    assert voce, "l'avvio non dice come sta la voce"
    assert "motore=" in voce[0] and "gia_in_memoria=" in voce[0]


def test_lo_stato_distingue_installato_da_caricato(cliente_autenticato, monkeypatch):
    """La dashboard deve poter dire «aspetta» invece di far parlare qualcuno
    dentro un'attesa che finira' tagliata."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: False)

    stato = cliente_autenticato.get("/api/voce/stato").json()

    assert stato["pronto"] is True, "il motore c'e': non e' questo che manca"
    assert stato["modello_caricato"] is False


def test_il_silenzio_torna_come_niente_non_come_errore(cliente_autenticato, monkeypatch):
    """«Non ho sentito niente» e' una risposta, non un guasto: chi riceve un
    500 crede che il server sia rotto e non riprova."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: True)
    monkeypatch.setattr(
        servizio_modulo.whisper,
        "trascrivi",
        lambda audio, modello, lingua: "Sottotitoli e revisione a cura di QTSS",
    )

    risposta = cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert risposta.status_code == 200
    assert risposta.json() == {"testo": "", "vuota": True}


def test_senza_il_motore_locale_la_rotta_risponde_conflitto(cliente_autenticato, monkeypatch):
    """409 e non 500: non e' un guasto, e' una condizione che si risolve
    installando qualcosa."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: False)

    risposta = cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert risposta.status_code == 409
    assert "faster-whisper" in risposta.json()["detail"]


def test_un_formato_non_gestito_e_un_errore_del_cliente(cliente_autenticato, con_motore):
    risposta = cliente_autenticato.post(
        "/api/voce/trascrivi", files=_file(tipo="video/mp4"), data={"tipo": "video/mp4"}
    )

    assert risposta.status_code == 400


def test_una_registrazione_troppo_lunga_viene_rifiutata(cliente_autenticato, con_motore):
    grande = b"\x00" * (dominio.DIMENSIONE_MASSIMA + 1024)

    risposta = cliente_autenticato.post("/api/voce/trascrivi", files=_file(grande))

    assert risposta.status_code == 400
    assert str(dominio.MEGABYTE_MASSIMI) in risposta.json()["detail"]


def test_il_testo_detto_non_finisce_nel_log(cliente_autenticato, monkeypatch):
    """E' cio' che una persona ha detto in casa sua. Nel log resta che una
    trascrizione c'e' stata, non cosa diceva.

    Il logger si sostituisce invece di leggere `caplog`: l'applicazione
    installa i propri gestori, e un `caplog` che non intercetta niente
    lascerebbe passare **qualunque** cosa venisse scritta. E' cosi' che questo
    test era scritto la prima volta, e non aveva nessun potere.
    """
    segreto = "la chiave di scorta e' sotto il vaso"
    scritte: list[str] = []

    class LoggerFinto:
        def info(self, messaggio, *argomenti):
            scritte.append(messaggio % argomenti if argomenti else messaggio)

        def __getattr__(self, _nome):
            return lambda *a, **k: None

    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
    monkeypatch.setattr(servizio_modulo.whisper, "caricato", lambda nome: True)
    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", lambda audio, modello, lingua: segreto)
    monkeypatch.setattr(rotte_voce, "logger", LoggerFinto())

    cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert scritte, "la rotta non scrive piu' niente: il test non guarda piu' niente"
    for riga in scritte:
        assert segreto not in riga, f"il testo detto e' finito nel log: {riga!r}"
