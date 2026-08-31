import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config.settings import settings, save_config, AppConfig
from core.agent import agent
from core.ollama_client import OllamaClient
from core.ha_client import HomeAssistantClient
from core.user_manager import user_manager
from integrations.alexa.skill_handler import handle_alexa_request
from server.routes_admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Shinra")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shinra AI Hub", version="2.0.0")
app.include_router(admin_router)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve la dashboard web dell'assistente."""
    return templates.TemplateResponse(request=request, name="index.html", context={"settings": settings})

@app.post("/api/chat")
async def chat_endpoint(payload: ChatRequest):
    """Endpoint per richieste di chat / voce dall'interfaccia web o client locali."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto.")
    
    result = await agent.process_user_input(
        user_text=payload.message,
        user_id=payload.user_id
    )
    return result

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
                "outputSpeech": {
                    "type": "PlainText",
                    "text": "Si è verificato un errore interno. Riprova."
                },
                "shouldEndSession": True
            }
        }

@app.get("/api/status")
async def status_endpoint():
    """Controlla lo stato dei servizi (Ollama, Home Assistant)."""
    ollama = OllamaClient()
    ollama_health = await ollama.check_health()
    
    ha = HomeAssistantClient(
        base_url=settings.home_assistant.url,
        token=settings.home_assistant.token
    )
    ha_health = await ha.check_connection()
    
    return {
        "status": "running",
        "ollama": ollama_health,
        "home_assistant": ha_health,
        "alexa_endpoint": "/api/alexa"
    }

@app.get("/api/ha/entities")
async def get_ha_entities():
    """Restituisce le entità caricate da Home Assistant."""
    ha = HomeAssistantClient(
        base_url=settings.home_assistant.url,
        token=settings.home_assistant.token
    )
    states = await ha.get_states()
    return {"count": len(states), "entities": states}
