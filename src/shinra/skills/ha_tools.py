import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence

from shinra.domain import grafo as grafo_dominio
from shinra.domain import presenza as presenza_dominio
from shinra.domain.eventi import RICHIESTA_AVVISO, Evento, bus
from shinra.infra.data_store import data_store
from shinra.infra.homeassistant.client import client_home_assistant

logger = logging.getLogger(__name__)


async def _percorso_del_grafo(
    nodi: Sequence[Dict[str, Any]], archi: Sequence[Dict[str, Any]]
) -> tuple[list[grafo_dominio.Passo], list[tuple[str, str, str]]]:
    """Cosa eseguire, secondo il dominio, con la casa com'e' adesso.

    Gli stati si leggono **una volta sola** e valgono per tutte le condizioni
    del grafo: se una routine ha tre condizioni sulla stessa lampadina, e la
    lampadina cambia a meta' esecuzione, i tre rami devono venire dalla stessa
    fotografia. Altrimenti la stessa routine, sullo stesso grafo, fa cose
    diverse a seconda di quanto era lenta.
    """
    struttura = grafo_dominio.Grafo(nodi, archi)

    # La lettura serve solo se c'e' qualcosa da decidere: una routine lineare
    # non deve pagare un giro a Home Assistant per niente.
    servono_stati = any(struttura.tipo_di(i) == grafo_dominio.CONDIZIONE for i in struttura.mappa)
    stati: Dict[str, str] = {}
    abitata: Optional[bool] = None

    if servono_stati:
        try:
            correnti = list(await client_home_assistant().stati_correnti())
        except Exception as errore:  # una casa irraggiungibile non e' un errore di grafo
            logger.warning("Condizioni valutate senza stati: %s", errore)
            correnti = []
        stati = {str(s.get("entity_id")): str(s.get("state")) for s in correnti if s.get("entity_id")}
        presenti = presenza_dominio.leggi(presenza_dominio.persone_dagli_stati(correnti))
        abitata = presenti.abitata if presenti.conosciuta else None

    return grafo_dominio.percorso(struttura, datetime.now().astimezone(), stati, abitata)


async def _notifica_dal_nodo(dati: Mapping[str, Any], nome_routine: str) -> bool:
    """Chiede un avviso, senza sapere chi lo mandera'.

    Una capacita' non puo' chiamare il servizio delle notifiche — `skills/`
    sta sotto `services/` — quindi pubblica sul bus e chi sa mandarle lo
    raccoglie. Non e' un giro largo per rispettare una regola: e' il motivo
    per cui la regola esiste, perche' domani un secondo canale puo' iscriversi
    allo stesso evento senza che questa riga cambi.
    """
    testo = str(dati.get("testo") or dati.get("message") or "").strip()
    if not testo:
        return False

    await bus.pubblica(
        Evento(
            tipo=RICHIESTA_AVVISO,
            dati={
                "titolo": str(dati.get("titolo") or dati.get("title") or nome_routine),
                "testo": testo,
                "categoria": dati.get("categoria"),
                "priorita": dati.get("priorita"),
                "destinazione": dati.get("destinazione") or "/#modalita",
            },
        )
    )
    return True


async def control_device(
    entity_id: str,
    action: str,  # 'turn_on', 'turn_off', 'toggle', 'set_temperature', 'open', 'close', 'press'
    brightness: Optional[int] = None,  # 0-100 per luci
    temperature: Optional[float] = None,  # per termostati
    color_name: Optional[str] = None,  # per luci RGB (es. 'rosso', 'blu', 'bianco caldo')
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

    res = await client_home_assistant().call_service(domain, service, service_data)
    if res.get("success"):
        return {
            "success": True,
            "message": f"Azione '{action}' eseguita con successo su '{resolved_entity}'.",
        }
    return {
        "success": False,
        "error": res.get("error"),
        "message": f"Non è stato possibile eseguire l'azione '{action}' su '{resolved_entity}'.",
    }


async def get_home_status(filter_domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Recupera lo stato attuale dei dispositivi e sensori di casa (es. luci accese, temperature, sensori).
    """
    states = await client_home_assistant().get_states()
    if not states:
        return {
            "success": False,
            "message": "Nessun dato disponibile da Home Assistant (verifica connessione/token).",
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

            results.append(
                {"entity_id": entity_id, "nome": friendly_name, "stato": f"{state} {unit}".strip()}
            )

    return {"success": True, "conteggio_dispositivi": len(results), "dispositivi": results[:50]}


async def activate_scene_or_routine(entity_id: str) -> Dict[str, Any]:
    """
    Attiva una scena, routine o script domotico configurato in Home Assistant.
    """
    domain = entity_id.split(".")[0] if "." in entity_id else "scene"
    service = "turn_on"
    res = await client_home_assistant().call_service(domain, service, {"entity_id": entity_id})
    if res.get("success"):
        return {"success": True, "message": f"Scena '{entity_id}' attivata."}
    return {"success": False, "error": res.get("error")}


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

    decisioni: list[Dict[str, Any]] = []

    if nodes and edges:
        # Il percorso lo decide `domain/grafo.py`; qui si esegue e basta.
        #
        # Prima c'erano novanta righe di visita in ampiezza scritte dentro
        # questa funzione, mescolate alle chiamate a Home Assistant. Non era
        # solo brutto: percorreva **tutti** gli archi, e un nodo condizione
        # con due uscite avrebbe eseguito entrambi i rami — cioe' non sarebbe
        # stato una condizione. Riferimento: issue #28.
        passi, scelte = await _percorso_del_grafo(nodes, edges)
        decisioni = [{"node_id": nodo, "ramo": ramo, "motivo": motivo} for nodo, ramo, motivo in scelte]

        for passo in passi:
            n_type, n_data, curr_id = passo.tipo, passo.dati, passo.id

            # 1. Nodo Dispositivo Home Assistant
            if n_type in (grafo_dominio.DISPOSITIVO, grafo_dominio.SERVIZIO):
                entity_id = n_data.get("entity_id")
                act_cmd = n_data.get("action", "turn_on")
                if entity_id:
                    resolved_entity = data_store.resolve_alias_or_entity(entity_id)
                    domain = resolved_entity.split(".")[0] if "." in resolved_entity else "homeassistant"
                    s_data: Dict[str, Any] = {"entity_id": resolved_entity}
                    if n_data.get("brightness") is not None:
                        s_data["brightness_pct"] = int(n_data["brightness"])
                    if n_data.get("temperature") is not None:
                        s_data["temperature"] = float(n_data["temperature"])

                    res = await client_home_assistant().call_service(domain, act_cmd, s_data)
                    executed_actions.append(
                        {
                            "type": "ha_device",
                            "node_id": curr_id,
                            "entity_id": resolved_entity,
                            "action": act_cmd,
                            "status": res.get("success", False),
                        }
                    )

            # 2. Nodo Ritardo Temporizzato (Delay)
            elif n_type == grafo_dominio.RITARDO:
                delay_sec = float(n_data.get("seconds") or n_data.get("delay_seconds") or 1)
                logger.info(f"[Shinra Flow] Pausa temporizzata di {delay_sec}s sul nodo {curr_id}...")
                await asyncio.sleep(delay_sec)
                executed_actions.append(
                    {"type": "delay", "node_id": curr_id, "seconds": delay_sec, "status": True}
                )

            # 3. Nodo Sintesi Vocale (TTS)
            elif n_type == grafo_dominio.ANNUNCIO:
                msg = n_data.get("message", "")
                if msg:
                    tts_messages.append(msg)
                    executed_actions.append(
                        {"type": "tts", "node_id": curr_id, "message": msg, "status": True}
                    )

            # 4. Nodo Notifica (issue #28). Distinto dall'annuncio: un
            #    annuncio lo sente chi e' nella stanza, una notifica raggiunge
            #    il telefono anche di chi non c'e'. Sono due cose diverse, e
            #    prima si poteva scrivere solo la prima.
            elif n_type == grafo_dominio.NOTIFICA:
                inviata = await _notifica_dal_nodo(n_data, mode_name)
                executed_actions.append(
                    {
                        "type": "notifica",
                        "node_id": curr_id,
                        "titolo": n_data.get("titolo") or n_data.get("title") or "",
                        "status": inviata,
                    }
                )

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

                    res = await client_home_assistant().call_service(domain, act_cmd, s_data)
                    executed_actions.append(
                        {
                            "type": "ha_device",
                            "entity_id": resolved_entity,
                            "action": act_cmd,
                            "status": res.get("success", False),
                        }
                    )

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

    final_msg = (
        " ".join(tts_messages)
        if tts_messages
        else f"Modalità {target_mode.get('name')} eseguita con successo."
    )
    return {
        "success": True,
        "modalita": target_mode.get("name"),
        "azioni_eseguite": executed_actions,
        # Quali rami hanno preso le condizioni, e perche'. Serve a rispondere
        # a «perche' la routine non ha acceso la luce» senza rieseguirla, e a
        # illuminare il ramo giusto nel simulatore dell'editor.
        "decisioni": decisioni,
        "messaggio": final_msg,
    }


async def get_indoor_temperature(room: str = "") -> Dict[str, Any]:
    """Legge i sensori di temperatura di casa, eventualmente di una stanza sola.

    Esiste perche' «che temperatura c'e' in salotto» non e' una domanda sul
    meteo: prima quella frase finiva a Open-Meteo e riceveva la temperatura
    esterna della citta'. Sbagliata, e detta con sicurezza.
    """
    states = await client_home_assistant().get_states()
    if not states:
        return {
            "success": False,
            "message": "Non riesco a leggere i sensori: Home Assistant non risponde.",
        }

    cercata = (room or "").strip().lower()
    letture = []
    for entity in states:
        entity_id = entity.get("entity_id", "")
        if not entity_id.startswith("sensor."):
            continue
        attributi = entity.get("attributes", {})
        unita = (attributi.get("unit_of_measurement") or "").strip()
        classe = (attributi.get("device_class") or "").lower()
        if classe != "temperature" and unita not in ("°C", "°F"):
            continue

        stato = entity.get("state", "")
        if stato in ("unknown", "unavailable", "", None):
            continue

        nome = attributi.get("friendly_name", entity_id)
        if cercata and cercata not in nome.lower() and cercata not in entity_id.lower():
            continue

        letture.append({"entita": entity_id, "nome": nome, "valore": stato, "unita": unita})

    return {"success": True, "stanza": room, "letture": letture}
