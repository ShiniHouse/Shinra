import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config.settings import (
    assicura_segreto_sessione,
    migra_segreti_su_env,
    settings,
    verifica_configurazione,
)
from core.agent import agent
from core.ha_client import HomeAssistantClient
from core.ollama_client import OllamaClient
from integrations.alexa.skill_handler import handle_alexa_request
from server.routes_admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Shinra")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Controlli e migrazioni all'avvio.

    Nessuno di questi passi puo' impedire l'avvio: un hub domotico che si
    rifiuta di partire lascia una casa senza controllo. I problemi vengono
    segnalati con chiarezza nel log e restano visibili.
    """
    migrati = migra_segreti_su_env()
    if migrati:
        logger.warning(
            "Segreti spostati da config.yaml a .env: %s. "
            "Se config.yaml e' mai finito in un commit, revoca subito quelle credenziali.",
            ", ".join(migrati),
        )

    if assicura_segreto_sessione():
        logger.info("Generato il segreto di sessione di questa installazione.")

    for problema in verifica_configurazione():
        logger.warning("Configurazione: %s", problema)

    yield


app = FastAPI(title="Shinra AI Hub", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(admin_router)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None


from fastapi.responses import Response

from core.tts_engine import NEURAL_VOICES, generate_speech_mp3


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve la dashboard web dell'assistente."""
    return templates.TemplateResponse(request=request, name="index.html", context={"settings": settings})


@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    """Endpoint per richieste di chat / voce dall'interfaccia web o client locali."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto.")

    result = await agent.process_user_input(user_text=payload.message, user_id=payload.user_id)
    return result


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "it-IT-DiegoNeural"
    rate: Optional[str] = "+0%"
    pitch: Optional[str] = "+0Hz"


@app.post("/api/tts")
async def tts_endpoint(payload: TTSRequest):
    """Genera audio vocale neurale MP3 in alta definizione."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Il testo per il TTS non può essere vuoto.")
    try:
        audio_bytes = await generate_speech_mp3(
            text=payload.text,
            voice=payload.voice or "it-IT-DiegoNeural",
            rate=payload.rate or "+0%",
            pitch=payload.pitch or "+0Hz",
        )
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Errore generazione TTS neurale: {e}")
        raise HTTPException(status_code=500, detail=f"Errore generazione audio: {e}") from e


@app.get("/api/tts/voices")
async def tts_voices_endpoint():
    """Restituisce le voci neurali disponibili nel server."""
    return NEURAL_VOICES


@app.post("/api/alexa")
async def alexa_skill_endpoint(request: Request):
    """
    Endpoint per Amazon Alexa Skill Kit.
    Riceve le richieste JSON dai dispositivi Echo / Alexa e restituisce la risposta vocale.
    """
    try:
        data = await request.json()
        req_type = data.get("request", {}).get("type", "Unknown")
        logger.info(f"Ricevuta richiesta Alexa Skill: {req_type}")
        response = await handle_alexa_request(data)
        return response
    except Exception as e:
        logger.error(f"Errore gestione richiesta Alexa: {e}")
        return {
            "version": "1.0",
            "response": {
                "outputSpeech": {"type": "PlainText", "text": "Si è verificato un errore interno. Riprova."},
                "shouldEndSession": True,
            },
        }


@app.get("/api/status")
async def status_endpoint():
    """Controlla lo stato dei servizi (Ollama, Home Assistant)."""
    ollama = OllamaClient()
    ollama_health = await ollama.check_health()

    ha = HomeAssistantClient()
    ha_health = await ha.check_connection()

    return {
        "status": "running",
        "ollama": ollama_health,
        "home_assistant": ha_health,
        "alexa_endpoint": "/api/alexa",
    }
