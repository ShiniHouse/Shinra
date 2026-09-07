"""La versione mostrata deve essere quella che gira davvero.

Un numero di versione sbagliato e' peggio di nessun numero: chi lo legge
smette di controllare e comincia a fidarsi. Riferimento: la pagina deve
rispondere a «a che versione siamo?» senza entrare in SSH sul server.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core import versione

RADICE = Path(__file__).resolve().parent.parent.parent


def test_il_numero_viene_da_pyproject_e_da_nessun_altro_posto():
    """Scriverlo in due posti significa, prima o poi, scriverlo diverso."""
    testo = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    dichiarata = re.search(r'^version = "([^"]+)"', testo, re.MULTILINE).group(1)

    assert versione.numero() == dichiarata


def test_la_descrizione_dice_se_non_siamo_su_una_release():
    """Fra un tag e il successivo passano decine di commit: mostrare solo il
    numero del tag su un server aggiornato su main sarebbe falso."""
    descritta = versione.descrizione()
    rev = versione.revisione()

    if rev.get("tag"):
        assert descritta == rev["tag"]
    elif rev.get("commit"):
        assert descritta.endswith(rev["commit"])
        assert descritta.startswith(versione.numero())
    else:
        assert descritta == versione.numero()


def test_senza_git_la_versione_si_ottiene_lo_stesso(monkeypatch):
    """Il codice puo' arrivare da un archivio senza cronologia — un pacchetto,
    uno zip. Non e' un motivo per non sapere che versione e'."""
    versione.revisione.cache_clear()
    monkeypatch.setattr(versione.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    try:
        assert versione.revisione() == {"commit": "", "ramo": "", "tag": ""}
        assert versione.descrizione() == versione.numero()
    finally:
        versione.revisione.cache_clear()


def test_lo_stato_del_sistema_riporta_la_versione(cliente_autenticato):
    risposta = cliente_autenticato.get("/api/status")

    assert risposta.status_code == 200
    assert risposta.json()["versione"]["descrizione"] == versione.descrizione()


def test_la_dashboard_mostra_la_versione(cliente_autenticato):
    pagina = cliente_autenticato.get("/").text

    assert 'id="badge-versione"' in pagina
    assert versione.descrizione() in pagina


def test_la_pagina_di_accesso_non_la_mostra():
    """Chi non e' entrato non deve sapere quale versione gira: e' la prima
    informazione utile a chi cerca una vulnerabilita' nota, ed e' inutile a
    chi deve solo digitare il PIN."""
    from config.settings import settings
    from core.user_manager import user_manager
    from server import sicurezza
    from server.app import app

    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    utente = user_manager.get_users()[0]
    user_manager.imposta_pin(utente.id, "482913")
    sicurezza.azzera_stato()
    try:
        with TestClient(app) as client:
            pagina = client.get("/")
            assert pagina.status_code == 401
            assert versione.descrizione() not in pagina.text
    finally:
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()


@pytest.mark.parametrize("campo", ["versione", "descrizione", "commit", "ramo", "tag"])
def test_il_dettaglio_ha_tutti_i_campi(campo):
    assert campo in versione.dettaglio()
