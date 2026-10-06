"""Il service worker puo' controllare la pagina (issue #29).

Il worker sta in `/static/sw.js` e la pagina in `/`. Per regola un worker controlla solo il proprio percorso: con lo
scope predefinito (`/static/`) `navigator.serviceWorker.ready` non si risolve **mai** per una pagina in `/`, e le
notifiche push non si potevano attivare su nessun dispositivo vero — mentre il test del browser, che fingeva il worker,
passava. La deroga e' un'intestazione che il server deve mandare, e che nessun test vedeva perche' nessuno la chiedeva.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from shinra.api.app import app

RADICE = Path(__file__).resolve().parent.parent.parent


def test_il_service_worker_puo_controllare_tutta_l_applicazione():
    risposta = TestClient(app).get("/static/sw.js")

    assert risposta.status_code == 200
    assert risposta.headers.get("service-worker-allowed") == "/"


def test_gli_altri_file_statici_non_ricevono_la_deroga():
    risposta = TestClient(app).get("/static/js/principale.js")

    assert risposta.status_code == 200
    assert "service-worker-allowed" not in risposta.headers


def test_la_pagina_registra_il_worker_con_lo_scope_della_radice():
    """Senza `scope: '/'` la deroga del server non serve: la registrazione resterebbe sotto `/static/`."""
    sorgente = (RADICE / "web" / "static" / "js" / "impostazioni.js").read_text(encoding="utf-8")

    assert "register('/static/sw.js', { scope: '/' })" in " ".join(sorgente.split())
