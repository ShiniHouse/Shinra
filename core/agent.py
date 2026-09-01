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

        if any(w in user_lower for w in ["meteo", "tempo a", "tempo fa", "tempo farà", "previsioni", "pioverà", "piove", "temperatura"]):
            target_city = settings.assistant.default_city or "Roma"
            city_match = re.search(r"\b(?:a|ad|per|di)\s+([a-zA-Zàèéìòù]+)", user_text, re.IGNORECASE)
            if city_match:
                cand = city_match.group(1).strip()
                if cand.lower() not in ["oggi", "domani", "casa", "adesso", "questo", "questa", "sera", "mattina"]:
                    target_city = cand

            logger.info(f"[Shinra] Auto-recupero meteo in tempo reale per: {target_city}")
            w_res = await execute_tool("get_weather", {"location": target_city, "days": 2})
            actions_taken.append({"tool": "get_weather", "args": {"location": target_city, "days": 2}, "result": w_res})
            
            if w_res.get("success"):
                adesso = w_res.get("adesso", {})
                previsioni = w_res.get("previsioni", [])
                prev_text = "; ".join([f"{p.get('giorno')}: {p.get('condizione')}, max {p.get('temp_max')}°C, min {p.get('temp_min')}°C, probabilità pioggia {p.get('probabilita_pioggia')}" for p in previsioni])
                live_context = f"DATI METEO REALI ({w_res.get('localita', target_city)}): Adesso {adesso.get('temperatura', '')}, {adesso.get('condizione', '')}. Previsioni -> {prev_text}."
            else:
                live_context = f"DATI METEO: Impossibile recuperare il meteo per {target_city}."

        elif any(w in user_lower for w in ["notizie", "ultime notizie", "rassegna stampa", "cosa succede"]):
            logger.info(f"[Shinra] Auto-recupero notizie in tempo reale")
            n_res = await execute_tool("get_latest_news", {"category": "generale"})
            actions_taken.append({"tool": "get_latest_news", "args": {"category": "generale"}, "result": n_res})
            
            if n_res.get("success"):
                titoli = [item.get("titolo", "") for item in n_res.get("notizie", [])[:3]]
                live_context = f"ULTIME NOTIZIE REALI: " + " | ".join(titoli)

        elif any(w in user_lower for w in ["cosa significa", "chi era", "chi è", "definizione di", "cos'è", "che cos'è", "spiegami"]):
            clean_term = re.sub(r"^(cosa significa|chi era|chi è|definizione di|cos'è|che cos'è|spiegami|il termine|la parola)\s+", "", user_text, flags=re.IGNORECASE).strip(" ?.,\"'")
            if clean_term:
                logger.info(f"[Shinra] Auto-recupero Wikipedia per: {clean_term}")
                wiki_res = await execute_tool("search_wikipedia", {"query": clean_term})
                actions_taken.append({"tool": "search_wikipedia", "args": {"query": clean_term}, "result": wiki_res})
                if wiki_res.get("success"):
                    live_context = f"DEFINIZIONE/ENCICLOPEDIA PER '{clean_term.upper()}': {wiki_res.get('estratto', '')}"

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
