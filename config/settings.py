"""Caricamento della configurazione.

I valori non sensibili vivono in `config/config.yaml`; i segreti stanno
nell'ambiente o in `.env`, che non e' versionato (vedi `config/secrets.py`).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

import yaml
from pydantic import BaseModel, Field

from config import secrets as segreti

logger = logging.getLogger("Shinra.Settings")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
CONFIG_EXAMPLE_PATH = BASE_DIR / "config" / "config.example.yaml"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False


class LLMConfig(BaseModel):
    ollama_url: str = "http://localhost:11434"
    model: str = "gemma2:9b"
    temperature: float = 0.4
    timeout_seconds: int = 60
    max_tokens: int = 150


class HomeAssistantConfig(BaseModel):
    enabled: bool = True
    url: str = "http://homeassistant.local:8123"
    token: str = ""
    alexa_media_player_entity: Optional[str] = ""


class AlexaConfig(BaseModel):
    enabled: bool = True
    skill_id: Optional[str] = ""
    invocation_name: str = "kyra"


class AssistantConfig(BaseModel):
    name: str = "Kyra"
    language: str = "it"
    default_city: str = "Roma"


class SecurityConfig(BaseModel):
    # Chiusa per difetto. Un hub che comanda luci, prese e clima non puo'
    # nascere aperto a chiunque sia sulla rete: al primo avvio senza PIN ne
    # viene generato uno e scritto nel log, cosi' il proprietario entra
    # comunque. Vedi server/app.py::_prepara_accesso.
    auth_enabled: bool = True
    admin_pin: Optional[str] = ""
    # Nessun valore predefinito: un segreto uguale per tutte le installazioni
    # non e' un segreto. Viene generato al primo avvio e scritto in .env.
    session_secret: Optional[str] = ""
    protect_dashboard: bool = True
    # Indirizzi dei reverse proxy di cui fidarsi per leggere X-Forwarded-For.
    # Vuoto significa: non fidarsi di nessuno, e usare l'indirizzo osservato.
    # Un'intestazione X-Forwarded-For arriva dal client e chiunque puo'
    # scriverla: fidarsene senza sapere da dove viene la richiesta permette a
    # chi attacca di aggirare la limitazione dei tentativi cambiando un valore.
    trusted_proxies: List[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    alexa: AlexaConfig = Field(default_factory=AlexaConfig)
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


# --------------------------------------------------------------------------
# Caricamento
# --------------------------------------------------------------------------


def _leggi_yaml() -> dict[str, Any]:
    percorso = CONFIG_PATH if CONFIG_PATH.exists() else CONFIG_EXAMPLE_PATH
    if not percorso.exists():
        return {}
    try:
        with open(percorso, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError) as e:
        # Prima l'eccezione veniva ingoiata in silenzio e si ripartiva dai
        # valori predefiniti: un file corrotto faceva perdere la
        # configurazione senza che nulla lo segnalasse.
        logger.error("Configurazione illeggibile (%s): %s. Uso i valori predefiniti.", percorso, e)
        return {}


def _applica_ambiente(dati: dict[str, Any]) -> dict[str, Any]:
    """Sovrascrive con i valori presi da ambiente o .env, dove presenti."""
    for (sezione, campo), (variabile, _) in segreti.CAMPI_DA_AMBIENTE.items():
        valore = segreti.leggi(variabile)
        if valore:
            dati.setdefault(sezione, {})
            if isinstance(dati[sezione], dict):
                dati[sezione][campo] = valore
    return dati


def load_config() -> AppConfig:
    return AppConfig(**_applica_ambiente(_leggi_yaml()))


def reload_settings() -> AppConfig:
    """Rilegge la configurazione **dentro lo stesso oggetto**.

    Sostituire l'oggetto lascerebbe indietro chiunque abbia scritto
    `from config.settings import settings`: quel nome resta legato alla
    vecchia istanza per sempre. Succedeva a sei moduli — fra cui
    `server/sicurezza.py` — che dopo un salvataggio dal pannello
    impostazioni continuavano a leggere i valori di prima fino al riavvio
    del servizio. E' la stessa forma del difetto REL-04 (issue #9), dove il
    client di Home Assistant congelava l'indirizzo al momento dell'import.

    Aggiornare i campi al loro posto mantiene una sola identita' condivisa:
    chi ha importato `settings` vede la configurazione corrente, sempre.
    """
    nuovo = load_config()
    for campo in AppConfig.model_fields:
        setattr(settings, campo, getattr(nuovo, campo))
    return settings


# --------------------------------------------------------------------------
# Salvataggio
# --------------------------------------------------------------------------


def save_config(config: AppConfig) -> None:
    """Scrive i segreti in .env e tutto il resto in config.yaml.

    Nessun segreto tocca il file di configurazione: e' l'invariante che
    impedisce a un `git commit -a` di pubblicare le credenziali di casa.
    """
    dati = config.model_dump()

    da_ambiente: dict[str, str] = {}
    for (sezione, campo), (variabile, e_segreto) in segreti.CAMPI_DA_AMBIENTE.items():
        valore = (dati.get(sezione) or {}).get(campo)
        if valore:
            da_ambiente[variabile] = str(valore)
        if e_segreto and sezione in dati and isinstance(dati[sezione], dict):
            dati[sezione][campo] = ""

    segreti.scrivi(da_ambiente)

    temporaneo = CONFIG_PATH.with_suffix(".yaml.tmp")
    with open(temporaneo, "w", encoding="utf-8") as f:
        yaml.safe_dump(dati, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    temporaneo.replace(CONFIG_PATH)

    reload_settings()


# --------------------------------------------------------------------------
# Migrazione e controlli d'avvio
# --------------------------------------------------------------------------


def migra_segreti_su_env() -> list[str]:
    """Sposta in .env i segreti rimasti in config.yaml. Idempotente.

    Restituisce i nomi delle variabili migrate.
    """
    if not CONFIG_PATH.exists():
        return []

    dati = _leggi_yaml()
    da_spostare: dict[str, str] = {}

    for sezione, campo in segreti.CAMPI_SEGRETI:
        valore = (dati.get(sezione) or {}).get(campo)
        if segreti.e_segnaposto(valore):
            continue
        variabile = segreti.CAMPI_DA_AMBIENTE[(sezione, campo)][0]
        if segreti.leggi(variabile):
            continue  # gia' nell'ambiente: l'ambiente vince
        da_spostare[variabile] = str(valore)

    if not da_spostare:
        return []

    segreti.scrivi(da_spostare)
    for sezione, campo in segreti.CAMPI_SEGRETI:
        if sezione in dati and isinstance(dati[sezione], dict) and campo in dati[sezione]:
            dati[sezione][campo] = ""

    temporaneo = CONFIG_PATH.with_suffix(".yaml.tmp")
    with open(temporaneo, "w", encoding="utf-8") as f:
        yaml.safe_dump(dati, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    temporaneo.replace(CONFIG_PATH)

    logger.warning(
        "Migrati %d segreti da config.yaml a .env: %s. "
        "Se quel file e' mai finito in un commit, revoca subito le credenziali.",
        len(da_spostare),
        ", ".join(sorted(da_spostare)),
    )
    reload_settings()
    return sorted(da_spostare)


def assicura_segreto_sessione() -> bool:
    """Genera il segreto di sessione se manca. Vero se ne ha creato uno."""
    if segreti.leggi("SHINRA_SESSION_SECRET"):
        return False
    nuovo = segreti.genera_segreto_sessione()
    segreti.scrivi({"SHINRA_SESSION_SECRET": nuovo})
    logger.info("Generato un nuovo segreto di sessione in .env.")
    reload_settings()
    return True


def verifica_configurazione(config: Optional[AppConfig] = None) -> list[str]:
    """Problemi di configurazione da segnalare all'avvio.

    Non solleva eccezioni: chi chiama decide se fermarsi o proseguire.
    """
    cfg = config or settings
    problemi: list[str] = []

    if cfg.home_assistant.enabled and segreti.e_segnaposto(cfg.home_assistant.token):
        problemi.append(
            "Home Assistant e' abilitato ma il token non e' configurato. "
            "Imposta SHINRA_HA_TOKEN in .env, oppure metti home_assistant.enabled a false."
        )

    if not cfg.security.auth_enabled:
        problemi.append(
            "L'autenticazione e' disattivata: chiunque sia sulla rete di casa puo' "
            "comandare l'impianto e leggere i dati della famiglia."
        )

    if cfg.server.debug and cfg.server.host == "0.0.0.0":
        problemi.append(
            "server.debug e' attivo con il servizio in ascolto su tutte le interfacce: "
            "il ricaricamento automatico e le tracce di errore non vanno esposti in rete."
        )

    if cfg.alexa.enabled and not (cfg.alexa.skill_id or "").strip():
        problemi.append(
            "La skill Alexa e' abilitata senza skill_id: /api/alexa non puo' verificare "
            "da quale skill arrivano i comandi. Imposta SHINRA_ALEXA_SKILL_ID in .env."
        )

    return problemi


settings = load_config()
