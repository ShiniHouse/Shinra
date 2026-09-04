"""Nessun segreto deve poter finire in un file versionato.

E' l'invariante della issue #07: `config/config.yaml` era tracciato da git e
riceveva il token di Home Assistant a ogni salvataggio dalle impostazioni.
Questi test impediscono che la situazione si ripresenti.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from config import secrets as segreti
from config.settings import AppConfig, migra_segreti_su_env, save_config, verifica_configurazione

RADICE = Path(__file__).resolve().parent.parent.parent
# Ha la forma di un JWT perche' il test deve somigliare al caso reale.
TOKEN_FINTO = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.finto-token-di-prova.xxxxxxxxxxxx"  # pragma: allowlist secret
)


@pytest.fixture()
def ambiente_isolato(tmp_path, monkeypatch):
    """Reindirizza .env e config.yaml in una cartella temporanea."""
    env = tmp_path / ".env"
    cfg = tmp_path / "config.yaml"
    monkeypatch.setattr(segreti, "ENV_PATH", env)
    import config.settings as impostazioni

    monkeypatch.setattr(impostazioni, "CONFIG_PATH", cfg)
    for variabile, _ in segreti.CAMPI_DA_AMBIENTE.values():
        monkeypatch.delenv(variabile, raising=False)
    return env, cfg


# ---------------------------------------------------------------- invariante


def test_il_repository_non_traccia_file_sensibili() -> None:
    """Il controllo che la CI esegue, disponibile anche in locale."""
    vietati = [
        "config/config.yaml",
        ".env",
        "data/users.json",
        "data/knowledge.json",
        "data/device_aliases.json",
        "data/modes.json",
        "data/sources.json",
    ]
    tracciati = [
        f
        for f in vietati
        if subprocess.run(
            ["git", "ls-files", "--error-unmatch", f],
            cwd=RADICE,
            capture_output=True,
        ).returncode
        == 0
    ]
    assert not tracciati, f"File con dati sensibili tracciati da git: {tracciati}"


def test_salvare_le_impostazioni_non_scrive_segreti_nello_yaml(ambiente_isolato) -> None:
    env, cfg = ambiente_isolato

    config = AppConfig()
    config.home_assistant.token = TOKEN_FINTO
    config.security.admin_pin = "1234"
    config.security.session_secret = "un-segreto-qualunque"
    config.assistant.name = "Kyra"
    save_config(config)

    scritto = cfg.read_text(encoding="utf-8")
    for segreto in (TOKEN_FINTO, "1234", "un-segreto-qualunque"):
        assert segreto not in scritto, f"{segreto!r} e' finito in config.yaml"

    # I valori non sensibili restano dove ci si aspetta.
    dati = yaml.safe_load(scritto)
    assert dati["assistant"]["name"] == "Kyra"

    # I segreti finiscono in .env.
    contenuto_env = env.read_text(encoding="utf-8")
    assert TOKEN_FINTO in contenuto_env
    assert "SHINRA_ADMIN_PIN=1234" in contenuto_env


def test_il_file_env_e_leggibile_solo_dal_proprietario(ambiente_isolato) -> None:
    env, _ = ambiente_isolato
    segreti.scrivi({"SHINRA_HA_TOKEN": TOKEN_FINTO})
    assert (env.stat().st_mode & 0o077) == 0, "il file .env e' leggibile da altri utenti"


# ---------------------------------------------------------------- precedenza


def test_l_ambiente_ha_la_precedenza_sul_file(ambiente_isolato, monkeypatch) -> None:
    segreti.scrivi({"SHINRA_HA_TOKEN": "valore-da-file"})
    assert segreti.leggi("SHINRA_HA_TOKEN") == "valore-da-file"

    monkeypatch.setenv("SHINRA_HA_TOKEN", "valore-da-ambiente")
    assert segreti.leggi("SHINRA_HA_TOKEN") == "valore-da-ambiente"


def test_scrivere_conserva_le_altre_chiavi_e_i_commenti(ambiente_isolato) -> None:
    env, _ = ambiente_isolato
    env.write_text("# un commento\nALTRA_COSA=intatta\nSHINRA_HA_TOKEN=vecchio\n", encoding="utf-8")

    segreti.scrivi({"SHINRA_HA_TOKEN": "nuovo"})

    contenuto = env.read_text(encoding="utf-8")
    assert "# un commento" in contenuto
    assert "ALTRA_COSA=intatta" in contenuto
    assert "SHINRA_HA_TOKEN=nuovo" in contenuto
    assert "vecchio" not in contenuto


# ---------------------------------------------------------------- migrazione


def test_migra_i_segreti_rimasti_nello_yaml(ambiente_isolato) -> None:
    env, cfg = ambiente_isolato
    cfg.write_text(
        yaml.safe_dump(
            {
                "home_assistant": {"enabled": True, "token": TOKEN_FINTO},
                "assistant": {"name": "Kyra"},
            }
        ),
        encoding="utf-8",
    )

    migrati = migra_segreti_su_env()

    assert "SHINRA_HA_TOKEN" in migrati
    assert TOKEN_FINTO in env.read_text(encoding="utf-8")
    assert TOKEN_FINTO not in cfg.read_text(encoding="utf-8")
    # Il resto della configurazione non viene toccato.
    assert yaml.safe_load(cfg.read_text(encoding="utf-8"))["assistant"]["name"] == "Kyra"


def test_la_migrazione_e_idempotente(ambiente_isolato) -> None:
    _, cfg = ambiente_isolato
    cfg.write_text(yaml.safe_dump({"home_assistant": {"token": TOKEN_FINTO}}), encoding="utf-8")
    assert migra_segreti_su_env()
    assert migra_segreti_su_env() == []


def test_il_segnaposto_non_viene_migrato(ambiente_isolato) -> None:
    env, cfg = ambiente_isolato
    cfg.write_text(
        yaml.safe_dump({"home_assistant": {"token": "INSERISCI_QUI_IL_TUO_LONG_LIVED_ACCESS_TOKEN"}}),
        encoding="utf-8",
    )
    assert migra_segreti_su_env() == []
    assert not env.exists()


# ------------------------------------------------------- controlli d'avvio


def test_segnala_il_token_mancante() -> None:
    config = AppConfig()
    config.home_assistant.enabled = True
    config.home_assistant.token = ""
    problemi = verifica_configurazione(config)
    assert any("token" in p.lower() for p in problemi)


def test_non_segnala_nulla_quando_e_tutto_a_posto() -> None:
    config = AppConfig()
    config.home_assistant.enabled = False
    config.alexa.enabled = False
    config.security.auth_enabled = True
    config.server.debug = False
    assert verifica_configurazione(config) == []


def test_segnala_l_autenticazione_disattivata() -> None:
    """Spegnere l'autenticazione apre la casa a chiunque sia sulla rete:
    deve restare una scelta visibile, non un valore che passa inosservato."""
    config = AppConfig()
    config.home_assistant.enabled = False
    config.alexa.enabled = False
    config.server.debug = False
    config.security.auth_enabled = False
    assert any("autenticazione" in p.lower() for p in verifica_configurazione(config))


def test_segnala_il_debug_esposto_in_rete() -> None:
    config = AppConfig()
    config.home_assistant.enabled = False
    config.alexa.enabled = False
    config.server.debug = True
    config.server.host = "0.0.0.0"
    assert any("debug" in p.lower() for p in verifica_configurazione(config))


def test_il_segreto_di_sessione_non_ha_un_valore_predefinito() -> None:
    """Un segreto uguale per tutte le installazioni non e' un segreto."""
    assert not AppConfig().security.session_secret
