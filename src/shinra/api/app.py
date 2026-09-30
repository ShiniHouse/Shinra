import asyncio
import json
import logging
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from shinra import percorsi, versione
from shinra.api import sicurezza
from shinra.api.routes_attivita import router as attivita_router
from shinra.api.routes_auth import router as auth_router
from shinra.api.routes_casa import router as casa_router
from shinra.api.routes_cervello import router as cervello_router
from shinra.api.routes_conoscenza import router as conoscenza_router
from shinra.api.routes_impostazioni import router as impostazioni_router
from shinra.api.routes_notifiche import router as notifiche_router
from shinra.api.routes_regole import router as regole_router
from shinra.api.routes_utenti import router as utenti_router
from shinra.api.routes_voce import router as voce_router
from shinra.api.routes_voci import router as voci_router
from shinra.channels.alexa.skill_handler import handle_alexa_request
from shinra.channels.alexa.verifica_firma import FirmaNonValida, verifica_richiesta
from shinra.config.settings import (
    settings,
)
from shinra.domain import contesto
from shinra.domain.eventi import (
    AVVISO,
    CASA_ABITATA,
    CASA_INTRUSIONE,
    CASA_VUOTA,
    HA_STATO_CAMBIATO,
    PERSONA_RIENTRATA,
    PERSONA_USCITA,
    PROMEMORIA_SCADUTO,
    TIMER_SCADUTO,
    Evento,
    bus,
)
from shinra.infra.homeassistant.client import client_home_assistant
from shinra.infra.llm.ollama import OllamaClient
from shinra.services import registro
from shinra.services.agent import agent
from shinra.services.consegna import descrivi
from shinra.services.satelliti import registro_satelliti

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
# I lavori di avvio che girano in sottofondo. Tenerne un riferimento e'
# necessario: `asyncio` non lo fa, e un task non referenziato puo'
# sparire a meta'.
_in_sottofondo: set = set()

logger = logging.getLogger("Shinra")

BASE_DIR = percorsi.RADICE
TEMPLATES_DIR = percorsi.MODELLI_HTML
STATIC_DIR = percorsi.STATICI
STATIC_DIR.mkdir(parents=True, exist_ok=True)


from shinra.api.ciclo_di_vita import (  # noqa: F401  (i test e gli strumenti li importano da qui)
    _prepara_accesso,
    _prepara_archivio,
    _pulisci_registro,
    lifespan,
)

app = FastAPI(title="Shinra AI Hub", version="2.0.0", lifespan=lifespan)


class FileStatici(StaticFiles):
    """I file statici, da rivalidare a ogni richiesta.

    Dalla #34 il JavaScript e' fatto di moduli ES, e un `import` non puo'
    portare con se' il numero di versione: `principale.js?v=...` cambia a ogni
    rilascio, ma `./stato.js` dentro di lui resta lo stesso indirizzo. Senza
    istruzioni un browser puo' tenere un modulo vecchio per ore (la
    cache euristica e' una frazione dell'eta' del file), e dopo un
    aggiornamento la pagina girerebbe con un'area nuova e una vecchia.

    `no-cache` non vuol dire «non tenerlo»: vuol dire «chiedi prima se e'
    cambiato». Con l'ETag che `StaticFiles` manda gia', la risposta di un file
    invariato e' un 304 senza corpo.
    """

    def file_response(self, *args, **kwargs):
        risposta = super().file_response(*args, **kwargs)
        risposta.headers["Cache-Control"] = "no-cache"
        return risposta


app.mount("/static", FileStatici(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def contesto_del_registro(request: Request, call_next):
    """Apre il contesto della richiesta: chi, da dove, con quale correlazione.

    Sta in un middleware e non nelle singole rotte per la stessa ragione per
    cui la memoria si sceglie dentro l'agente: cosi' nessuna rotta nuova puo'
    dimenticarsene. L'identificativo di correlazione torna anche al client
    nell'intestazione della risposta, cosi' una segnalazione («stamattina non
    si e' accesa la luce») si ritrova nel registro senza cercare a mano.
    """
    ctx = registro.apri_contesto(canale="web")
    sessione = sicurezza.sessione_dalla_richiesta(request)
    if sessione:
        ctx.attore = sessione.user_id

    risposta = await call_next(request)
    risposta.headers["X-Correlazione"] = ctx.correlazione
    return risposta


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
app.include_router(utenti_router)  # protetto per difetto
app.include_router(casa_router)  # protetto per difetto
app.include_router(cervello_router)  # protetto per difetto
app.include_router(impostazioni_router)  # protetto per difetto
app.include_router(attivita_router)  # protetto per difetto
app.include_router(notifiche_router)  # protetto per difetto
app.include_router(regole_router)  # protetto per difetto
app.include_router(conoscenza_router)  # protetto per difetto
app.include_router(voci_router)  # protetto per difetto
app.include_router(voce_router)  # protetto per difetto

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    # Da quale punto di ascolto arriva (issue #33). La dashboard lo manda se
    # si e' dichiarata satellite di una stanza; chi non lo manda continua a
    # funzionare come prima.
    satellite: Optional[str] = None


from fastapi.responses import Response

from shinra.infra.tts import NEURAL_VOICES, generate_speech_mp3


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
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        # La versione arriva col disegno della pagina: nessuna chiamata in
        # piu', e resta corretta anche se il resto non risponde.
        context={"settings": settings, "versione": versione.dettaglio()},
    )


@app.post("/api/chat", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
async def chat_endpoint(payload: ChatRequest):
    """Endpoint per richieste di chat / voce dall'interfaccia web o client locali."""
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto.")

    if payload.satellite:
        # Chi ha sentito la frase per primo risponde; agli altri si dice che
        # e' gia' stata presa in carico, e non si esegue niente. Due
        # dispositivi sullo stesso tavolo sentono la stessa cosa, e due
        # esecuzioni della stessa richiesta su una serranda si notano.
        if not registro_satelliti.prende_in_carico(payload.satellite, payload.message):
            return {"response": "", "gia_in_carico": True}
        contesto.dichiara_stanza(registro_satelliti.stanza_di(payload.satellite))

    result = await agent.process_user_input(user_text=payload.message, user_id=payload.user_id)
    return result


class SatelliteIn(BaseModel):
    id: str
    nome: Optional[str] = ""
    stanza: Optional[str] = ""


@app.post("/api/satelliti", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
async def annuncia_satellite(payload: SatelliteIn):
    """Un punto di ascolto si presenta e dice in quale stanza si trova.

    Non chiede il permesso di modificare niente: dichiarare dove ci si trova
    non cambia la casa, cambia solo a chi si riferiscono le proprie frasi. Il
    permesso serve per **comandare**, e quello si controlla dove si comanda.
    """
    if not payload.id.strip():
        raise HTTPException(status_code=400, detail="Un satellite ha bisogno di un identificativo.")

    satellite = registro_satelliti.annuncia(payload.id.strip(), payload.nome or "", payload.stanza or "")
    return {"success": True, "stanza": satellite.stanza}


@app.get("/api/satelliti", dependencies=[Depends(sicurezza.richiedi_autenticazione)])
async def elenco_satelliti():
    """Chi sta ascoltando, e da dove."""
    return {"satelliti": registro_satelliti.per_l_interfaccia()}


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
    # Il canale conta nel registro: «chi ha spento il riscaldamento» ha una
    # risposta diversa se e' stato detto a voce in cucina o cliccato dalla
    # dashboard. Il middleware l'ha aperto come "web", qui si corregge.
    registro.contesto().canale = "alexa"

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
    # Si chiede a `sessione_dalla_richiesta` come fa tutto il resto, invece di
    # guardare il solo cookie di sessione. Le sessioni stanno in memoria: dopo
    # un riavvio del servizio il cookie di sessione del browser e' morto, ma
    # quello del dispositivo fidato no. Le rotte HTTP lo sapevano e da li'
    # coniavano una sessione nuova; questa rotta no, e chiudeva con 1008 —
    # cioe' un 403 sull'handshake — a ogni tentativo, per sempre. La dashboard
    # restava aperta e funzionante e non riceveva piu' un solo evento: niente
    # timer scaduti, niente promemoria, niente allarme intrusione (issue #159).
    if sicurezza.autenticazione_attiva() and sicurezza.sessione_dalla_richiesta(websocket) is None:
        # Un rifiuto muto e' costato un'indagine intera: nel journal si vedeva
        # un 403 ogni trenta secondi e nient'altro (issue #161).
        logger.info("Canale eventi rifiutato: %s", sicurezza.motivo_senza_sessione(websocket))
        await websocket.close(code=1008)
        return

    await websocket.accept()
    coda: asyncio.Queue = asyncio.Queue()

    def accoda(evento: Evento) -> None:
        coda.put_nowait(descrivi(evento))

    annulla = [
        bus.sottoscrivi(t, accoda)
        for t in (
            TIMER_SCADUTO,
            PROMEMORIA_SCADUTO,
            HA_STATO_CAMBIATO,
            # Chi entra e chi esce: senza questi la scritta «chi c'e' in
            # casa» resterebbe ferma al caricamento della pagina.
            PERSONA_RIENTRATA,
            PERSONA_USCITA,
            CASA_ABITATA,
            CASA_VUOTA,
            # Gli avvisi gia' formati dal servizio notifiche, e l'allarme.
            # `casa.intrusione` non era in questo elenco: veniva pubblicato e
            # non arrivava nemmeno a una dashboard aperta (issue #29).
            AVVISO,
            CASA_INTRUSIONE,
        )
    ]
    # Questa rotta parlava e basta: restava ferma su `coda.get()` e non
    # leggeva mai dal socket. Un canale che non ascolta non si accorge di
    # niente — ne' del browser che chiude la scheda, ne' del server che
    # sta spegnendosi.
    #
    # Il secondo caso costava novanta secondi a ogni riavvio. Uvicorn, per
    # fermarsi, chiede a ogni connessione di chiudersi e **poi aspetta**
    # che se ne vadano, senza scadenza. La chiusura arriva qui come un
    # messaggio da leggere; nessuno lo leggeva, la connessione non se ne
    # andava, e dopo novanta secondi systemd sparava un SIGKILL — che non
    # e' una fermata, e' un'esecuzione: tutto cio' che sta dopo lo `yield`
    # nel lifespan non veniva eseguito. Misurato: senza websocket il
    # servizio muore in due decimi di secondo, con una aperta non muore.
    #
    # Riferimento: issue #118.
    ascolto = asyncio.create_task(websocket.receive())
    try:
        while True:
            prossimo = asyncio.create_task(coda.get())
            finiti, _ = await asyncio.wait({prossimo, ascolto}, return_when=asyncio.FIRST_COMPLETED)

            if ascolto in finiti:
                prossimo.cancel()
                if ascolto.result().get("type") == "websocket.disconnect":
                    break
                # La dashboard non manda niente, ma se un giorno lo
                # facesse: si torna ad ascoltare invece di chiudere.
                ascolto = asyncio.create_task(websocket.receive())
                continue

            await websocket.send_json(prossimo.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        ascolto.cancel()
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
        "versione": versione.dettaglio(),
        "ollama": ollama_health,
        "home_assistant": ha_health,
        "alexa_endpoint": "/api/alexa",
    }
