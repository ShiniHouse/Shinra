import logging
import feedparser
import asyncio
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from core.user_manager import user_manager, UserProfile
from core.data_store import data_store
from core.tools.ha_tools import activate_mode
from core.ha_client import HomeAssistantClient
from config.settings import settings, save_config, AppConfig, reload_settings

logger = logging.getLogger("Shinra.Admin")
router = APIRouter(prefix="/api", tags=["Admin & Management"])
ha_client = HomeAssistantClient()

# --- User Models ---
class IdentifyRequest(BaseModel):
    text: str

# --- USERS ENDPOINTS ---
@router.get("/users")
async def list_users():
    return user_manager.get_users()

@router.post("/users")
async def save_user(user: UserProfile):
    user_manager.upsert_user(user)
    return {"success": True, "user": user}

@router.delete("/users/{user_id}")
async def delete_user(user_id: str):
    success = user_manager.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    return {"success": True}

@router.post("/users/identify")
async def identify_user(req: IdentifyRequest):
    profile = user_manager.find_user_by_name(req.text)
    if profile.age_group == "child":
        greeting = f"Ciao {profile.name}! Come posso aiutarti oggi?"
    elif profile.role == "admin":
        greeting = f"{profile.name}. Sono online. Dimmi pure."
    else:
        greeting = f"Ciao {profile.name}, a tua disposizione."
    return {"user": profile, "greeting": greeting}

# --- KNOWLEDGE ENDPOINTS ---
@router.get("/knowledge")
async def list_knowledge():
    return data_store.get_knowledge()

@router.post("/knowledge")
async def save_knowledge(item: Dict[str, Any]):
    items = data_store.get_knowledge()
    item_id = item.get("id") or f"k_{len(items) + 1}"
    item["id"] = item_id
    
    updated = False
    for i, k in enumerate(items):
        if k.get("id") == item_id:
            items[i] = item
            updated = True
            break
    if not updated:
        items.append(item)
    
    data_store.save_knowledge(items)
    return {"success": True, "item": item}

@router.delete("/knowledge/{item_id}")
async def delete_knowledge(item_id: str):
    items = data_store.get_knowledge()
    filtered = [k for k in items if k.get("id") != item_id]
    data_store.save_knowledge(filtered)
    return {"success": True}

# --- SOURCES (RSS) ENDPOINTS ---
@router.get("/sources")
async def list_sources():
    return data_store.get_sources()

@router.post("/sources")
async def save_source(source: Dict[str, Any]):
    sources = data_store.get_sources()
    s_id = source.get("id") or f"src_{len(sources) + 1}"
    source["id"] = s_id

    updated = False
    for i, s in enumerate(sources):
        if s.get("id") == s_id:
            sources[i] = source
            updated = True
            break
    if not updated:
        sources.append(source)

    data_store.save_sources(sources)
    return {"success": True, "source": source}

@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    sources = data_store.get_sources()
    filtered = [s for s in sources if s.get("id") != source_id]
    data_store.save_sources(filtered)
    return {"success": True}

@router.get("/sources/test")
async def test_source(url: str = Query(...)):
    try:
        def _parse():
            return feedparser.parse(url)
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, _parse)
        
        if feed.bozo and not feed.entries:
            return {"valid": False, "error": "Feed non valido o non raggiungibile."}
        
        preview = []
        for entry in feed.entries[:3]:
            preview.append({
                "title": entry.get("title", ""),
                "published": entry.get("published", "")
            })
        return {
            "valid": True,
            "title": feed.feed.get("title", "Senza titolo"),
            "items_count": len(feed.entries),
            "preview": preview
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

# --- HOME ASSISTANT ENTITIES ---
CONTROLLABLE_DOMAINS = ["light", "switch", "climate", "cover", "media_player", "fan", "scene", "script", "automation", "input_boolean", "vacuum", "lock"]
ALL_VISIBLE_DOMAINS = CONTROLLABLE_DOMAINS + ["sensor", "binary_sensor", "camera", "weather", "person", "device_tracker"]

DOMAIN_LABELS = {
    "light": "💡 Luci",
    "switch": "🔌 Interruttori",
    "climate": "🌡️ Clima",
    "cover": "🪟 Tapparelle / Coperture",
    "media_player": "📺 Media Player",
    "fan": "💨 Ventilatori",
    "scene": "🎭 Scene",
    "script": "📜 Script",
    "automation": "⚡ Automazioni",
    "input_boolean": "🔘 Interruttori Virtuali",
    "vacuum": "🤖 Robot Aspirapolvere",
    "lock": "🔒 Serrature",
    "sensor": "📡 Sensori",
    "binary_sensor": "🔔 Sensori Binari",
    "weather": "☁️ Meteo",
    "person": "👤 Persone",
    "device_tracker": "📍 Tracker",
}

@router.get("/ha/entities")
async def get_ha_entities(domain: Optional[str] = None):
    """Restituisce tutte le entità HA raggruppate per dominio."""
    states = await ha_client.get_states()
    if not states:
        conn = await ha_client.check_connection()
        return {"error": True, "status": conn.get("status"), "message": conn.get("message"), "groups": {}}

    groups: Dict[str, List[Dict]] = {}
    current_aliases = {a.get("entity_id"): a.get("alias") for a in data_store.get_aliases()}

    for entity in states:
        entity_id = entity.get("entity_id", "")
        d = entity_id.split(".")[0]
        if domain and d != domain:
            continue
        if d not in ALL_VISIBLE_DOMAINS:
            continue
        groups.setdefault(d, [])
        groups[d].append({
            "entity_id": entity_id,
            "friendly_name": entity.get("attributes", {}).get("friendly_name", entity_id),
            "state": entity.get("state", "unknown"),
            "unit": entity.get("attributes", {}).get("unit_of_measurement", ""),
            "domain": d,
            "domain_label": DOMAIN_LABELS.get(d, d),
            "controllable": d in CONTROLLABLE_DOMAINS,
            "alias": current_aliases.get(entity_id),
        })

    # Ordina i gruppi per priorità (controllabili prima)
    ordered = {}
    for d in CONTROLLABLE_DOMAINS + [x for x in ALL_VISIBLE_DOMAINS if x not in CONTROLLABLE_DOMAINS]:
        if d in groups:
            ordered[d] = sorted(groups[d], key=lambda x: x["friendly_name"])

    return {"error": False, "groups": ordered, "total": sum(len(v) for v in ordered.values())}


# --- DEVICE ALIASES ENDPOINTS ---
@router.get("/aliases")
async def list_aliases():
    return data_store.get_aliases()

@router.post("/aliases")
async def save_alias(alias: Dict[str, Any]):
    aliases = data_store.get_aliases()
    a_id = alias.get("id") or f"alias_{len(aliases) + 1}"
    alias["id"] = a_id

    updated = False
    for i, a in enumerate(aliases):
        if a.get("id") == a_id:
            aliases[i] = alias
            updated = True
            break
    if not updated:
        aliases.append(alias)

    data_store.save_aliases(aliases)
    return {"success": True, "alias": alias}

@router.delete("/aliases/{alias_id}")
async def delete_alias(alias_id: str):
    aliases = data_store.get_aliases()
    filtered = [a for a in aliases if a.get("id") != alias_id]
    data_store.save_aliases(filtered)
    return {"success": True}

# --- MODES ENDPOINTS ---
@router.get("/modes")
async def list_modes():
    return data_store.get_modes()

@router.post("/modes")
async def save_mode(mode: Dict[str, Any]):
    modes = data_store.get_modes()
    m_id = mode.get("id") or f"mode_{len(modes) + 1}"
    mode["id"] = m_id

    updated = False
    for i, m in enumerate(modes):
        if m.get("id") == m_id:
            modes[i] = mode
            updated = True
            break
    if not updated:
        modes.append(mode)

    data_store.save_modes(modes)
    return {"success": True, "mode": mode}

@router.delete("/modes/{mode_id}")
async def delete_mode(mode_id: str):
    modes = data_store.get_modes()
    filtered = [m for m in modes if m.get("id") != mode_id]
    data_store.save_modes(filtered)
    return {"success": True}

@router.post("/modes/{mode_name}/activate")
async def trigger_mode(mode_name: str):
    result = await activate_mode(mode_name)
    return result

# --- SETTINGS ENDPOINTS ---
@router.get("/settings")
async def get_app_settings():
    return reload_settings().model_dump()

@router.post("/settings")
async def update_app_settings(new_settings: AppConfig):
    save_config(new_settings)
    return {"success": True, "settings": reload_settings().model_dump()}
