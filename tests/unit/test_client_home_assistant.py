"""Il client Home Assistant deve essere uno solo, e deve seguire la configurazione.

`core/tools/ha_tools.py` costruiva il proprio client passando URL e token come
valori al momento dell'import, congelandoli. Ogni altro punto del progetto
usava le property dinamiche. Chi correggeva l'indirizzo dalle impostazioni
vedeva il pannello diagnostico diventare verde — quello usa un client
dinamico — mentre i comandi ai dispositivi continuavano a fallire contro il
vecchio indirizzo, fino al riavvio del servizio.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import core.ha_client as modulo
from config.settings import AppConfig
from core.ha_client import HomeAssistantClient, client_home_assistant


@pytest.fixture(autouse=True)
def _client_pulito():
    modulo._client_condiviso = None
    yield
    modulo._client_condiviso = None


@pytest.fixture()
def configurazione(monkeypatch) -> AppConfig:
    """Sostituisce la sorgente che il client legge davvero.

    Le property rileggono la configurazione a ogni accesso — oggi da disco,
    dalla v0.2.0 da una cache (issue #14). Il test agisce su quella sorgente,
    non sull'oggetto in memoria, altrimenti verificherebbe qualcosa che il
    codice non guarda.
    """
    cfg = AppConfig()
    monkeypatch.setattr(modulo, "reload_settings", lambda: cfg)
    return cfg


def test_e_sempre_lo_stesso_client() -> None:
    assert client_home_assistant() is client_home_assistant()


def test_cambiare_indirizzo_ha_effetto_senza_riavviare(configurazione: AppConfig) -> None:
    """Il difetto REL-04, nella sua forma osservabile."""
    configurazione.home_assistant.url = "http://casa-vecchia.local:8123"
    client = client_home_assistant()
    assert client.base_url == "http://casa-vecchia.local:8123"

    configurazione.home_assistant.url = "http://casa-nuova.local:8123"
    assert (
        client.base_url == "http://casa-nuova.local:8123"
    ), "il client ha congelato l'indirizzo: e' esattamente REL-04"


def test_anche_il_token_segue_la_configurazione(configurazione: AppConfig) -> None:
    configurazione.home_assistant.token = "token-primo"
    client = client_home_assistant()
    assert client.headers["Authorization"] == "Bearer token-primo"

    configurazione.home_assistant.token = "token-secondo"
    assert client.headers["Authorization"] == "Bearer token-secondo"


def test_un_client_costruito_con_valori_li_congela(configurazione: AppConfig) -> None:
    """La dimostrazione del difetto, conservata come test.

    E' il comportamento che aveva `ha_tools.py`. Il costruttore continua ad
    accettare i valori — servono nei test — ma nessun modulo
    dell'applicazione deve usarli, e il test successivo lo verifica.
    """
    congelato = HomeAssistantClient(base_url="http://fisso.local:8123")
    configurazione.home_assistant.url = "http://cambiato.local:8123"
    assert congelato.base_url == "http://fisso.local:8123"


def test_nessun_modulo_costruisce_un_client_con_valori_fissi() -> None:
    """La guardia contro il ripetersi del difetto."""
    radice = Path(__file__).resolve().parent.parent.parent
    colpevoli = []
    for cartella in ("core", "server", "integrations"):
        for percorso in (radice / cartella).rglob("*.py"):
            if "__pycache__" in percorso.parts:
                continue
            for chiamata in re.findall(r"HomeAssistantClient\([^)]*\)", percorso.read_text(encoding="utf-8")):
                if "base_url" in chiamata or "token" in chiamata:
                    colpevoli.append(f"{percorso.relative_to(radice)}: {chiamata}")

    assert not colpevoli, (
        "Client Home Assistant costruiti con valori congelati:\n  "
        + "\n  ".join(colpevoli)
        + "\nUsa client_home_assistant()."
    )


def test_la_connessione_viene_riusata() -> None:
    """Ogni metodo apriva il proprio client: una connessione TCP e un
    handshake nuovi per ogni lampadina accesa."""
    client = HomeAssistantClient()
    assert client._connessione(5.0) is client._connessione(5.0)


@pytest.mark.asyncio
async def test_chiudere_libera_la_connessione() -> None:
    client = HomeAssistantClient()
    connessione = client._connessione(5.0)
    await client.chiudi()
    assert connessione.is_closed
    # Dopo la chiusura se ne ottiene una nuova, invece di un errore.
    assert not client._connessione(5.0).is_closed
    await client.chiudi()
