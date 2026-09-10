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

from shinra import versione

RADICE = Path(__file__).resolve().parent.parent.parent


def test_il_numero_viene_da_pyproject_e_da_nessun_altro_posto():
    """Scriverlo in due posti significa, prima o poi, scriverlo diverso."""
    testo = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    dichiarata = re.search(r'^version = "([^"]+)"', testo, re.MULTILINE).group(1)

    assert versione.numero() == dichiarata


def test_il_readme_non_annuncia_una_versione_che_non_esiste():
    """Il README diceva «beta 0.1.0» mentre il progetto era alla `0.4.0`, e la
    `0.2.0` e la `0.3.0` erano state rilasciate nel frattempo.

    E' la porta d'ingresso del progetto: chi la legge non ha modo di sapere
    che e' vecchia, e vale la stessa regola scritta in cima a questo file — un
    numero sbagliato e' peggio di nessun numero. La guardia e' minima di
    proposito: non pretende che il README racconti la storia delle release,
    pretende che la sezione «Stato del progetto» nomini la versione a cui il
    progetto e' arrivato.
    """
    testo = (RADICE / "README.md").read_text(encoding="utf-8")
    corrente = ".".join(versione.numero().split(".")[:2])

    inizio = testo.find("## 🚧 Stato del progetto")
    assert inizio != -1, "il README non ha piu' una sezione «Stato del progetto»"
    sezione = testo[inizio : testo.find("\n## ", inizio + 1)]

    # Solo dentro quella sezione, e solo le versioni scritte per intero fra
    # apici inversi: `1.0.0` compare altrove come meta della roadmap, ed e'
    # giusto che ci sia. Qui la domanda e' un'altra — questa pagina sa a che
    # punto siamo?
    citate = set(re.findall(r"`(\d+\.\d+\.\d+)`", sezione))
    assert citate, "la sezione «Stato del progetto» non dichiara nessuna versione"

    minori = {".".join(v.split(".")[:2]) for v in citate}
    assert corrente in minori, (
        f"il README parla delle versioni {sorted(minori)} mentre il progetto " f"e' alla `{corrente}`"
    )

    # E deve dire qual e' l'ultima **rilasciata**, che non e' quella in
    # lavorazione: chi legge decide da li' cosa puo' installare. Le note di
    # rilascio sono la fonte, perche' esistono nel repository anche quando i
    # tag non ci sono — in CI il clone e' superficiale.
    rilasciate = sorted(
        (p.stem.lstrip("v") for p in (RADICE / "docs" / "release").glob("v*.md")),
        key=lambda v: tuple(int(p) for p in v.split(".")),
    )
    if rilasciate:
        ultima = rilasciate[-1]
        assert ultima in citate, (
            f"la sezione «Stato del progetto» non nomina la `{ultima}`, che e' "
            f"l'ultima release: dice {sorted(citate)}"
        )


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
    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.config.settings import settings
    from shinra.services.user_manager import user_manager

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


def test_metadati_sorpassati_non_ingannano_il_numero(monkeypatch):
    """Il difetto che ha fatto dire «0.1.0» a un server aggiornato da un minuto.

    `importlib.metadata` cerca lungo `sys.path`, e il servizio parte dalla
    cartella del progetto — che viene prima di site-packages. Un
    `shinra.egg-info` lasciato li' da un'installazione di mesi prima, quando
    il codice non stava ancora sotto `src/`, veniva trovato per primo.

    Il badge mostrava il commit giusto accanto alla versione sbagliata: la
    piu' insidiosa delle mezze verita', perche' sembra informazione.
    """
    from shinra import versione

    def metadati_bugiardi(_nome: str) -> str:
        return "0.1.0"

    monkeypatch.setattr("importlib.metadata.version", metadati_bugiardi)
    versione.numero.cache_clear()
    try:
        letto = versione.numero()
    finally:
        versione.numero.cache_clear()

    atteso = re.search(
        r'^version\s*=\s*"([^"]+)"', (RADICE / "pyproject.toml").read_text(encoding="utf-8"), re.M
    ).group(1)
    assert letto == atteso != "0.1.0"


def test_numero_e_commit_vengono_dalla_stessa_cartella():
    """Due numeri da fonti diverse prima o poi si contraddicono, ed e'
    esattamente cio' che e' successo: il commit dal repository, il numero da
    metadati di un'altra installazione."""
    from shinra import percorsi, versione

    assert (percorsi.RADICE / "pyproject.toml").exists()
    assert versione._dal_progetto() == versione.numero()
