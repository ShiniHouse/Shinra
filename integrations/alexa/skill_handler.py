import logging
import re
from typing import Dict, Any, Optional
from config.settings import settings
from core.agent import agent
from core.user_manager import user_manager
from core.tts_engine import clean_text_for_tts

logger = logging.getLogger("Alexa.Skill")

def build_alexa_response(
    speech_text: str,
    reprompt_text: str = "",
    should_end_session: bool = True,
    session_attributes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Genera la struttura JSON conforme alle specifiche Amazon Alexa Skill Kit."""
    response: Dict[str, Any] = {
        "version": "1.0",
        "sessionAttributes": session_attributes or {},
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech_text
            },
            "shouldEndSession": should_end_session
        }
    }
    if reprompt_text:
        response["response"]["reprompt"] = {
            "outputSpeech": {
                "type": "PlainText",
                "text": reprompt_text
            }
        }
    return response

async def handle_alexa_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gestisce le richieste inviate dal servizio Amazon Alexa Skill Kit.
    Supporta apertura vocale continua, controllo dispositivi, cambio utente e query LLM.
    """
    request = request_data.get("request", {})
    req_type = request.get("type")
    session = request_data.get("session", {})
    session_attributes = session.get("attributes", {}) or {}
    assistant_name = getattr(settings.assistant, "name", "Kyra") or "Kyra"

    # 1. Apertura della Skill ("Alexa, apri Kyra")
    if req_type == "LaunchRequest":
        users = user_manager.get_users()
        admin_user = users[0] if users else None
        user_name = admin_user.name if admin_user else "Alessio"
        user_id = admin_user.id if admin_user else "alessio"
        session_attributes["user_id"] = user_id

        welcome_msg = f"{assistant_name} online, {user_name}. Dimmi pure."
        reprompt_msg = "Puoi chiedermi il meteo, le notizie, accendere una luce o attivare una modalità."
        return build_alexa_response(
            welcome_msg,
            reprompt_msg,
            should_end_session=False,
            session_attributes=session_attributes
        )

    # 2. Ricezione di un Intento o Comando Vocale
    elif req_type == "IntentRequest":
        intent = request.get("intent", {})
        intent_name = intent.get("name", "")

        # Intenti standard di sistema Alexa
        if intent_name in ["AMAZON.StopIntent", "AMAZON.CancelIntent"]:
            return build_alexa_response(f"{assistant_name} offline.", should_end_session=True)
        elif intent_name == "AMAZON.HelpIntent":
            help_text = (
                f"Sono {assistant_name}. Gestisco la domotica Home Assistant, "
                "previsioni meteo, notizie in tempo reale e rispondo alle tue domande. Cosa vorresti fare?"
            )
            return build_alexa_response(help_text, "Dimmi pure.", should_end_session=False, session_attributes=session_attributes)
        elif intent_name == "AMAZON.FallbackIntent":
            return build_alexa_response(
                "Non ho capito bene la richiesta. Puoi chiedermi il meteo, le notizie, o di controllare luci e prese.",
                "Cosa vorresti fare?",
                should_end_session=False,
                session_attributes=session_attributes
            )

        slots = intent.get("slots", {}) or {}
        user_query = ""

        # Gestione mirata in base all'intento specifico
        if intent_name == "TurnOnIntent":
            device = (slots.get("device", {}).get("value") or slots.get("query", {}).get("value") or "").strip()
            user_query = f"accendi {device}" if device else "accendi"
        elif intent_name == "TurnOffIntent":
            device = (slots.get("device", {}).get("value") or slots.get("query", {}).get("value") or "").strip()
            user_query = f"spegni {device}" if device else "spegni"
        elif intent_name == "ActivateModeIntent":
            mode = (slots.get("mode", {}).get("value") or slots.get("query", {}).get("value") or "").strip()
            user_query = f"modalità {mode}" if mode else "modalità"
        elif intent_name == "GeneralQueryIntent":
            user_query = (slots.get("query", {}).get("value") or slots.get("text", {}).get("value") or "").strip()
        
        # Fallback se non ancora trovato un testo
        if not user_query:
            for _, slot_data in slots.items():
                if "value" in slot_data and slot_data["value"]:
                    user_query = slot_data["value"].strip()
                    break

        if not user_query:
            user_query = intent_name.replace("_", " ")

        # Rimozione di eventuale prefisso di invocazione residuo che Alexa può aver catturato nello slot
        # Es: "kyra di accendere il salotto" -> "accendere il salotto"
        user_query = re.sub(
            r"^(?:alexa\s+|a\s+)?(?:kyra|kira|chira|shinra)\s+(?:di\s+)?",
            "",
            user_query,
            flags=re.IGNORECASE
        ).strip()

        # Normalizzazione forme verbali comuni domotica
        if user_query.lower().startswith("accendere "):
            user_query = "accendi " + user_query[10:]
        elif user_query.lower().startswith("spegnere "):
            user_query = "spegni " + user_query[9:]

        logger.info(f"[Alexa Intent: {intent_name}] Esecuzione: '{user_query}' | User: {session_attributes.get('user_id')}")

        # Cambio utente vocale esplicito ("sono Sonia" / "parla con Alessio" / "cambia utente in Sonia")
        if user_query.lower().startswith(("sono ", "parla con ", "cambia utente ")):
            clean_name = re.sub(r"^(sono|parla con|cambia utente(?:\s+in)?)\s+", "", user_query, flags=re.IGNORECASE).strip()
            profile = user_manager.find_user_by_name(clean_name)
            if profile:
                session_attributes["user_id"] = profile.id
                reply = f"Profilo impostato su {profile.name}. A tua disposizione."
                return build_alexa_response(reply, "Cosa posso fare per te?", should_end_session=False, session_attributes=session_attributes)

        current_user_id = session_attributes.get("user_id") or "alessio"
        result = await agent.process_user_input(user_query, user_id=current_user_id)
        raw_reply = result.get("response", "Operazione completata.")
        reply = clean_text_for_tts(raw_reply) or "Operazione completata."

        # Se la risposta finisce con una domanda (es. intervista o conferma), mantieni aperta la sessione vocale
        should_end = True
        reprompt = ""
        if reply.strip().endswith("?") or result.get("learning_active"):
            should_end = False
            reprompt = "Ti ascolto."

        return build_alexa_response(reply, reprompt_text=reprompt, should_end_session=should_end, session_attributes=session_attributes)

    # 3. Fine sessione
    elif req_type == "SessionEndedRequest":
        return build_alexa_response(f"{assistant_name} offline.", should_end_session=True)

    return build_alexa_response("Non ho compreso il comando.", should_end_session=False, session_attributes=session_attributes)
