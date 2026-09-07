"""La configurazione non si rilegge dal disco a ogni domanda.

`reload_settings()` apriva e analizzava `config.yaml` **dentro** le property
`base_url`, `model`, `timeout` di OllamaClient e `token`, `headers` di
HomeAssistantClient. Un singolo turno di chat produceva decine di letture
sincrone dal filesystem, dentro l'event loop asincrono.

Su un SSD non si sente. E' esattamente il genere di blocco che non si vede
finche' non lo si cerca, e che degrada tutto quando il carico cresce.
Riferimento: REL-06, issue #14.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def letture_dal_disco(monkeypatch):
    """Conta quante volte qualcuno apre config.yaml."""
    from config import settings as modulo

    conteggio = {"letture": 0}
    originale = modulo._leggi_yaml

    def contando():
        conteggio["letture"] += 1
        return originale()

    monkeypatch.setattr(modulo, "_leggi_yaml", contando)
    return conteggio


# --------------------------------------------- niente disco durante una chat


def test_chiedere_indirizzo_e_modello_non_tocca_il_disco(letture_dal_disco):
    from core.ollama_client import OllamaClient

    cliente = OllamaClient()
    for _ in range(20):
        _ = cliente.base_url
        _ = cliente.model
        _ = cliente.timeout

    assert letture_dal_disco["letture"] == 0


def test_il_client_home_assistant_non_tocca_il_disco(letture_dal_disco):
    from core.ha_client import client_home_assistant

    ha = client_home_assistant()
    for _ in range(20):
        _ = ha.base_url
        _ = ha.headers

    assert letture_dal_disco["letture"] == 0


async def test_una_chiamata_al_modello_e_alla_casa_non_legge_la_configurazione(letture_dal_disco):
    """Il criterio di accettazione, sul percorso che davvero le usava.

    Attenzione al test facile: un comando risolto dal percorso rapido degli
    alias non tocca ne' Ollama ne' Home Assistant, quindi non leggeva la
    configurazione nemmeno prima della correzione — un test cosi' sarebbe
    passato anche col difetto presente. Qui si chiamano i due client veri,
    con l'HTTP simulato. Misurato sul codice precedente: cinque letture di
    config.yaml per una sola chiamata al modello piu' un riepilogo della
    casa, e il ciclo dei tool di un turno puo' ripeterle quattro volte.
    """
    import httpx
    import respx

    from core.ha_client import HomeAssistantClient
    from core.ollama_client import OllamaClient

    cliente = OllamaClient()
    ha = HomeAssistantClient()

    with respx.mock(assert_all_called=False) as finto:
        finto.post(url__regex=r".*/api/chat").mock(
            return_value=httpx.Response(200, json={"message": {"content": "ciao"}})
        )
        finto.get(url__regex=r".*/api/states").mock(return_value=httpx.Response(200, json=[]))

        letture_dal_disco["letture"] = 0
        await cliente.chat([{"role": "user", "content": "ciao"}])
        await ha.get_relevant_entities_summary()

    await ha.chiudi()
    assert letture_dal_disco["letture"] == 0


# ------------------------------------------------- ma resta sempre corrente


def test_cambiare_la_configurazione_ha_effetto_subito():
    """Togliere la rilettura da disco non deve reintrodurre REL-04, cioe' un
    valore congelato all'avvio. I client leggono l'oggetto condiviso, che il
    salvataggio aggiorna al suo posto."""
    from config.settings import settings
    from core.ollama_client import OllamaClient

    cliente = OllamaClient()
    originale = settings.llm.ollama_url
    try:
        settings.llm.ollama_url = "http://nuovo-server:11434"
        assert cliente.base_url == "http://nuovo-server:11434"
    finally:
        settings.llm.ollama_url = originale


def test_un_salvataggio_arriva_ai_client(monkeypatch):
    """Il percorso completo: si salva, si ricarica, e i client lo vedono."""
    from config import settings as modulo
    from core.ha_client import client_home_assistant

    aggiornata = modulo.load_config()
    aggiornata.home_assistant.url = "http://casa-nuova.local:8123"
    monkeypatch.setattr(modulo, "load_config", lambda: aggiornata)

    try:
        modulo.reload_settings()
        assert client_home_assistant().base_url == "http://casa-nuova.local:8123"
    finally:
        monkeypatch.undo()
        modulo.reload_settings()


# ------------------------------------------------------- perche' non torni


def test_nessun_modulo_del_percorso_di_richiesta_rilegge_il_disco():
    """`reload_settings()` puo' comparire solo dove la rilettura e' voluta:
    in config/settings.py, che la definisce, e nel pannello impostazioni, che
    deve mostrare cosa c'e' davvero sul file. Ovunque altro e' il difetto."""
    consentiti = {"config/settings.py", "server/routes_admin.py"}
    colpevoli = []
    for cartella in ("core", "server", "config", "integrations"):
        for percorso in (RADICE / cartella).rglob("*.py"):
            if "__pycache__" in percorso.parts:
                continue
            relativo = percorso.relative_to(RADICE).as_posix()
            if relativo in consentiti:
                continue
            if "reload_settings" in percorso.read_text(encoding="utf-8"):
                colpevoli.append(relativo)

    assert colpevoli == [], (
        f"{colpevoli} rilegge la configurazione da disco: usa l'oggetto "
        "condiviso `settings`, che il salvataggio aggiorna gia'"
    )
