"""Verifica che ogni impostazione esposta all'utente abbia un consumatore.

La revisione tecnica ha individuato nove elementi che l'interfaccia o il file di
configurazione presentano come funzionanti e che nessuna riga di codice legge —
la «configurazione fantasma». Non producono errori: producono silenzio, il che
li rende piu' insidiosi di un difetto visibile.

Questi test sono il presidio che impedisce al fenomeno di ripetersi.
Riferimento: issue v0.3.0 #26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent
SORGENTI = [RADICE / "core", RADICE / "server", RADICE / "config", RADICE / "integrations"]


def occorrenze(simbolo: str, escludi: tuple[str, ...] = ()) -> list[str]:
    """File Python che nominano il simbolo, esclusi quelli indicati."""
    trovati = []
    for radice in SORGENTI:
        if not radice.is_dir():
            continue
        for percorso in radice.rglob("*.py"):
            if percorso.name in escludi or "__pycache__" in percorso.parts:
                continue
            if simbolo in percorso.read_text(encoding="utf-8"):
                trovati.append(str(percorso.relative_to(RADICE)))
    return trovati


@pytest.mark.xfail(
    strict=True,
    reason="Le fonti RSS configurabili non sono lette: news_search.py usa RSS_FEEDS scritto nel codice — issue v0.3.0 #26",
)
def test_le_fonti_rss_configurate_sono_usate() -> None:
    assert occorrenze("get_sources", escludi=("data_store.py", "routes_admin.py")), (
        "data/sources.json e il gestore fonti dell'interfaccia non hanno alcun effetto: "
        "core/tools/news_search.py usa un dizionario RSS_FEEDS scritto nel codice"
    )


@pytest.mark.xfail(
    strict=True,
    reason="preferred_news_categories e' salvato per ogni utente e mai letto — issue v0.3.0 #26",
)
def test_le_categorie_di_notizie_preferite_sono_usate() -> None:
    assert occorrenze("preferred_news_categories", escludi=("user_manager.py",)), (
        "Il campo e' salvato in users.json ma nessun codice lo consuma: "
        "il briefing notizie e' identico per tutti gli utenti"
    )


@pytest.mark.xfail(
    strict=True,
    reason="restricted_topics e' dichiarato nel profilo e mai applicato — issue v0.1.0 #08",
)
def test_gli_argomenti_vietati_sono_applicati() -> None:
    assert occorrenze("restricted_topics", escludi=("user_manager.py",)), (
        "Nessun filtro sui contenuti per i minori: il profilo 'child' cambia "
        "solo il tono del prompt, non cio' a cui puo' accedere"
    )


@pytest.mark.xfail(
    strict=True,
    reason="skill_id e' configurabile e mai confrontato: l'endpoint Alexa accetta chiunque — issue v0.1.0 #04",
)
def test_l_application_id_di_alexa_e_verificato() -> None:
    assert occorrenze("skill_id", escludi=("settings.py",)), (
        "settings.alexa.skill_id non e' letto da nessuna riga: /api/alexa non "
        "verifica da quale skill provenga la richiesta"
    )


@pytest.mark.xfail(
    strict=True,
    reason="speak_on_alexa e' definita e mai chiamata — collegata in v0.2.0 #11",
)
def test_l_annuncio_su_echo_e_utilizzato() -> None:
    assert occorrenze("speak_on_alexa", escludi=("ha_client.py",)), (
        "core/ha_client.py definisce speak_on_alexa() ma nessuno la chiama: "
        "l'assistente non puo' parlare spontaneamente su un dispositivo Echo"
    )


@pytest.mark.xfail(
    strict=True,
    reason="session_secret e' dichiarato e mai usato: i token non sono firmati — issue v0.1.0 #06",
)
def test_il_segreto_di_sessione_e_utilizzato() -> None:
    assert occorrenze(
        "session_secret", escludi=("settings.py",)
    ), "I token di sessione sono generati con secrets.token_hex e non firmati"


def test_nessuna_dipendenza_dichiarata_e_inutilizzata() -> None:
    """duckduckgo-search e' in requirements.txt e non e' importata da nessuna parte.

    Questo test resta verde perche' verifica la coerenza di pyproject.toml, che
    e' il file di riferimento dalla v0.1.0. requirements.txt viene ripulito
    nella issue v0.1.0 #10.
    """
    pyproject = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    assert "duckduckgo" not in pyproject, (
        "duckduckgo-search non e' importata da nessun modulo: non deve comparire " "fra le dipendenze"
    )
