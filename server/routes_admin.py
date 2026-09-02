import logging
import feedparser
import asyncio
import hmac
import hashlib
import time
import secrets
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Header, Request
from pydantic import BaseModel

from core.user_manager import user_manager, UserProfile
from core.data_store import data_store
from core.tools.ha_tools import activate_mode
from core.ha_client import HomeAssistantClient
from config.settings import settings, save_config, AppConfig, reload_settings

logger = logging.getLogger("Shinra.Admin")
router = APIRouter(prefix="/api", tags=["Admin & Management"])
ha_client = HomeAssistantClient()

# --- AUTH & SESSION SECURITY ENGINE ---
ACTIVE_SESSIONS: Dict[str, float] = {}
SESSION_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 giorni di durata sessione
FAILED_ATTEMPTS: Dict[str, List[float]] = {}

def is_authenticated(auth_header: Optional[str] = None) -> bool:
    if not settings.security.auth_enabled or not settings.security.admin_pin:
        return True
    if not auth_header:
        return False
    token = auth_header.replace("Bearer ", "").strip()
    if token in ACTIVE_SESSIONS:
        created_at = ACTIVE_SESSIONS[token]
        if time.time() - created_at < SESSION_EXPIRY_SECONDS:
            return True
        else:
            ACTIVE_SESSIONS.pop(token, None)
    return False

class LoginRequest(BaseModel):
    pin: str

@router.get("/auth/status")
async def auth_status(x_shinra_auth: Optional[str] = Header(None)):
    """Restituisce lo stato di sicurezza e autenticazione corrente."""
    auth_enabled = bool(settings.security.auth_enabled and settings.security.admin_pin)
    authenticated = is_authenticated(x_shinra_auth) if auth_enabled else True
    return {
        "auth_enabled": auth_enabled,
        "authenticated": authenticated,
        "protect_dashboard": settings.security.protect_dashboard
    }

@router.post("/auth/login")
async def auth_login(req: LoginRequest, request: Request):
    """Verifica il PIN di sicurezza e genera un token di sessione."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Rate limiting anti-bruteforce
    attempts = FAILED_ATTEMPTS.get(client_ip, [])
    # Filtra tentativi negli ultimi 5 minuti
    attempts = [t for t in attempts if now - t < 300]
    FAILED_ATTEMPTS[client_ip] = attempts

    if len(attempts) >= 5:
        logger.warning(f"Troppi tentativi di accesso falliti da {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Troppi tentativi errati. Accesso temporaneamente bloccato per 5 minuti."
        )

    expected_pin = (settings.security.admin_pin or "").strip()
    provided_pin = req.pin.strip()

    if not expected_pin or provided_pin == expected_pin:
        token = secrets.token_hex(24)
        ACTIVE_SESSIONS[token] = now
        logger.info(f"Accesso riuscito per sessione amministratore da {client_ip}")
        return {"success": True, "token": token}
    else:
        attempts.append(now)
        FAILED_ATTEMPTS[client_ip] = attempts
        logger.warning(f"Tentativo di accesso con PIN errato da {client_ip}")
        raise HTTPException(status_code=401, detail="PIN o Password non corretta.")

@router.post("/auth/logout")
async def auth_logout(x_shinra_auth: Optional[str] = Header(None)):
    """Invalida il token di sessione attivo."""
    if x_shinra_auth:
        token = x_shinra_auth.replace("Bearer ", "").strip()
        ACTIVE_SESSIONS.pop(token, None)
    return {"success": True}

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

@router.post("/sources/bulk-toggle")
async def bulk_toggle_sources(payload: Dict[str, Any]):
    enabled = bool(payload.get("enabled", True))
    sources = data_store.get_sources()
    for s in sources:
        s["enabled"] = enabled
    data_store.save_sources(sources)
    return {"success": True, "count": len(sources), "enabled": enabled}

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
def mask_secret(secret: Optional[str]) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    return secret[:4] + "••••••••" + secret[-4:]

def is_masked(secret: Optional[str]) -> bool:
    if not secret:
        return False
    return "••••" in secret or "********" in secret or "***" in secret

@router.get("/settings")
async def get_app_settings(x_shinra_auth: Optional[str] = Header(None)):
    current = reload_settings().model_dump()
    # Maschera token sensibili
    if current.get("home_assistant", {}).get("token"):
        current["home_assistant"]["token"] = mask_secret(current["home_assistant"]["token"])
    if current.get("security", {}).get("admin_pin"):
        current["security"]["admin_pin"] = mask_secret(current["security"]["admin_pin"])
    return current

@router.post("/settings")
async def update_app_settings(new_settings: AppConfig, x_shinra_auth: Optional[str] = Header(None)):
    if settings.security.auth_enabled and settings.security.admin_pin:
        if not is_authenticated(x_shinra_auth):
            raise HTTPException(status_code=401, detail="Accesso non autorizzato. Inserisci il PIN di sicurezza.")

    current_cfg = reload_settings()

    # Preserva token Home Assistant se inviato mascherato o vuoto
    if is_masked(new_settings.home_assistant.token) and current_cfg.home_assistant.token:
        new_settings.home_assistant.token = current_cfg.home_assistant.token
    elif not new_settings.home_assistant.token and current_cfg.home_assistant.token:
        new_settings.home_assistant.token = current_cfg.home_assistant.token

    # Preserva PIN se inviato mascherato o vuoto con auth attiva
    if is_masked(new_settings.security.admin_pin) and current_cfg.security.admin_pin:
        new_settings.security.admin_pin = current_cfg.security.admin_pin
    elif not new_settings.security.admin_pin and current_cfg.security.admin_pin and new_settings.security.auth_enabled:
        new_settings.security.admin_pin = current_cfg.security.admin_pin

    save_config(new_settings)
    return await get_app_settings(x_shinra_auth)

# --- OLLAMA MODELS DISCOVERY ---
@router.get("/ollama/models")
async def get_ollama_models():
    """Recupera la lista dettagliata dei modelli disponibili direttamente da Ollama."""
    from core.ollama_client import OllamaClient
    client = OllamaClient()
    models = await client.get_models_detailed()
    return {"success": True, "models": models, "active_model": client.model}

# --- TIMERS & REMINDERS ENDPOINTS ---
from core.timer_engine import timer_engine

class CreateTimerReq(BaseModel):
    label: str = "Timer"
    duration_seconds: int = 60
    user_id: str = "alessio"

class CreateReminderReq(BaseModel):
    text: str
    remind_at: str
    user_id: str = "alessio"

@router.get("/timers")
async def list_timers():
    return timer_engine.get_timers()

@router.post("/timers")
async def create_timer(payload: CreateTimerReq):
    item = timer_engine.add_timer(payload.label, payload.duration_seconds, payload.user_id)
    return {"success": True, "timer": item}

@router.delete("/timers/{timer_id}")
async def remove_timer(timer_id: str):
    success = timer_engine.delete_timer(timer_id)
    return {"success": success}

@router.get("/reminders")
async def list_reminders():
    return timer_engine.get_reminders()

@router.post("/reminders")
async def create_reminder(payload: CreateReminderReq):
    item = timer_engine.add_reminder(payload.text, payload.remind_at, payload.user_id)
    return {"success": True, "reminder": item}

@router.delete("/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    success = timer_engine.delete_reminder(reminder_id)
    return {"success": success}

# --- LEARNING & INTERVIEW ENGINE ENDPOINTS ---
from core.interview_engine import interview_engine

class StartLearningReq(BaseModel):
    user_id: str = "alessio"

class AnswerLearningReq(BaseModel):
    user_id: str = "alessio"
    answer: str

class ConfirmRoutineReq(BaseModel):
    routine: Dict[str, Any]

@router.post("/learning/start")
async def start_learning_session(payload: StartLearningReq):
    res = interview_engine.start_session(payload.user_id)
    return res

@router.post("/learning/answer")
async def answer_learning_question(payload: AnswerLearningReq):
    res = await interview_engine.process_answer(payload.user_id, payload.answer)
    return res

@router.post("/learning/confirm-routine")
async def confirm_learning_routine(payload: ConfirmRoutineReq):
    res = interview_engine.confirm_routine(payload.routine)
    return res

@router.post("/learning/stop")
async def stop_learning_session(payload: StartLearningReq):
    interview_engine.stop_session(payload.user_id)
    return {"success": True, "message": "Sessione terminata."}

@router.get("/learning/status")
async def get_learning_status(user_id: str = "alessio"):
    session = interview_engine.get_session(user_id)
    return {"is_active": interview_engine.is_session_active(user_id), "session": session}



