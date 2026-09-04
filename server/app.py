import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
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
from core.user_manager import user_manager
from integrations.alexa.skill_handler import handle_alexa_request
from server import sicurezza
from server.routes_admin import router as admin_router
from server.routes_auth import router as auth_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("Shinra")

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


def _prepara_accesso() -> None:
    """Fa in modo che al primo avvio esista un modo per entrare.

    Con l'autenticazione attiva e nessun PIN configurato, imporre la
    protezione chiuderebbe fuori tutti — e in una casa questo significa
    restare senza controllo su luci e riscaldamento. Qui succedono due cose:

    - un PIN in chiaro rimasto in configurazione da una versione precedente
      viene trasferito sull'amministratore e cifrato;
    - se non esiste alcun PIN, ne viene generato uno e scritto nel log una
      volta sola, perche' il proprietario possa entrare e cambiarlo.
    """
    if not settings.security.auth_enabled:
        logger.warning(
            "Autenticazione disattivata: chiunque sia sulla rete puo' comandare "
            "l'impianto e leggere i dati della famiglia. Attivala dalle impostazioni."
        )
        return

    utenti = user_manager.get_users()
    if not utenti:
        return
    if any(u.pin for u in utenti):
        return

    amministratore = next((u for u in utenti if u.role == "admin"), utenti[0])

    pin_ereditato = (settings.security.admin_pin or "").strip()
    if pin_ereditato and not sicurezza.e_cifrato(pin_ereditato):
        user_manager.imposta_pin(amministratore.id, pin_ereditato)
        logger.warning(
            "Il PIN di %s e' stato preso dalla configurazione e cifrato. "
            "Da ora ogni familiare ha il proprio PIN.",
            amministratore.name,
        )
        return

    pin_nuovo = f"{secrets.randbelow(1_000_000):06d}"
    user_manager.imposta_pin(amministratore.id, pin_nuovo)
    logger.warning(
        "=== PRIMO ACCESSO ===  PIN per %s: %s  "
        "Compare solo in questo messaggio: annotalo e cambialo dalle impostazioni.",
        amministratore.name,
        pin_nuovo,
    )


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

    _prepara_accesso()

    for problema in verifica_configurazione():
        logger.warning("Configurazione: %s", problema)

    yield


app = FastAPI(title="Shinra AI Hub", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(auth_router)  # pubblico: e' l'accesso stesso
app.include_router(admin_router)  # protetto per difetto

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


@app.post("/api/chat", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
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


@app.post("/api/tts", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
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


@app.get("/api/tts/voices", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
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


@app.get("/health")
async def health_endpoint():
    """Sonda di liveness: dice solo che il processo risponde.

    Pubblica di proposito, e per questo non contiene nulla — niente modelli,
    niente indirizzo di Home Assistant, niente stato dei servizi. Quelle
    informazioni stanno in /api/status, che richiede una sessione.
    Serve a scripts/deploy.sh per capire se il servizio e' vivo dopo un
    riavvio senza doversi autenticare.
    """
    return {"status": "ok"}


@app.get("/api/status", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
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
