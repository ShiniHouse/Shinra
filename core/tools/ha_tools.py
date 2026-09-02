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

import asyncio

async def activate_mode(mode_name: str) -> Dict[str, Any]:
    """
    Attiva una modalità o scenario personalizzato modulare a catena (Action-Reaction Flow).
    Supporta:
    - Controllo dispositivi HA (luci, prese, clima, tapparelle)
    - Ritardi temporali (delay_seconds)
    - Messaggi vocali TTS
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
    tts_messages = []

    # Se la modalità è definita con la struttura a Grafo (Nodes & Edges - Stile Visio/Node-RED)
    nodes = target_mode.get("nodes", [])
    edges = target_mode.get("edges", [])

    if nodes and edges:
        # Costruisce la mappa dei nodi e l'adiacenza
        node_map = {n["id"]: n for n in nodes if "id" in n}
        adj = {}
        in_degree = {n["id"]: 0 for n in nodes if "id" in n}
        for e in edges:
            u, v = e.get("from"), e.get("to")
            if u and v and u in node_map and v in node_map:
                adj.setdefault(u, []).append(v)
                in_degree[v] = in_degree.get(v, 0) + 1

        # Trova il punto di partenza (nodo trigger o con in_degree == 0)
        start_nodes = [n_id for n_id, deg in in_degree.items() if deg == 0 and node_map[n_id].get("type") == "trigger"]
        if not start_nodes:
            start_nodes = [n_id for n_id, deg in in_degree.items() if deg == 0]
        if not start_nodes and nodes:
            start_nodes = [nodes[0]["id"]]

        # Coda di esecuzione BFS ordinata
        queue = list(start_nodes)
        visited = set()

        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited:
                continue
            visited.add(curr_id)

            curr_node = node_map.get(curr_id)
            if not curr_node:
                continue

            n_type = curr_node.get("type")
            n_data = curr_node.get("data", {})

            # 1. Nodo Dispositivo Home Assistant
            if n_type in ["ha_device", "ha_service"]:
                entity_id = n_data.get("entity_id")
                act_cmd = n_data.get("action", "turn_on")
                if entity_id:
                    resolved_entity = data_store.resolve_alias_or_entity(entity_id)
                    domain = resolved_entity.split(".")[0] if "." in resolved_entity else "homeassistant"
                    s_data = {"entity_id": resolved_entity}
                    if n_data.get("brightness") is not None:
                        s_data["brightness_pct"] = int(n_data["brightness"])
                    if n_data.get("temperature") is not None:
                        s_data["temperature"] = float(n_data["temperature"])

                    res = await ha_client.call_service(domain, act_cmd, s_data)
                    executed_actions.append({"type": "ha_device", "node_id": curr_id, "entity_id": resolved_entity, "action": act_cmd, "status": res.get("success", False)})

            # 2. Nodo Ritardo Temporizzato (Delay)
            elif n_type == "delay":
                delay_sec = float(n_data.get("seconds") or n_data.get("delay_seconds") or 1)
                logger.info(f"[Shinra Flow] Pausa temporizzata di {delay_sec}s sul nodo {curr_id}...")
                await asyncio.sleep(delay_sec)
                executed_actions.append({"type": "delay", "node_id": curr_id, "seconds": delay_sec, "status": True})

            # 3. Nodo Sintesi Vocale (TTS)
            elif n_type == "tts":
                msg = n_data.get("message", "")
                if msg:
                    tts_messages.append(msg)
                    executed_actions.append({"type": "tts", "node_id": curr_id, "message": msg, "status": True})

            # Accoda i nodi successivi collegati
            for neighbor in adj.get(curr_id, []):
                if neighbor not in visited:
                    queue.append(neighbor)

    else:
        # Fallback per routine con array lineare di actions
        for action in target_mode.get("actions", []):
            act_type = action.get("type", "ha_device")

            if act_type in ["ha_device", "ha_service"]:
                entity_id = action.get("entity_id") or action.get("data", {}).get("entity_id")
                act_cmd = action.get("action") or action.get("service", "turn_on")
                if entity_id:
                    resolved_entity = data_store.resolve_alias_or_entity(entity_id)
                    domain = resolved_entity.split(".")[0] if "." in resolved_entity else "homeassistant"
                    s_data = {"entity_id": resolved_entity}
                    if action.get("brightness") is not None:
                        s_data["brightness_pct"] = int(action["brightness"])
                    if action.get("temperature") is not None:
                        s_data["temperature"] = float(action["temperature"])

                    res = await ha_client.call_service(domain, act_cmd, s_data)
                    executed_actions.append({"type": "ha_device", "entity_id": resolved_entity, "action": act_cmd, "status": res.get("success", False)})

            elif act_type == "delay":
                delay_sec = float(action.get("seconds") or action.get("delay_seconds") or 1)
                logger.info(f"[Shinra Routine] Pausa programmata di {delay_sec}s...")
                await asyncio.sleep(delay_sec)
                executed_actions.append({"type": "delay", "seconds": delay_sec, "status": True})

            elif act_type == "tts":
                msg = action.get("message", "")
                if msg:
                    tts_messages.append(msg)
                    executed_actions.append({"type": "tts", "message": msg, "status": True})

    final_msg = " ".join(tts_messages) if tts_messages else f"Modalità {target_mode.get('name')} eseguita con successo."
    return {
        "success": True,
        "modalita": target_mode.get("name"),
        "azioni_eseguite": executed_actions,
        "messaggio": final_msg
    }
