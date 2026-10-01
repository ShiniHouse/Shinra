import json
import logging
import re
from typing import Any, Dict, List, Optional

from shinra.config.prompt_templates import get_system_prompt
from shinra.config.settings import settings
from shinra.infra.data_store import data_store
from shinra.infra.homeassistant.client import client_home_assistant
from shinra.infra.llm.ollama import OllamaClient
from shinra.services.conoscenza import servizio_conoscenza
from shinra.services.cronaca import Cronaca
from shinra.services.intenti import Richiesta, instrada
from shinra.services.intenti.lingue import schemi
from shinra.services.memory import ConversationMemory, gestore_memorie
from shinra.services.user_manager import UserProfile, user_manager
from shinra.skills.registry import TOOLS_SCHEMA, execute_tool

logger = logging.getLogger("Shinra")


class ShinraAgent:
    def __init__(self):
        self.ollama = OllamaClient()
        self.ha = client_home_assistant()

    async def process_user_input(
        self,
        user_text: str,
        user_id: Optional[str] = None,
        user_profile: Optional[UserProfile] = None,
        session_memory: Optional[ConversationMemory] = None,
        max_tool_iterations: int = 4,
    ) -> Dict[str, Any]:
        """
        Elabora l'input dell'utente calibrando il comportamento sul profilo (adulto/bambino/ospite).
        """
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

        # 1a. La memoria della conversazione e' di questa persona, non di
        # tutta la casa. Si sceglie qui, dopo aver risolto il profilo, e non
        # nel chiamante: cosi' nessuna rotta nuova puo' dimenticarsene — che
        # e' esattamente com'e' nato il difetto (REL-03). Chi vuole una
        # memoria propria — un test, un canale separato — la passa e vince.
        mem = session_memory or gestore_memorie.per_utente(profile.id if profile else user_id)

        # Il racconto della richiesta, per il grafo del Cervello (issue #188).
        cronaca = Cronaca(profile.id if profile else user_id)
        cronaca.richiesta_ricevuta()

        # 1b. Argomenti vietati al profilo: si controlla prima di qualunque
        # altra cosa, altrimenti il fast-path potrebbe agire su una richiesta
        # che questo utente non ha il diritto di fare.
        from shinra.domain.argomenti_vietati import consenti

        # La lingua di chi sta parlando: quella del profilo, se l'ha scelta,
        # altrimenti quella dell'installazione (issue #36).
        lingua = schemi(getattr(profile, "lingua", "") or "")

        vietato = consenti(user_text, profile)
        if vietato:
            rifiuto = lingua.dice("argomento_vietato")
            mem.add_user_message(user_text)
            mem.add_assistant_message(rifiuto)
            cronaca.risposta_data(dal_modello=False)
            return {
                "response": rifiuto,
                "actions": [],
                "user": profile.model_dump() if profile else None,
                "success": True,
            }

        # 2. Instradamento sugli intenti.
        #
        # Prima qui c'erano duecento righe di `if`/`elif`: intervista, timer,
        # modalita', dispositivi, meteo, notizie, enciclopedia, una dopo
        # l'altra dentro questa stessa funzione. Ora ogni intento e' un
        # oggetto in `core/intenti/`, con la sua priorita' e i suoi test.
        # Aggiungerne uno non richiede di toccare questa funzione.
        richiesta = Richiesta(testo=user_text, profilo=profile, memoria=mem, azioni=actions_taken)
        risposta = await instrada(richiesta)
        if risposta is not None:
            mem.add_user_message(user_text)
            mem.add_assistant_message(risposta.testo)
            cronaca.azioni(richiesta.azioni)
            cronaca.risposta_data(dal_modello=False)
            return {
                "response": risposta.testo,
                "actions": richiesta.azioni,
                "user": profile.model_dump() if profile else None,
                "success": True,
                **risposta.extra,
            }

        actions_taken = richiesta.azioni

        # 3. Nessun intento ha risposto: si passa al modello.
        #
        # Il riepilogo della casa si chiede adesso, non prima: quando la
        # richiesta la risolve un intento — «accendi la luce della cucina» —
        # non serve a niente, e prima veniva chiesto lo stesso a ogni frase.
        ha_summary = ""
        if settings.home_assistant.enabled:
            ha_summary = await self.ha.get_relevant_entities_summary()

        conoscenza = await servizio_conoscenza.per_la_domanda(richiesta.testo)
        cronaca.conoscenza_consultata(servizio_conoscenza.fatti_usati())

        system_prompt = get_system_prompt(
            lingua=lingua,
            home_context_summary=ha_summary,
            default_city=settings.assistant.default_city,
            user_profile=profile,
            # Il recupero al posto dell'iniezione totale (issue #32). Sotto
            # i venticinque fatti manda tutto come prima: il problema esiste
            # a duecento fatti, non a venti.
            custom_knowledge=conoscenza,
            device_aliases=data_store.get_aliases_summary(),
            modes_summary=data_store.get_modes_summary(),
        )

        # Cio' che gli intenti hanno raccolto senza rispondere: oggi solo
        # l'estratto di Wikipedia, che informa il modello invece di essere
        # letto a voce cosi' com'e'.
        if richiesta.contesto:
            system_prompt += (
                "\n\n"
                + lingua.prompt_di("informazioni_in_tempo_reale")
                + "\n"
                + "\n".join(richiesta.contesto)
                + "\n"
                + lingua.prompt_di("informazioni_chiusura")
            )

        # 5. Aggiornamento memoria e messaggi
        mem.add_user_message(user_text)

        conversation_messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        conversation_messages.extend(mem.get_messages())

        # 6. Ciclo di Tool Calling con Gemma / Qwen
        # Attiva i tools complessi solo se il messaggio contiene richieste di domotica o ricerca web attiva
        # Le parole che fanno passare gli strumenti al modello, nella lingua di chi parla.
        ACTION_KEYWORDS = lingua.parole_azione
        needs_action_tools = any(kw in user_text.lower() for kw in ACTION_KEYWORDS)

        for iteration in range(max_tool_iterations):
            user_label = profile.name if profile else "Utente"
            logger.info(f"[Shinra] ({user_label}) Iterazione {iteration + 1} per: '{user_text}'")

            # Passa i tools solo se strettamente necessari e solo alla prima iterazione
            current_tools = (
                TOOLS_SCHEMA if (needs_action_tools and not richiesta.contesto and iteration == 0) else None
            )
            response = await self.ollama.chat(messages=conversation_messages, tools=current_tools)

            if not response.get("success"):
                err_msg = response.get("error") or "Ollama"
                logger.error(f"[Shinra] Errore Ollama: {err_msg}")
                cronaca.errore("modello")
                fallback = lingua.dice("errore_ollama", errore=err_msg)
                return {
                    "response": fallback,
                    "actions": actions_taken,
                    "user": profile.model_dump() if profile else None,
                    "success": False,
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
                    cronaca.strumento(t_name, t_args, t_res)
                    actions_taken.append({"tool": t_name, "args": t_args, "result": t_res})
                    mem.add_tool_interaction(t_name, t_args, t_res)

                    # Aggiunge il risultato per consentire a Shinra di formulare la risposta vocale naturale
                    conversation_messages.append({"role": "assistant", "content": content})
                    conversation_messages.append(
                        {
                            "role": "user",
                            "content": lingua.dice(
                                "risultato_operazione",
                                tool=t_name,
                                risultato=json.dumps(t_res, ensure_ascii=False),
                            ),
                        }
                    )
                    continue
                else:
                    final_text = content.strip() or lingua.dice("operazione_completata")
                    mem.add_assistant_message(final_text)
                    cronaca.risposta_data(dal_modello=True)
                    return {
                        "response": final_text,
                        "actions": actions_taken,
                        "user": profile.model_dump() if profile else None,
                        "success": True,
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
                cronaca.strumento(str(tool_name or ""), args, tool_result)

                actions_taken.append({"tool": tool_name, "args": args, "result": tool_result})
                mem.add_tool_interaction(tool_name, args, tool_result)

                conversation_messages.append(
                    {
                        "role": "tool",
                        "name": tool_name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        fallback = lingua.dice("dati_verificati")
        mem.add_assistant_message(fallback)
        cronaca.risposta_data(dal_modello=True)
        return {
            "response": fallback,
            "actions": actions_taken,
            "user": profile.model_dump() if profile else None,
            "success": True,
        }


# Istanza globale dell'agente
agent = ShinraAgent()
