import json
import logging
import re
from typing import Dict, Any, List, Optional

from config.settings import settings
from config.prompt_templates import get_system_prompt
from core.ollama_client import OllamaClient
from core.memory import memory, ConversationMemory
from core.tools.registry import TOOLS_SCHEMA, execute_tool
from core.ha_client import HomeAssistantClient
from core.user_manager import user_manager, UserProfile
from core.data_store import data_store

logger = logging.getLogger("Shinra")

class ShinraAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.ha = HomeAssistantClient()

    async def process_user_input(
        self,
        user_text: str,
        user_id: Optional[str] = None,
        user_profile: Optional[UserProfile] = None,
        session_memory: Optional[ConversationMemory] = None,
        max_tool_iterations: int = 4
    ) -> Dict[str, Any]:
        """
        Elabora l'input dell'utente calibrando il comportamento sul profilo (adulto/bambino/ospite).
        """
        mem = session_memory or memory
        actions_taken: List[Dict[str, Any]] = []

        # 1. Risoluzione profilo utente
        profile = user_profile
        if not profile:
            if user_id:
                profile = user_manager.get_user_by_id(user_id)
            if not profile:
                # Profilo admin predefinito se non specificato
                users = user_manager.get_users()
                profile = users[0] if users else None

        # 2. Recupero riepilogo dispositivi da Home Assistant se abilitato
        ha_summary = ""
        if settings.home_assistant.enabled:
            ha_summary = await self.ha.get_relevant_entities_summary()

        # 3. Recupero informazioni da DataStore (conoscenza, alias, modalità)
        custom_knowledge = data_store.get_enabled_knowledge_summary()
        device_aliases = data_store.get_aliases_summary()
        modes_summary = data_store.get_modes_summary()

        # 4. Costruzione system prompt personalizzato
        system_prompt = get_system_prompt(
            home_context_summary=ha_summary,
            default_city=settings.assistant.default_city,
            user_profile=profile,
            custom_knowledge=custom_knowledge,
            device_aliases=device_aliases,
            modes_summary=modes_summary
        )

        # 4b. Arricchimento proattivo per dati live (Meteo & Notizie)
        user_lower = user_text.lower()
        live_context = ""

        # ==================== FAST-PATH ULTRA-RAPIDO (<0.2s) ====================
        # 0. Fast-Path: Timer & Promemoria Vocali
        from core.timer_engine import timer_engine
        parsed_timer = timer_engine.parse_timer_or_reminder(user_text)
        if parsed_timer:
            if parsed_timer["type"] == "timer":
                item = timer_engine.add_timer(
                    label=parsed_timer["label"],
                    duration_seconds=parsed_timer["duration_seconds"],
                    user_id=profile.id if profile else "alessio"
                )
                resp = f"Timer di {parsed_timer['amount']} {parsed_timer['unit']} impostato per {parsed_timer['label']}."
                mem.add_user_message(user_text)
                mem.add_assistant_message(resp)
                return {"response": resp, "actions": [{"tool": "set_timer", "args": parsed_timer, "result": item}], "user": profile.model_dump() if profile else None, "success": True}

            elif parsed_timer["type"] == "reminder":
                item = timer_engine.add_reminder(
                    text=parsed_timer["text"],
                    remind_at_iso=parsed_timer["remind_at"],
                    user_id=profile.id if profile else "alessio"
                )
                resp = f"Perfetto, ti ricorderò di {parsed_timer['text']} {parsed_timer['formatted_time']}."
                mem.add_user_message(user_text)
                mem.add_assistant_message(resp)
                return {"response": resp, "actions": [{"tool": "set_reminder", "args": parsed_timer, "result": item}], "user": profile.model_dump() if profile else None, "success": True}

        # 1. Fast-Path: Attivazione Modalità & Routine
        modes = data_store.get_modes()
        for m in modes:
            if m.get("enabled", True):
                triggers = [t.lower() for t in m.get("trigger_phrases", [])] + [m.get("name", "").lower(), f"modalità {m.get('name', '').lower()}", f"attiva {m.get('name', '').lower()}"]
                if any(t in user_lower for t in triggers if t):
                    logger.info(f"[Shinra Fast-Path] Attivazione immediata modalità: {m.get('name')}")
                    m_res = await execute_tool("activate_mode", {"mode_name": m.get("name")})
                    actions_taken.append({"tool": "activate_mode", "args": {"mode_name": m.get("name")}, "result": m_res})
                    resp = f"Modalità {m.get('name')} attivata."
                    mem.add_user_message(user_text)
                    mem.add_assistant_message(resp)
                    return {"response": resp, "actions": actions_taken, "user": profile.model_dump() if profile else None, "success": True}

        # 2. Fast-Path: Controllo Diretto Dispositivi con Alias (Accendi/Spegni rapido)
        action_match = re.match(r"^(accendi|attiva|spegni|disattiva)\s+(?:la\s+|il\s+|le\s+|l'|i\s+|gli\s+)?(.+)$", user_text, re.IGNORECASE)
        if action_match:
            verb = action_match.group(1).lower()
            target_device_name = action_match.group(2).strip().lower()
            is_turn_on = verb in ["accendi", "attiva"]
            action_code = "turn_on" if is_turn_on else "turn_off"
            
            # Cerca tra gli alias configurati
            aliases = data_store.get_aliases()
            matched_entity = None
            matched_alias_name = target_device_name
            for a in aliases:
                a_name = a.get("alias", "").lower()
                if a_name == target_device_name or a_name in target_device_name or target_device_name in a_name:
                    matched_entity = a.get("entity_id")
                    matched_alias_name = a.get("alias")
                    break

            if matched_entity:
                logger.info(f"[Shinra Fast-Path] Controllo immediato alias '{matched_alias_name}' -> {matched_entity} ({action_code})")
                ha_res = await execute_tool("control_device", {"entity_id": matched_entity, "action": action_code})
                actions_taken.append({"tool": "control_device", "args": {"entity_id": matched_entity, "action": action_code}, "result": ha_res})
                resp = f"{matched_alias_name.capitalize()} {'acceso' if is_turn_on else 'spento'}."
                mem.add_user_message(user_text)
                mem.add_assistant_message(resp)
                return {"response": resp, "actions": actions_taken, "user": profile.model_dump() if profile else None, "success": True}

        # 3. Fast-Path: Meteo Diretto (Previsioni istantanee in 0.15s)
        if any(w in user_lower for w in ["meteo", "tempo a", "tempo fa", "tempo farà", "previsioni", "pioverà", "piove", "temperatura"]):
            target_city = settings.assistant.default_city or "Roma"
            city_match = re.search(r"\b(?:a|ad|per|di)\s+([a-zA-Zàèéìòù]+)", user_text, re.IGNORECASE)
            if city_match:
                cand = city_match.group(1).strip()
                if cand.lower() not in ["oggi", "domani", "casa", "adesso", "questo", "questa", "sera", "mattina"]:
                    target_city = cand

            logger.info(f"[Shinra Fast-Path] Recupero meteo per: {target_city}")
            w_res = await execute_tool("get_weather", {"location": target_city, "days": 2})
            actions_taken.append({"tool": "get_weather", "args": {"location": target_city, "days": 2}, "result": w_res})
            
            if w_res.get("success"):
                loc = w_res.get("localita", target_city)
                adesso = w_res.get("adesso", {})
                previsioni = w_res.get("previsioni", [])
                
                if "domani" in user_lower and len(previsioni) > 1:
                    p_dom = previsioni[1]
                    resp = f"Domani a {loc} {p_dom.get('condizione', 'variabile').lower()}, max {p_dom.get('temp_max')} gradi e min {p_dom.get('temp_min')}."
                else:
                    p_oggi = previsioni[0] if previsioni else {}
                    t_adesso = adesso.get('temperatura', '')
                    c_adesso = adesso.get('condizione', '')
                    resp = f"A {loc} attualmente {t_adesso}, {c_adesso.lower()}."
                    if p_oggi:
                        resp += f" Massima prevista di {p_oggi.get('temp_max')} gradi."
                
                mem.add_user_message(user_text)
                mem.add_assistant_message(resp)
                return {"response": resp, "actions": actions_taken, "user": profile.model_dump() if profile else None, "success": True}

        # 4. Fast-Path: Notizie Flash in tempo reale
        elif any(w in user_lower for w in ["notizie", "ultime notizie", "rassegna stampa", "cosa succede"]):
            logger.info(f"[Shinra Fast-Path] Recupero notizie flash")
            n_res = await execute_tool("get_latest_news", {"category": "generale"})
            actions_taken.append({"tool": "get_latest_news", "args": {"category": "generale"}, "result": n_res})
            
            if n_res.get("success"):
                titoli = [item.get("titolo", "") for item in n_res.get("notizie", [])[:2]]
                resp = "Ultime notizie: " + ". ".join(titoli)
                mem.add_user_message(user_text)
                mem.add_assistant_message(resp)
                return {"response": resp, "actions": actions_taken, "user": profile.model_dump() if profile else None, "success": True}

        # 5. Arricchimento Enciclopedia/Wikipedia per LLM
        elif any(w in user_lower for w in ["cosa significa", "chi era", "chi è", "chi fu", "definizione di", "cos'è", "che cos'è", "spiegami", "quando è", "quando e", "patrono", "storia di", "dove si trova", "chi sono", "biografia di"]):
            clean_term = re.sub(r"^(cosa significa|chi era|chi è|chi fu|definizione di|cos'è|che cos'è|spiegami|il termine|la parola|quando è|quando e|dove si trova|storia di|patrono di|la festa di|il santo)\s+", "", user_text, flags=re.IGNORECASE).strip(" ?.,\"'")
            if clean_term:
                logger.info(f"[Shinra] Auto-recupero Wikipedia per: {clean_term}")
                wiki_res = await execute_tool("search_wikipedia", {"query": clean_term})
                actions_taken.append({"tool": "search_wikipedia", "args": {"query": clean_term}, "result": wiki_res})
                if wiki_res.get("success"):
                    live_context = f"ENCICLOPEDIA/DATI PER '{clean_term.upper()}': {wiki_res.get('estratto', '')}"

        if live_context:
            system_prompt += f"\n\n### INFORMAZIONI IN TEMPO REALE:\n{live_context}\nRispondi direttamente alla domanda dell'utente comunicando questi dati in modo sintetico e naturale (1-2 frasi). Non menzionare API o funzioni tecniche."

        # 5. Aggiornamento memoria e messaggi
        mem.add_user_message(user_text)
        
        conversation_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        conversation_messages.extend(mem.get_messages())

        # 6. Ciclo di Tool Calling con Gemma / Qwen
        # Attiva i tools complessi solo se il messaggio contiene richieste di domotica o ricerca web attiva
        ACTION_KEYWORDS = [
            "accend", "spegn", "attiva", "disattiva", "imposta", "regola", "alza", "abbassa",
            "chiudi", "apri", "luce", "luci", "lampad", "termostato", "presa", "interruttore",
            "modalità", "routine", "stato casa", "cerca sul web", "cerca su internet", "trova online",
            "dispositivi", "entità"
        ]
        needs_action_tools = any(kw in user_lower for kw in ACTION_KEYWORDS)

        for iteration in range(max_tool_iterations):
            user_label = profile.name if profile else 'Utente'
            logger.info(f"[Shinra] ({user_label}) Iterazione {iteration + 1} per: '{user_text}'")
            
            # Passa i tools solo se strettamente necessari e solo alla prima iterazione
            current_tools = TOOLS_SCHEMA if (needs_action_tools and not live_context and iteration == 0) else None
            response = await self.ollama.chat(
                messages=conversation_messages,
                tools=current_tools
            )

            if not response.get("success"):
                err_msg = response.get("error") or "Errore di elaborazione da Ollama"
                logger.error(f"[Shinra] Errore Ollama: {err_msg}")
                fallback = (
                    f"Si è verificato un problema di comunicazione con il motore IA: {err_msg}. "
                    "Assicurati che Ollama sia avviato e il modello sia pronto."
                )
                return {
                    "response": fallback,
                    "actions": actions_taken,
                    "user": profile.model_dump() if profile else None,
                    "success": False
                }

            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])
            content = message.get("content", "")

            # Se non ci sono tool calls nativi, cerca comandi testuali [TOOL: nome {...}]
            if not tool_calls:
                text_tool_match = re.search(r"\[TOOL:\s*(\w+)\s*(\{.*?\})\]", content, flags=re.DOTALL)
                if text_tool_match:
                    t_name = text_tool_match.group(1)
                    t_raw_args = text_tool_match.group(2)
                    try:
                        t_args = json.loads(t_raw_args)
                    except Exception:
                        t_args = {}
                    
                    logger.info(f"[Shinra] Rilevato tool testuale: '{t_name}' con {t_args}")
                    t_res = await execute_tool(t_name, t_args)
                    actions_taken.append({"tool": t_name, "args": t_args, "result": t_res})
                    
                    # Aggiunge il risultato per consentire a Shinra di formulare la risposta vocale naturale
                    conversation_messages.append({"role": "assistant", "content": content})
                    conversation_messages.append({"role": "user", "content": f"Risultato operazione {t_name}: {json.dumps(t_res, ensure_ascii=False)}. Formula ora una risposta breve e naturale per l'utente."})
                    continue
                else:
                    final_text = content.strip() or "Operazione completata."
                    mem.add_assistant_message(final_text)
                    return {
                        "response": final_text,
                        "actions": actions_taken,
                        "user": profile.model_dump() if profile else None,
                        "success": True
                    }

            conversation_messages.append(message)

            for call in tool_calls:
                func_info = call.get("function", {})
                tool_name = func_info.get("name")
                raw_args = func_info.get("arguments", {})

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except Exception:
                        args = {}
                else:
                    args = raw_args

                logger.info(f"Esecuzione tool '{tool_name}' con parametri: {args}")
                tool_result = await execute_tool(tool_name, args)
                
                actions_taken.append({
                    "tool": tool_name,
                    "args": args,
                    "result": tool_result
                })

                conversation_messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

        fallback = "Ho elaborato la tua richiesta e verificato i dati."
        mem.add_assistant_message(fallback)
        return {
            "response": fallback,
            "actions": actions_taken,
            "user": profile.model_dump() if profile else None,
            "success": True
        }

# Istanza globale dell'agente
agent = ShinraAgent()
