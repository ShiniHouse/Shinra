import logging
from typing import Dict, Any, Optional
from core.ha_client import HomeAssistantClient
from core.data_store import data_store
from config.settings import settings

logger = logging.getLogger(__name__)

# Istanza condivisa del client HA
ha_client = HomeAssistantClient(
    base_url=settings.home_assistant.url,
    token=settings.home_assistant.token
)

async def control_device(
    entity_id: str,
    action: str, # 'turn_on', 'turn_off', 'toggle', 'set_temperature', 'open', 'close', 'press'
    brightness: Optional[int] = None, # 0-100 per luci
    temperature: Optional[float] = None, # per termostati
    color_name: Optional[str] = None # per luci RGB (es. 'rosso', 'blu', 'bianco caldo')
) -> Dict[str, Any]:
    """
    Controlla un dispositivo smart della casa tramite Home Assistant o risolvendo l'alias configurato.
    """
    # Risoluzione automatica alias (es. "lampadario salotto" -> "light.salotto_main")
    resolved_entity = data_store.resolve_alias_or_entity(entity_id)

    domain = resolved_entity.split(".")[0] if "." in resolved_entity else "homeassistant"
    service_data: Dict[str, Any] = {"entity_id": resolved_entity}
    service = action

    if action == "turn_on":
        if domain == "light":
            if brightness is not None:
                service_data["brightness_pct"] = max(1, min(100, int(brightness)))
            if color_name:
                service_data["color_name"] = color_name
        service = "turn_on"

    elif action == "turn_off":
        service = "turn_off"

    elif action == "set_temperature":
        domain = "climate"
        service = "set_temperature"
        if temperature is not None:
            service_data["temperature"] = float(temperature)

    elif action in ["open", "close"]:
        domain = "cover"
        service = "open_cover" if action == "open" else "close_cover"

    res = await ha_client.call_service(domain, service, service_data)
    if res.get("success"):
        return {
            "success": True,
            "message": f"Azione '{action}' eseguita con successo su '{resolved_entity}'."
        }
    return {
        "success": False,
        "error": res.get("error"),
        "message": f"Non è stato possibile eseguire l'azione '{action}' su '{resolved_entity}'."
    }

async def get_home_status(filter_domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Recupera lo stato attuale dei dispositivi e sensori di casa (es. luci accese, temperature, sensori).
    """
    states = await ha_client.get_states()
    if not states:
        return {
            "success": False,
            "message": "Nessun dato disponibile da Home Assistant (verifica connessione/token)."
        }

    results = []
    for entity in states:
        entity_id = entity.get("entity_id", "")
        domain = entity_id.split(".")[0]
        
        if filter_domain and domain != filter_domain:
            continue

        if domain in ["light", "switch", "climate", "cover", "sensor"]:
            friendly_name = entity.get("attributes", {}).get("friendly_name", entity_id)
            state = entity.get("state", "unknown")
            unit = entity.get("attributes", {}).get("unit_of_measurement", "")
            
            if domain == "sensor" and any(x in entity_id for x in ["uptime", "ip_address", "last_boot"]):
                continue

            results.append({
                "entity_id": entity_id,
                "nome": friendly_name,
                "stato": f"{state} {unit}".strip()
            })

    return {
        "success": True,
        "conteggio_dispositivi": len(results),
        "dispositivi": results[:50]
    }

async def activate_scene_or_routine(entity_id: str) -> Dict[str, Any]:
    """
    Attiva una scena, routine o script domotico configurato in Home Assistant.
    """
    domain = entity_id.split(".")[0] if "." in entity_id else "scene"
    service = "turn_on"
    res = await ha_client.call_service(domain, service, {"entity_id": entity_id})
    if res.get("success"):
        return {"success": True, "message": f"Scena '{entity_id}' attivata."}
    return {"success": False, "error": res.get("error")}

async def activate_mode(mode_name: str) -> Dict[str, Any]:
    """
    Attiva una modalità o scenario personalizzato salvato in Shinra (es. 'Cinema', 'Buonanotte', 'Buongiorno', 'Lavoro').
    """
    modes = data_store.get_modes()
    target_mode = None
    clean = mode_name.strip().lower()

    for m in modes:
        if m.get("name", "").lower() == clean or m.get("id", "").lower() == clean:
            target_mode = m
            break
        for trigger in m.get("trigger_phrases", []):
            if trigger.lower() in clean or clean in trigger.lower():
                target_mode = m
                break
        if target_mode:
            break

    if not target_mode:
        return {"success": False, "message": f"Modalità '{mode_name}' non trovata."}

    executed_actions = []
    tts_message = ""

    for action in target_mode.get("actions", []):
        act_type = action.get("type")
        if act_type == "ha_service":
            domain = action.get("domain", "homeassistant")
            service = action.get("service", "turn_on")
            data = action.get("data", {})
            res = await ha_client.call_service(domain, service, data)
            executed_actions.append({"service": f"{domain}.{service}", "status": res.get("success", False)})
        elif act_type == "tts":
            tts_message = action.get("message", "")

    return {
        "success": True,
        "modalita": target_mode.get("name"),
        "azioni_eseguite": executed_actions,
        "messaggio": tts_message or f"Modalità {target_mode.get('name')} attivata."
    }
