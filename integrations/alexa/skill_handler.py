import logging
from typing import Dict, Any, Optional
from core.agent import agent
from core.user_manager import user_manager

from core.tts_engine import clean_text_for_tts

logger = logging.getLogger("Shinra.Alexa")

def build_alexa_response(
    speech_text: str,
    reprompt_text: str = "",
    should_end_session: bool = True,
    session_attributes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Genera la struttura JSON conforme alle specifiche Alexa Skill Kit."""
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
    Gestisce le richieste inviate dal servizio Alexa con flusso di identificazione utente ("Con chi parlo?").
    """
    request = request_data.get("request", {})
    req_type = request.get("type")
    session = request_data.get("session", {})
    session_attributes = session.get("attributes", {})

    # 1. Apertura della Skill ("Alexa, apri Shinra")
    if req_type == "LaunchRequest":
        users = user_manager.get_users()
        admin_user = users[0] if users else None
        user_name = admin_user.name if admin_user else "Alessio"
        user_id = admin_user.id if admin_user else "alessio"
        session_attributes["user_id"] = user_id
        
        welcome_msg = f"Shinra online, {user_name}. Dimmi pure."
        reprompt_msg = "Puoi chiedermi il meteo, una curiosità, le notizie o di controllare i dispositivi."
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

        # Gestione intenti standard di sistema Alexa
        if intent_name in ["AMAZON.StopIntent", "AMAZON.CancelIntent"]:
            return build_alexa_response("Shinra offline.", should_end_session=True)
        elif intent_name == "AMAZON.HelpIntent":
            help_text = (
                "Gestisco i dispositivi di casa tramite Home Assistant, fornisco previsioni meteo, "
                "notizie in tempo reale, spiegazioni e promemoria. Cosa ti serve?"
            )
            return build_alexa_response(help_text, "Dimmi pure.", should_end_session=False, session_attributes=session_attributes)
        elif intent_name == "AMAZON.FallbackIntent":
            return build_alexa_response(
                "Non ho capito bene la richiesta. Puoi chiedermi il meteo, una definizione, o di controllare i dispositivi.",
                "Cosa vorresti fare?",
                should_end_session=False,
                session_attributes=session_attributes
            )

        # Estrazione del testo della richiesta dell'utente
        slots = intent.get("slots", {})
        user_query = ""
        for slot_name, slot_data in slots.items():
            if "value" in slot_data:
                user_query = slot_data["value"]
                break

        if not user_query:
            user_query = intent.get("name", "").replace("_", " ")

        logger.info(f"[Alexa] Ricevuto: '{user_query}' | Attributi: {session_attributes}")

        # Cambio utente vocale esplicito ("sono Marco" / "parla con Sara")
        if user_query.lower().startswith(("sono ", "parla con ", "cambia utente ")):
            clean_name = re.sub(r"^(sono|parla con|cambia utente)\s+", "", user_query, flags=re.IGNORECASE).strip()
            profile = user_manager.find_user_by_name(clean_name)
            session_attributes["user_id"] = profile.id
            reply = f"Profilo impostato su {profile.name}. A tua disposizione."
            return build_alexa_response(reply, "Cosa posso fare per te?", should_end_session=False, session_attributes=session_attributes)

        current_user_id = session_attributes.get("user_id") or "alessio"
        result = await agent.process_user_input(user_query, user_id=current_user_id)
        raw_reply = result.get("response", "Operazione completata.")
        reply = clean_text_for_tts(raw_reply) or "Operazione completata."

        return build_alexa_response(reply, should_end_session=True, session_attributes=session_attributes)

    # 3. Fine sessione
    elif req_type == "SessionEndedRequest":
        return build_alexa_response("Shinra offline.", should_end_session=True)

    return build_alexa_response("Ripeti la richiesta.", should_end_session=False, session_attributes=session_attributes)
