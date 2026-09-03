from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True


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
    auth_enabled: bool = False
    admin_pin: Optional[str] = ""
    # Un segreto uguale per tutte le installazioni non e' un segreto:
    # sostituito da uno generato per installazione nella issue #07.
    session_secret: Optional[str] = "shinra-secret-key-salt"  # noqa: S105
    protect_dashboard: bool = True


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    alexa: AlexaConfig = Field(default_factory=AlexaConfig)
    assistant: AssistantConfig = Field(default_factory=AssistantConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)


def load_config() -> AppConfig:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return AppConfig(**data)
        except Exception:  # noqa: S110  — registrato nella issue #07
            pass
    return AppConfig()


def reload_settings() -> AppConfig:
    global settings
    settings = load_config()
    return settings


def save_config(config: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f, default_flow_style=False, allow_unicode=True)
    reload_settings()


settings = load_config()
