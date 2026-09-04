import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse
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
from core.consegna import descrivi, registra_canali
from core.eventi import PROMEMORIA_SCADUTO, TIMER_SCADUTO, Evento, bus
from core.ha_client import client_home_assistant
from core.ollama_client import OllamaClient
from core.scheduler import scheduler
from core.timer_engine import timer_engine
from core.user_manager import user_manager
from integrations.alexa.skill_handler import handle_alexa_request
from integrations.alexa.verifica_firma import FirmaNonValida, verifica_richiesta
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

    # Un PIN in chiaro rimasto sul profilo da una versione precedente non
    # verrebbe mai riconosciuto: il confronto si aspetta un hash. Va cifrato
    # qui, altrimenti risulta "presente" e blocca la generazione, lasciando
    # chiusa fuori tutta la famiglia.
    migrati = [
        u.name
        for u in utenti
        if u.pin and not sicurezza.e_cifrato(u.pin) and user_manager.imposta_pin(u.id, u.pin)
    ]
    if migrati:
        logger.warning(
            "PIN cifrati per: %s. Restano quelli di prima, ora non piu' leggibili sul disco.",
            ", ".join(migrati),
        )
        utenti = user_manager.get_users()

    if any(sicurezza.e_cifrato(u.pin) for u in utenti):
        return

    amministratore = next((u for u in utenti if u.role == "admin"), utenti[0])

    pin_ereditato = (settings.security.admin_pin or "").strip()
    if pin_ereditato:
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

    # Scheduler: da qui timer e promemoria scattano lato server, anche a
    # browser chiuso e attraverso i riavvii.
    scheduler.avvia()
    registra_canali()
    ripresi = timer_engine.ripristina_job()
    rimossi = timer_engine.pulisci_scaduti()
    if any(ripresi.values()) or rimossi:
        logger.info(
            "Ripresi %d timer e %d promemoria; rimossi %d timer scaduti.",
            ripresi["timer"],
            ripresi["promemoria"],
            rimossi,
        )

    for problema in verifica_configurazione():
        logger.warning("Configurazione: %s", problema)

    yield

    # Spegnimento: i job restano nell'archivio per la prossima accensione.
    scheduler.ferma()
    await client_home_assistant().chiudi()


app = FastAPI(title="Shinra AI Hub", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def intestazioni_di_sicurezza(request: Request, call_next):
    """Aggiunge a ogni risposta le intestazioni che il browser sa far rispettare.

    Nessuna di queste sostituisce i controlli lato server: riducono il danno
    di un difetto che sfuggisse, e costano una riga ciascuna.
    """
    risposta = await call_next(request)
    risposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    risposta.headers.setdefault("X-Frame-Options", "DENY")
    risposta.headers.setdefault("Referrer-Policy", "same-origin")
    risposta.headers.setdefault("Permissions-Policy", "geolocation=(), camera=()")
    # microphone=() non compare: la dashboard usa il microfono per i comandi vocali.
    return risposta


@app.exception_handler(Exception)
async def errore_non_gestito(request: Request, exc: Exception):
    """Un errore imprevisto non deve raccontare com'e' fatto il server.

    Prima la traccia completa finiva nella risposta: nomi di file, percorsi,
    righe di codice. Ora resta nel log, dove serve, e al client arriva un
    messaggio generico.
    """
    logger.error("Errore non gestito su %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Si e' verificato un errore interno. Il dettaglio e' nel log del server."},
    )


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
    """Serve la dashboard, oppure la pagina di accesso a chi non e' entrato.

    Prima la dashboard veniva servita sempre, e la schermata di blocco era un
    rettangolo disegnato sopra: il markup era gia' arrivato al browser, e
    bastava chiudere l'overlay dagli strumenti sviluppatore — o disattivare
    JavaScript — per averla intera. La decisione ora e' del server.
    """
    if sicurezza.autenticazione_attiva() and sicurezza.utente_corrente(request) is None:
        return templates.TemplateResponse(
            request=request,
            name="accesso.html",
            context={"nome_assistente": settings.assistant.name},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
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
    """Endpoint per Amazon Alexa Skill Kit.

    E' l'unica porta di Shinra affacciata su Internet. Non e' protetta da una
    sessione — Amazon non ne ha una — ma dalla firma che Amazon appone su ogni
    richiesta. Chi non la supera non arriva all'agente.
    """
    if not settings.alexa.enabled:
        raise HTTPException(status_code=404, detail="Integrazione Alexa disattivata.")

    # Il corpo va letto grezzo: la firma copre i byte esatti inviati da
    # Amazon. Verificarla su un JSON riserializzato fallirebbe sempre, e
    # peggio ancora convaliderebbe un contenuto diverso da quello firmato.
    corpo = await request.body()

    try:
        data = json.loads(corpo)
        if not isinstance(data, dict):
            raise ValueError("il corpo non e' un oggetto JSON")
    except (ValueError, UnicodeDecodeError) as e:
        logger.warning("Richiesta Alexa con corpo illeggibile: %s", e)
        raise HTTPException(status_code=400, detail="Corpo della richiesta non valido.") from e

    try:
        await verifica_richiesta(
            corpo=corpo,
            intestazioni=dict(request.headers),
            dati=data,
            skill_id_atteso=settings.alexa.skill_id,
        )
    except FirmaNonValida as e:
        # Il motivo resta nel log: al chiamante si dice solo che e' stata
        # rifiutata, per non aiutare chi sta cercando di indovinare.
        logger.warning(
            "Richiesta Alexa rifiutata da %s: %s",
            request.client.host if request.client else "?",
            e,
        )
        raise HTTPException(status_code=400, detail="Richiesta non autenticata.") from e

    req_type = (data.get("request") or {}).get("type", "Sconosciuto")
    logger.info("Richiesta Alexa verificata: %s", req_type)

    try:
        return await handle_alexa_request(data)
    except Exception as e:
        # Solo qui si risponde con voce: la richiesta e' autentica, e un Echo
        # che resta muto e' peggio di uno che dice che qualcosa non va.
        logger.error("Errore gestione richiesta Alexa: %s", e, exc_info=True)
        return {
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": "Si e' verificato un errore interno. Riprova.",
                },
                "shouldEndSession": True,
            },
        }


@app.websocket("/ws/eventi")
async def eventi_websocket(websocket: WebSocket):
    """Eventi in tempo reale verso la dashboard.

    Sostituisce l'interrogazione periodica: la dashboard non chiede piu' «e'
    scaduto qualcosa?», riceve l'avviso nel momento in cui accade.
    """
    if sicurezza.autenticazione_attiva():
        token = websocket.cookies.get(sicurezza.NOME_COOKIE)
        if sicurezza.sessione_valida(token) is None:
            await websocket.close(code=1008)
            return

    await websocket.accept()
    coda: asyncio.Queue = asyncio.Queue()

    def accoda(evento: Evento) -> None:
        coda.put_nowait(descrivi(evento))

    annulla = [bus.sottoscrivi(t, accoda) for t in (TIMER_SCADUTO, PROMEMORIA_SCADUTO)]
    try:
        while True:
            await websocket.send_json(await coda.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        for a in annulla:
            a()


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

    ha = client_home_assistant()
    ha_health = await ha.check_connection()

    return {
        "status": "running",
        "ollama": ollama_health,
        "home_assistant": ha_health,
        "alexa_endpoint": "/api/alexa",
    }
