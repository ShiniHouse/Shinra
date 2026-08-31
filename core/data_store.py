import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.json"
SOURCES_FILE = DATA_DIR / "sources.json"
ALIASES_FILE = DATA_DIR / "device_aliases.json"
MODES_FILE = DATA_DIR / "modes.json"

class KnowledgeItem(BaseModel):
    id: str
    text: str
    category: str = "generale"
    enabled: bool = True

class NewsSource(BaseModel):
    id: str
    name: str
    category: str
    url: str
    enabled: bool = True

class DeviceAlias(BaseModel):
    id: str
    alias: str
    entity_id: str
    room: Optional[str] = ""
    domain: Optional[str] = "light"

class ModeAction(BaseModel):
    type: str # 'ha_service' o 'tts'
    domain: Optional[str] = None
    service: Optional[str] = None
    entity_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None

class ModeItem(BaseModel):
    id: str
    name: str
    icon: Optional[str] = "zap"
    trigger_phrases: List[str] = []
    description: Optional[str] = ""
    enabled: bool = True
    actions: List[Dict[str, Any]] = []

class DataStore:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # --- Knowledge ---
    def get_knowledge(self) -> List[Dict[str, Any]]:
        try:
            if KNOWLEDGE_FILE.exists():
                with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Errore lettura knowledge.json: {e}")
            return []

    def save_knowledge(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura knowledge.json: {e}")

    def get_enabled_knowledge_summary(self) -> str:
        items = self.get_knowledge()
        active = [f"- {item['text']}" for item in items if item.get("enabled", True)]
        return "\n".join(active) if active else "Nessuna informazione personalizzata registrata."

    # --- Sources ---
    def get_sources(self) -> List[Dict[str, Any]]:
        try:
            if SOURCES_FILE.exists():
                with open(SOURCES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Errore lettura sources.json: {e}")
            return []

    def save_sources(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(SOURCES_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura sources.json: {e}")

    # --- Device Aliases ---
    def get_aliases(self) -> List[Dict[str, Any]]:
        try:
            if ALIASES_FILE.exists():
                with open(ALIASES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Errore lettura device_aliases.json: {e}")
            return []

    def save_aliases(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(ALIASES_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura device_aliases.json: {e}")

    def resolve_alias_or_entity(self, query_name: str) -> str:
        """Risolve un nome naturale nell'entity_id esatto di Home Assistant."""
        clean = query_name.strip().lower()
        if "." in clean:
            # È già un entity_id esatto come light.salotto
            return clean

        aliases = self.get_aliases()
        for item in aliases:
            if item.get("alias", "").lower() == clean or clean in item.get("alias", "").lower():
                return item.get("entity_id", clean)
        return clean

    def get_aliases_summary(self) -> str:
        aliases = self.get_aliases()
        lines = [f"- '{item.get('alias')}' → `{item.get('entity_id')}` ({item.get('room', 'Generale')})" for item in aliases]
        return "\n".join(lines) if lines else "Nessun alias configurato."

    # --- Modes / Routines ---
    def get_modes(self) -> List[Dict[str, Any]]:
        try:
            if MODES_FILE.exists():
                with open(MODES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Errore lettura modes.json: {e}")
            return []

    def save_modes(self, items: List[Dict[str, Any]]) -> None:
        try:
            with open(MODES_FILE, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Errore scrittura modes.json: {e}")

    def get_modes_summary(self) -> str:
        modes = self.get_modes()
        lines = []
        for m in modes:
            if m.get("enabled", True):
                triggers = ", ".join([f"'{t}'" for t in m.get("trigger_phrases", [])])
                lines.append(f"- Modalità '{m.get('name')}' (frasi di attivazione: {triggers}): {m.get('description', '')}")
        return "\n".join(lines) if lines else "Nessuna modalità configurata."

data_store = DataStore()
