"""Il servizio deve potersi fermare.

Dal log di casa, 11 settembre: novanta secondi di attesa a ogni fermata e
poi `SIGKILL`. Non un caso isolato — **ogni** riavvio, quindi ogni
aggiornamento.

Un SIGKILL non e' una fermata, e' un'esecuzione: salta tutto cio' che il
`lifespan` fa dopo lo `yield`. Lo scheduler non viene fermato, il motore
di regole resta a meta', la connessione agli eventi di Home Assistant non
viene chiusa, e qualunque lavoro in sottofondo muore dov'e'.

La causa era la rotta `/ws/eventi`, che parlava e non ascoltava mai.
Uvicorn, per fermarsi, chiede a ogni connessione di chiudersi e poi
aspetta che se ne vada, senza scadenza. La richiesta di chiusura arriva
alla rotta come un messaggio da leggere: nessuno lo leggeva.

Questi test fanno partire un server vero e gli mandano un SIGTERM,
perche' e' l'unico modo di misurare quello che succede davvero. Il primo
e' il controllo: senza connessioni aperte la fermata e' sempre stata
sana, e se fallisse vorrebbe dire che il guasto sta altrove.

Riferimento: issue #118.
"""

from __future__ import annotations

import base64
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from shinra import avvio, percorsi

# Quanto puo' durare una fermata sana. Misurata: due decimi di secondo.
# Il tetto e' largo dieci volte per non diventare un test che ogni tanto
# fallisce su una macchina carica, e resta comunque lontanissimo dai
# novanta secondi oltre i quali systemd manda il SIGKILL.
SECONDI_CONCESSI = 20.0


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _risponde(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        try:
            s.connect(("127.0.0.1", porta))
            return True
        except OSError:
            return False


@pytest.fixture(scope="module")
def casa_finta(tmp_path_factory) -> Path:
    """Una radice di progetto usa e getta, senza PIN.

    Senza almeno un PIN l'autenticazione si spegne da sola: e' l'unico
    modo di aprire la websocket in un test senza toccare credenziali.
    """
    radice = tmp_path_factory.mktemp("casa")
    (radice / "pyproject.toml").write_text("[progetto]\n", encoding="utf-8")
    shutil.copytree(percorsi.MIGRAZIONI, radice / "migrazioni")
    for nome in ("alembic.ini",):
        origine = percorsi.RADICE / nome
        if origine.exists():
            shutil.copyfile(origine, radice / nome)

    (radice / "config").mkdir()
    esempio = (percorsi.CONFIGURAZIONE / "config.example.yaml").read_text(encoding="utf-8")
    assert "auth_enabled: true" in esempio, "la configurazione d'esempio e' cambiata: rileggi questo test"
    (radice / "config" / "config.yaml").write_text(
        esempio.replace("auth_enabled: true", "auth_enabled: false"), encoding="utf-8"
    )
    return radice


def _quanto_ci_mette_a_fermarsi(casa: Path, con_websocket: bool, rete_di_sicurezza: bool = False) -> float:
    """Quanti secondi passano fra il SIGTERM e la morte del processo.

    `rete_di_sicurezza` accende il `timeout_graceful_shutdown` che sta in
    `avvio.py`. Qui e' **spento** di proposito: con la rete accesa una
    rotta che ignora la chiusura fallisce comunque entro dieci secondi, e
    un test che non distingue «si chiude» da «viene tagliata» non sta
    provando la rotta, sta provando la rete. Spenta, la differenza e' fra
    due decimi di secondo e mai.
    """
    porta = _porta_libera()
    comando = [
        sys.executable,
        "-m",
        "uvicorn",
        "shinra.api.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(porta),
        "--log-level",
        "warning",
    ]
    if rete_di_sicurezza:
        comando += ["--timeout-graceful-shutdown", str(avvio.SECONDI_PER_CHIUDERE)]
    processo = subprocess.Popen(
        comando,
        env={**os.environ, "SHINRA_RADICE": str(casa), "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    cliente = None
    try:
        scadenza = time.monotonic() + 60
        while not _risponde(porta):
            if time.monotonic() > scadenza or processo.poll() is not None:
                pytest.fail("il server non e' partito")
            time.sleep(0.2)

        if con_websocket:
            # L'handshake a mano, poi silenzio: e' esattamente cio' che fa
            # la dashboard, che ascolta e non parla mai.
            cliente = socket.create_connection(("127.0.0.1", porta), timeout=5)
            chiave = base64.b64encode(b"0123456789abcdef").decode()
            cliente.sendall(
                f"GET /ws/eventi HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{porta}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {chiave}\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n".encode()
            )
            risposta = cliente.recv(4096)
            assert b" 101 " in risposta, f"la websocket non si e' aperta: {risposta[:120]!r}"
            time.sleep(0.5)

        inizio = time.monotonic()
        processo.send_signal(signal.SIGTERM)
        try:
            processo.wait(timeout=SECONDI_CONCESSI)
        except subprocess.TimeoutExpired:
            return float("inf")
        return time.monotonic() - inizio
    finally:
        if cliente is not None:
            cliente.close()
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM e i gruppi di processi sono di unix")
def test_senza_connessioni_aperte_il_servizio_si_ferma_subito(casa_finta):
    """Il controllo. Se fallisse questo, il guasto non sarebbe la websocket."""
    durata = _quanto_ci_mette_a_fermarsi(casa_finta, con_websocket=False)
    assert durata < SECONDI_CONCESSI, f"la fermata ha richiesto {durata:.1f}s"


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM e i gruppi di processi sono di unix")
def test_una_dashboard_aperta_non_impedisce_la_fermata(casa_finta):
    """Il difetto della #118, misurato.

    Prima: con una sola websocket aperta il processo **non moriva** — oltre
    cento secondi, cioe' fino al SIGKILL. Dopo: due decimi di secondo, come
    senza.

    Una dashboard aperta in cucina non e' un caso limite: e' il caso
    normale, ed e' il motivo per cui succedeva a ogni riavvio.
    """
    durata = _quanto_ci_mette_a_fermarsi(casa_finta, con_websocket=True)
    assert durata < SECONDI_CONCESSI, (
        f"con una dashboard aperta la fermata ha richiesto {durata:.1f}s: "
        "il servizio non si accorge che gli e' stato chiesto di chiudere, "
        "e in casa finisce a SIGKILL dopo novanta secondi"
    )


@pytest.mark.skipif(os.name != "posix", reason="SIGTERM e i gruppi di processi sono di unix")
def test_la_rete_di_sicurezza_taglia_comunque(casa_finta, monkeypatch):
    """L'altra meta': anche se una rotta ignorasse la chiusura, si deve morire.

    La rotta di oggi e' a posto — lo prova il test qui sopra. Questo prova
    che se domani ne nascesse una sorda, il servizio si fermerebbe lo
    stesso entro i secondi dichiarati invece di aspettare il SIGKILL.

    Per provarlo serve una rotta sorda: si rimette per un attimo quella di
    prima, nella copia usa e getta, e si misura con la rete accesa.
    """
    sorda = casa_finta / "rotta_sorda.py"
    sorda.write_text(
        "import asyncio\n"
        "from shinra.api.app import app\n"
        "\n"
        "@app.websocket('/ws/sorda')\n"
        "async def sorda(websocket):\n"
        "    await websocket.accept()\n"
        "    while True:\n"
        "        await asyncio.sleep(3600)\n",
        encoding="utf-8",
    )
    durata = _quanto_ci_mette_a_fermarsi(casa_finta, con_websocket=True, rete_di_sicurezza=True)
    assert durata < SECONDI_CONCESSI, f"nemmeno la rete di sicurezza ha fermato il servizio: {durata:.1f}s"


def test_la_rete_di_sicurezza_e_dichiarata():
    """Un numero che nessuno passa a uvicorn non protegge niente."""
    sorgente = (percorsi.RADICE / "src" / "shinra" / "avvio.py").read_text(encoding="utf-8")
    assert (
        "timeout_graceful_shutdown=SECONDI_PER_CHIUDERE" in sorgente
    ), "la scadenza non arriva a uvicorn: senza, aspetta per sempre"
    assert 1 <= avvio.SECONDI_PER_CHIUDERE <= 30, (
        f"SECONDI_PER_CHIUDERE e' {avvio.SECONDI_PER_CHIUDERE}: una fermata sana ne impiega "
        "due decimi, e systemd spara il SIGKILL a novanta"
    )
