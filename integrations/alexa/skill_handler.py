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

    # 1. Apertura della Skill ("Alexa, apri Shinra") -> Chiede l'interlocutore
    if req_type == "LaunchRequest":
        welcome_msg = "Shinra online. Con chi parlo?"
        reprompt_msg = "Dimmi il tuo nome per iniziare."
        session_attributes["waiting_for_user"] = True
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

        # Se siamo in attesa del nome dell'utente
        if session_attributes.get("waiting_for_user"):
            profile = user_manager.find_user_by_name(user_query)
            session_attributes["waiting_for_user"] = False
            session_attributes["user_id"] = profile.id

            if profile.age_group == "child":
                reply = f"Ciao {profile.name}! Come posso aiutarti oggi?"
                reprompt = "Puoi chiedermi una curiosità, il meteo o cosa c'è acceso."
            elif profile.role == "admin":
                reply = f"{profile.name}. Dimmi."
                reprompt = "In cosa posso esserti utile?"
            else:
                reply = f"Ciao {profile.name}. A tua disposizione."
                reprompt = "Cosa vorresti fare?"

            return build_alexa_response(
                reply,
                reprompt,
                should_end_session=False,
                session_attributes=session_attributes
            )

        # Se l'utente è già stato identificato o ha fatto direttamente una domanda
        current_user_id = session_attributes.get("user_id")
        result = await agent.process_user_input(user_query, user_id=current_user_id)
        raw_reply = result.get("response", "Operazione completata.")
        reply = clean_text_for_tts(raw_reply) or "Operazione completata."

        return build_alexa_response(reply, should_end_session=True, session_attributes=session_attributes)

    # 3. Fine sessione
    elif req_type == "SessionEndedRequest":
        return build_alexa_response("Shinra offline.", should_end_session=True)

    return build_alexa_response("Ripeti la richiesta.", should_end_session=False, session_attributes=session_attributes)
