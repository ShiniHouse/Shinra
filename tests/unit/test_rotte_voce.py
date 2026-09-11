"""La rotta che riceve l'audio del microfono.

Esiste perche' fino alla issue #31 quell'audio andava a Google. Adesso arriva
qui e non esce.

Riferimento: issue #31.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from shinra.api import routes_voce as rotte_voce
from shinra.api.app import app
from shinra.domain import trascrizione as dominio
from shinra.services import trascrizione as servizio_modulo


@pytest.fixture
def con_motore(monkeypatch):
    """Il motore locale c'e' e trascrive quello che gli si dice di trascrivere."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
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


def test_il_silenzio_torna_come_niente_non_come_errore(cliente_autenticato, monkeypatch):
    """«Non ho sentito niente» e' una risposta, non un guasto: chi riceve un
    500 crede che il server sia rotto e non riprova."""
    monkeypatch.setattr(servizio_modulo.whisper, "disponibile", lambda: True)
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
    monkeypatch.setattr(servizio_modulo.whisper, "trascrivi", lambda audio, modello, lingua: segreto)
    monkeypatch.setattr(rotte_voce, "logger", LoggerFinto())

    cliente_autenticato.post("/api/voce/trascrivi", files=_file())

    assert scritte, "la rotta non scrive piu' niente: il test non guarda piu' niente"
    for riga in scritte:
        assert segreto not in riga, f"il testo detto e' finito nel log: {riga!r}"
