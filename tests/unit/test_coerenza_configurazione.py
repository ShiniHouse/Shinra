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
    """File Python che nominano il simbolo, esclusi quelli indicati.

    `config/secrets.py` va quasi sempre escluso: rendere un campo
    impostabile dall'ambiente non significa che qualcuno lo usi per cio'
    a cui serve. Un test che si dichiara soddisfatto a vuoto e' peggio di
    nessun test.
    """
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


def test_gli_argomenti_vietati_sono_applicati() -> None:
    """Risolto dalla issue #8: il filtro esiste ed e' applicato nell'agente."""
    assert occorrenze("restricted_topics", escludi=("user_manager.py",)), (
        "Nessun filtro sui contenuti per i minori: il profilo 'child' cambia "
        "solo il tono del prompt, non cio' a cui puo' accedere"
    )


def test_l_application_id_di_alexa_e_verificato() -> None:
    """Risolto dalla issue #4: /api/alexa confronta l'applicationId.

    Il marcatore xfail e' stato rimosso quando la verifica e' entrata in
    funzione — e' il segnale che il difetto e' chiuso, non solo dichiarato tale.
    """
    assert occorrenze("skill_id", escludi=("settings.py", "secrets.py")), (
        "settings.alexa.skill_id non e' letto da nessuna riga: /api/alexa non "
        "verifica da quale skill provenga la richiesta"
    )


def test_l_annuncio_su_echo_e_utilizzato() -> None:
    """Risolto dalla issue #11: il canale di consegna la usa per annunciare
    timer e promemoria scaduti su un dispositivo Echo."""
    assert occorrenze("speak_on_alexa", escludi=("ha_client.py",)), (
        "core/ha_client.py definisce speak_on_alexa() ma nessuno la chiama: "
        "l'assistente non puo' parlare spontaneamente su un dispositivo Echo"
    )


def test_il_segreto_di_sessione_e_utilizzato() -> None:
    """Risolto dalla issue #6: i token di sessione sono firmati con esso."""
    assert occorrenze(
        "session_secret", escludi=("settings.py", "secrets.py")
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


# ------------------------------------------------- la configurazione ricaricata


MODULI_CHE_IMPORTANO_SETTINGS = (
    "server.sicurezza",
    "server.routes_admin",
    "core.agent",
    "core.consegna",
    "config.prompt_templates",
    "integrations.alexa.skill_handler",
)


def test_c_e_una_sola_configurazione_per_tutti() -> None:
    """Ogni `from config.settings import settings` deve guardare lo stesso oggetto.

    Se `reload_settings()` ne creasse uno nuovo, questi moduli resterebbero
    legati al vecchio: dopo un salvataggio dal pannello impostazioni
    leggerebbero i valori di prima fino al riavvio del servizio. E'
    esattamente il difetto REL-04 (issue #9) in un altro punto del codice.
    """
    import importlib

    from config import settings as modulo

    for nome in MODULI_CHE_IMPORTANO_SETTINGS:
        m = importlib.import_module(nome)
        assert (
            m.settings is modulo.settings
        ), f"{nome} ha una copia della configurazione invece di quella condivisa"


def test_dopo_un_ricarico_i_moduli_vedono_i_valori_nuovi(monkeypatch) -> None:
    """La prova che conta: cambiare la configurazione arriva a chi la usa."""
    from config import settings as modulo
    from server import sicurezza

    nome_originale = modulo.settings.assistant.name

    ricaricato = modulo.load_config()
    ricaricato.assistant.name = "NomeDiProva"
    ricaricato.security.auth_enabled = not modulo.settings.security.auth_enabled
    monkeypatch.setattr(modulo, "load_config", lambda: ricaricato)

    try:
        modulo.reload_settings()
        assert sicurezza.settings is modulo.settings
        assert sicurezza.settings.assistant.name == "NomeDiProva"
        assert sicurezza.settings.security.auth_enabled == ricaricato.security.auth_enabled
    finally:
        monkeypatch.undo()
        modulo.reload_settings()

    assert modulo.settings.assistant.name == nome_originale


def test_le_dipendenze_sono_dichiarate_in_un_posto_solo() -> None:
    """requirements.txt non deve elencare pacchetti: deve rimandare a pyproject.

    Quando i due elenchi erano separati, il secondo e' rimasto indietro:
    mancavano cryptography, apscheduler, sqlalchemy e pydantic-settings, e
    chi seguiva il README otteneva un'installazione che non partiva. Un
    elenco che va tenuto allineato a mano prima o poi non lo e' piu'.
    """
    righe = (RADICE / "requirements.txt").read_text(encoding="utf-8").splitlines()
    dichiarate = [r.strip() for r in righe if r.strip() and not r.strip().startswith("#")]
    assert dichiarate == ["-e ."], (
        "requirements.txt elenca dipendenze per conto suo: "
        f"{dichiarate}. Devono stare solo in pyproject.toml"
    )
