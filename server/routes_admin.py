import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import feedparser
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from config.settings import AppConfig, reload_settings, save_config, settings
from core import permessi, registro
from core.archivio import depositi
from core.data_store import data_store
from core.ha_client import client_home_assistant
from core.tools.ha_tools import activate_mode
from core.user_manager import UltimoAmministratore, UserProfile, user_manager
from server import dispositivi
from server.sicurezza import (
    chiudi_sessioni_di,
    richiedi_amministratore,
    richiedi_autenticazione,
    richiedi_permesso,
)

logger = logging.getLogger("Shinra.Admin")
# Ogni rotta di questo router richiede una sessione valida. E' l'inversione
# che risolve SEC-01: prima la protezione era un controllo manuale presente su
# un endpoint su trentanove, adesso e' il comportamento predefinito e per
# aprire un varco bisogna dichiararlo in sicurezza.ROTTE_PUBBLICHE.
router = APIRouter(
    prefix="/api",
    tags=["Admin & Management"],
    dependencies=[Depends(richiedi_autenticazione)],
)
ha_client = client_home_assistant()


# --- User Models ---
class IdentifyRequest(BaseModel):
    text: str


# --- USERS ENDPOINTS ---
@router.get("/users")
async def list_users():
    return user_manager.get_users()


@router.post("/users", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def save_user(user: UserProfile):
    try:
        user_manager.upsert_user(user)
    except UltimoAmministratore as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    registro.registra("profilo.modificato", dettagli={"profilo": user.id, "ruolo": user.role})
    return {"success": True, "user": user}


@router.delete("/users/{user_id}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def delete_user(user_id: str):
    try:
        success = user_manager.delete_user(user_id)
    except UltimoAmministratore as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not success:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    revocati = dispositivi.revoca_tutti(user_id)
    registro.registra("profilo.cancellato", dettagli={"profilo": user_id, "dispositivi_revocati": revocati})
    return {"success": True, "dispositivi_revocati": revocati}


class ImpostaPinReq(BaseModel):
    pin: Optional[str] = None


@router.post("/users/{user_id}/pin", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def imposta_pin_utente(
    user_id: str,
    payload: ImpostaPinReq,
    request: Request,
    chiamante: Optional[UserProfile] = Depends(richiedi_autenticazione),
):
    """Imposta o rimuove il PIN di un profilo.

    Ciascuno puo' cambiare il proprio; l'amministratore puo' cambiare quello di
    chiunque — in una casa serve, quando un figlio dimentica il PIN.
    """
    if chiamante is not None and chiamante.id != user_id and chiamante.role != "admin":
        raise HTTPException(status_code=403, detail="Puoi cambiare solo il tuo PIN.")

    pin = (payload.pin or "").strip()
    if pin and (len(pin) < 4 or not pin.isdigit()):
        raise HTTPException(status_code=400, detail="Il PIN deve essere di almeno 4 cifre.")

    if not user_manager.imposta_pin(user_id, pin or None):
        raise HTTPException(status_code=404, detail="Utente non trovato")

    # Cambiare il PIN chiude le sessioni aperte con quello vecchio: se e' stato
    # cambiato perche' qualcuno lo aveva scoperto, lasciarle aperte sarebbe inutile.
    chiuse = chiudi_sessioni_di(user_id)

    # E revoca i dispositivi ricordati, tranne quello da cui si sta cambiando:
    # se il PIN e' stato cambiato perche' qualcuno lo aveva scoperto, un
    # telefono ancora fidato renderebbe il cambio inutile. Risparmiare il
    # proprio evita che l'unica conseguenza visibile sia doverlo ridigitare
    # subito — che e' il modo in cui una funzione di sicurezza viene evitata.
    revocati = dispositivi.revoca_tutti(
        user_id, tranne_credenziale=request.cookies.get(dispositivi.NOME_COOKIE)
    )
    logger.info(
        "PIN aggiornato per %s (%d sessioni chiuse, %d dispositivi revocati)", user_id, chiuse, revocati
    )
    registro.registra("pin.cambiato", dettagli={"profilo": user_id, "dispositivi_revocati": revocati})
    return {
        "success": True,
        "sessioni_chiuse": chiuse,
        "dispositivi_revocati": revocati,
        "pin_impostato": bool(pin),
    }


@router.post("/users/identify")
async def identify_user(req: IdentifyRequest):
    profile = user_manager.find_user_by_name(req.text)
    if profile.age_group == "child":
        greeting = f"Ciao {profile.name}! Come posso aiutarti oggi?"
    elif profile.role == "admin":
        greeting = f"{profile.name}. Sono online. Dimmi pure."
    else:
        greeting = f"Ciao {profile.name}, a tua disposizione."
    return {"user": profile, "greeting": greeting}


# --- KNOWLEDGE ENDPOINTS ---
@router.get("/knowledge")
async def list_knowledge():
    return data_store.get_knowledge()


@router.post("/knowledge", dependencies=[Depends(richiedi_permesso(permessi.SCRIVI_CONOSCENZA))])
async def save_knowledge(item: Dict[str, Any]):
    salvato = data_store.salva_fatto(item)
    return {"success": True, "item": salvato}


@router.delete("/knowledge/{item_id}", dependencies=[Depends(richiedi_permesso(permessi.SCRIVI_CONOSCENZA))])
async def delete_knowledge(item_id: str):
    return {"success": data_store.cancella_fatto(item_id)}


# --- SOURCES (RSS) ENDPOINTS ---
@router.get("/sources")
async def list_sources():
    return data_store.get_sources()


@router.post("/sources")
async def save_source(source: Dict[str, Any]):
    salvata = data_store.salva_fonte(source)
    return {"success": True, "source": salvata}


@router.post("/sources/bulk-toggle")
async def bulk_toggle_sources(payload: Dict[str, Any]):
    attive = bool(payload.get("enabled", True))
    quante = data_store.imposta_tutte_le_fonti(attive)
    return {"success": True, "count": quante, "enabled": attive}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    return {"success": data_store.cancella_fonte(source_id)}


@router.get("/sources/test")
async def test_source(url: str = Query(...)):
    try:

        def _parse():
            return feedparser.parse(url)

        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, _parse)

        if feed.bozo and not feed.entries:
            return {"valid": False, "error": "Feed non valido o non raggiungibile."}

        preview = []
        for entry in feed.entries[:3]:
            preview.append({"title": entry.get("title", ""), "published": entry.get("published", "")})
        return {
            "valid": True,
            "title": feed.feed.get("title", "Senza titolo"),
            "items_count": len(feed.entries),
            "preview": preview,
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


# --- HOME ASSISTANT ENTITIES ---
CONTROLLABLE_DOMAINS = [
    "light",
    "switch",
    "climate",
    "cover",
    "media_player",
    "fan",
    "scene",
    "script",
    "automation",
    "input_boolean",
    "vacuum",
    "lock",
]
ALL_VISIBLE_DOMAINS = [
    *CONTROLLABLE_DOMAINS,
    "sensor",
    "binary_sensor",
    "camera",
    "weather",
    "person",
    "device_tracker",
]

DOMAIN_LABELS = {
    "light": "💡 Luci",
    "switch": "🔌 Interruttori",
    "climate": "🌡️ Clima",
    "cover": "🪟 Tapparelle / Coperture",
    "media_player": "📺 Media Player",
    "fan": "💨 Ventilatori",
    "scene": "🎭 Scene",
    "script": "📜 Script",
    "automation": "⚡ Automazioni",
    "input_boolean": "🔘 Interruttori Virtuali",
    "vacuum": "🤖 Robot Aspirapolvere",
    "lock": "🔒 Serrature",
    "sensor": "📡 Sensori",
    "binary_sensor": "🔔 Sensori Binari",
    "weather": "☁️ Meteo",
    "person": "👤 Persone",
    "device_tracker": "📍 Tracker",
}


@router.get("/ha/entities")
async def get_ha_entities(domain: Optional[str] = None):
    """Restituisce tutte le entità HA raggruppate per dominio."""
    states = await ha_client.get_states()
    if not states:
        conn = await ha_client.check_connection()
        return {"error": True, "status": conn.get("status"), "message": conn.get("message"), "groups": {}}

    groups: Dict[str, List[Dict]] = {}
    current_aliases = {a.get("entity_id"): a.get("alias") for a in data_store.get_aliases()}

    for entity in states:
        entity_id = entity.get("entity_id", "")
        d = entity_id.split(".")[0]
        if domain and d != domain:
            continue
        if d not in ALL_VISIBLE_DOMAINS:
            continue
        groups.setdefault(d, [])
        groups[d].append(
            {
                "entity_id": entity_id,
                "friendly_name": entity.get("attributes", {}).get("friendly_name", entity_id),
                "state": entity.get("state", "unknown"),
                "unit": entity.get("attributes", {}).get("unit_of_measurement", ""),
                "domain": d,
                "domain_label": DOMAIN_LABELS.get(d, d),
                "controllable": d in CONTROLLABLE_DOMAINS,
                "alias": current_aliases.get(entity_id),
            }
        )

    # Ordina i gruppi per priorità (controllabili prima)
    ordered = {}
    for d in CONTROLLABLE_DOMAINS + [x for x in ALL_VISIBLE_DOMAINS if x not in CONTROLLABLE_DOMAINS]:
        if d in groups:
            ordered[d] = sorted(groups[d], key=lambda x: x["friendly_name"])

    return {"error": False, "groups": ordered, "total": sum(len(v) for v in ordered.values())}


# --- DEVICE ALIASES ENDPOINTS ---
@router.get("/aliases")
async def list_aliases():
    return data_store.get_aliases()


@router.post("/aliases", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))])
async def save_alias(alias: Dict[str, Any]):
    salvato = data_store.salva_alias(alias)
    return {"success": True, "alias": salvato}


@router.delete(
    "/aliases/{alias_id}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))]
)
async def delete_alias(alias_id: str):
    return {"success": data_store.cancella_alias(alias_id)}


# --- MODES ENDPOINTS ---
@router.get("/modes")
async def list_modes():
    return data_store.get_modes()


@router.post("/modes", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def save_mode(mode: Dict[str, Any]):
    salvata = data_store.salva_modalita(mode)
    return {"success": True, "mode": salvata}


@router.delete("/modes/{mode_id}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def delete_mode(mode_id: str):
    return {"success": data_store.cancella_modalita(mode_id)}


@router.post(
    "/modes/{mode_name}/activate", dependencies=[Depends(richiedi_permesso(permessi.ATTIVA_MODALITA))]
)
async def trigger_mode(mode_name: str):
    result = await activate_mode(mode_name)
    return result


# --- SETTINGS ENDPOINTS ---
def mask_secret(secret: Optional[str]) -> str:
    if not secret:
        return ""
    if len(secret) <= 8:
        return "********"
    return secret[:4] + "••••••••" + secret[-4:]


def is_masked(secret: Optional[str]) -> bool:
    if not secret:
        return False
    return "••••" in secret or "********" in secret or "***" in secret


@router.get("/settings", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))])
async def get_app_settings():
    # Qui la rilettura da disco e' voluta, ed e' l'unico posto che la fa.
    # Dalla issue #14 nessun altro punto del progetto legge config.yaml
    # durante una richiesta: si lavora sull'oggetto condiviso, che il
    # salvataggio aggiorna al suo posto. Il pannello impostazioni pero' deve
    # mostrare cosa c'e' davvero sul disco, perche' su un server capita di
    # correggere il file a mano.
    current = reload_settings().model_dump()
    # Maschera token sensibili
    if current.get("home_assistant", {}).get("token"):
        current["home_assistant"]["token"] = mask_secret(current["home_assistant"]["token"])
    if current.get("security", {}).get("admin_pin"):
        current["security"]["admin_pin"] = mask_secret(current["security"]["admin_pin"])
    return current


@router.post("/settings", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))])
async def update_app_settings(new_settings: AppConfig):
    current_cfg = reload_settings()

    # Preserva token Home Assistant se inviato mascherato o vuoto
    if (is_masked(new_settings.home_assistant.token) and current_cfg.home_assistant.token) or (
        not new_settings.home_assistant.token and current_cfg.home_assistant.token
    ):
        new_settings.home_assistant.token = current_cfg.home_assistant.token

    # Preserva PIN se inviato mascherato o vuoto con auth attiva
    if (is_masked(new_settings.security.admin_pin) and current_cfg.security.admin_pin) or (
        not new_settings.security.admin_pin
        and current_cfg.security.admin_pin
        and new_settings.security.auth_enabled
    ):
        new_settings.security.admin_pin = current_cfg.security.admin_pin

    # Nel registro finisce **quali sezioni** sono cambiate, mai i valori:
    # qui dentro passano il token di Home Assistant e il PIN di casa.
    cambiate = [
        sezione
        for sezione in new_settings.model_dump()
        if new_settings.model_dump()[sezione] != current_cfg.model_dump().get(sezione)
    ]
    save_config(new_settings)
    registro.registra("impostazioni.modificate", dettagli={"sezioni": cambiate})
    return await get_app_settings()


# --- OLLAMA MODELS DISCOVERY ---
@router.get("/ollama/models")
async def get_ollama_models():
    """Recupera la lista dettagliata dei modelli disponibili direttamente da Ollama."""
    from core.ollama_client import OllamaClient

    client = OllamaClient()
    models = await client.get_models_detailed()
    return {"success": True, "models": models, "active_model": client.model}


# --- ALEXA INTERACTION MODEL GENERATOR ---
@router.get("/alexa/interaction-model")
async def get_alexa_interaction_model(name: Optional[str] = None):
    """Restituisce lo schema JSON Interaction Model per Amazon Alexa Skill Kit con nome personalizzato."""
    clean_name = (name or settings.alexa.invocation_name or "kyra").lower().strip()
    return {
        "interactionModel": {
            "languageModel": {
                "invocationName": clean_name,
                "intents": [
                    {"name": "AMAZON.CancelIntent", "samples": []},
                    {"name": "AMAZON.HelpIntent", "samples": []},
                    {"name": "AMAZON.StopIntent", "samples": []},
                    {"name": "AMAZON.NavigateHomeIntent", "samples": []},
                    {"name": "AMAZON.FallbackIntent", "samples": []},
                    {
                        "name": "TurnOnIntent",
                        "slots": [{"name": "device", "type": "AMAZON.SearchQuery"}],
                        "samples": [
                            "accendi {device}",
                            "attiva {device}",
                            "apri {device}",
                            "accendere {device}",
                            "attivare {device}",
                        ],
                    },
                    {
                        "name": "TurnOffIntent",
                        "slots": [{"name": "device", "type": "AMAZON.SearchQuery"}],
                        "samples": [
                            "spegni {device}",
                            "disattiva {device}",
                            "chiudi {device}",
                            "spegnere {device}",
                            "disattivare {device}",
                        ],
                    },
                    {
                        "name": "ActivateModeIntent",
                        "slots": [{"name": "mode", "type": "AMAZON.SearchQuery"}],
                        "samples": [
                            "modalità {mode}",
                            "modalita {mode}",
                            "avvia {mode}",
                            "imposta {mode}",
                            "attiva modalità {mode}",
                            "attiva modalita {mode}",
                        ],
                    },
                    {
                        "name": "GeneralQueryIntent",
                        "slots": [{"name": "query", "type": "AMAZON.SearchQuery"}],
                        "samples": [
                            "dimmi {query}",
                            "chiedi {query}",
                            "fai {query}",
                            "esegui {query}",
                            "cosa {query}",
                            "come {query}",
                            "quando {query}",
                            "chi {query}",
                            "dove {query}",
                            "perché {query}",
                            "perche {query}",
                            "quanto {query}",
                            "quanti {query}",
                            "qual è {query}",
                            "qual e {query}",
                            "cerca {query}",
                            "spiegami {query}",
                            "fammi {query}",
                            "domanda {query}",
                            "voglio {query}",
                            "vorrei {query}",
                            "puoi {query}",
                        ],
                    },
                ],
                "types": [],
            }
        }
    }


# --- TIMERS & REMINDERS ENDPOINTS ---
from core.timer_engine import timer_engine


class CreateTimerReq(BaseModel):
    label: str = "Timer"
    duration_seconds: int = 60
    user_id: str = "alessio"


class CreateReminderReq(BaseModel):
    text: str
    remind_at: str
    user_id: str = "alessio"


@router.get("/timers")
async def list_timers():
    return timer_engine.get_timers()


@router.post("/timers")
async def create_timer(payload: CreateTimerReq):
    item = timer_engine.add_timer(payload.label, payload.duration_seconds, payload.user_id)
    return {"success": True, "timer": item}


@router.delete("/timers/{timer_id}")
async def remove_timer(timer_id: str):
    success = timer_engine.delete_timer(timer_id)
    return {"success": success}


@router.get("/reminders")
async def list_reminders():
    return timer_engine.get_reminders()


@router.post("/reminders")
async def create_reminder(payload: CreateReminderReq):
    item = timer_engine.add_reminder(payload.text, payload.remind_at, payload.user_id)
    return {"success": True, "reminder": item}


@router.delete("/reminders/{reminder_id}")
async def remove_reminder(reminder_id: str):
    success = timer_engine.delete_reminder(reminder_id)
    return {"success": success}


# --- LEARNING & INTERVIEW ENGINE ENDPOINTS ---
from core.interview_engine import interview_engine


class StartLearningReq(BaseModel):
    user_id: str = "alessio"


class AnswerLearningReq(BaseModel):
    user_id: str = "alessio"
    answer: str


class ConfirmRoutineReq(BaseModel):
    routine: Dict[str, Any]


@router.post("/learning/start")
async def start_learning_session(payload: StartLearningReq):
    res = interview_engine.start_session(payload.user_id)
    return res


@router.post("/learning/answer")
async def answer_learning_question(payload: AnswerLearningReq):
    res = await interview_engine.process_answer(payload.user_id, payload.answer)
    return res


@router.post("/learning/confirm-routine")
async def confirm_learning_routine(payload: ConfirmRoutineReq):
    res = interview_engine.confirm_routine(payload.routine)
    return res


@router.post("/learning/stop")
async def stop_learning_session(payload: StartLearningReq):
    interview_engine.stop_session(payload.user_id)
    return {"success": True, "message": "Sessione terminata."}


@router.get("/learning/status")
async def get_learning_status(user_id: str = "alessio"):
    session = interview_engine.get_session(user_id)
    return {"is_active": interview_engine.is_session_active(user_id), "session": session}


# --- REGISTRO DELLE AZIONI ---
@router.get("/registro", dependencies=[Depends(richiedi_amministratore)])
async def leggi_registro(
    limite: int = Query(100, ge=1, le=1000),
    attore: Optional[str] = None,
    azione: Optional[str] = None,
    canale: Optional[str] = None,
    esito: Optional[str] = None,
    correlazione: Optional[str] = None,
    ore: Optional[int] = Query(None, ge=1, le=24 * 365),
):
    """Chi ha fatto cosa in casa, e com'e' andata.

    Riservato agli amministratori, e non per formalita': queste righe dicono
    a che ora qualcuno e' rientrato, quando accende le luci, quando esce.
    Sono i movimenti della famiglia. Il ruolo `adult` non basta.
    """
    dal = datetime.now(timezone.utc) - timedelta(hours=ore) if ore else None
    return registro.voci(
        limite=limite,
        attore=attore,
        azione=azione,
        canale=canale,
        esito=esito,
        correlazione=correlazione,
        dal=dal,
    )


@router.get("/registro/azioni", dependencies=[Depends(richiedi_amministratore)])
async def azioni_registrate():
    """L'elenco dei tipi di azione presenti, per costruire i filtri."""
    voci = registro.voci(limite=1000)
    return sorted({v["azione"] for v in voci})


# --- RUOLI E PERMESSI ---
@router.get("/permessi")
async def elenco_permessi():
    """Il catalogo dei permessi: serve alla schermata dei ruoli."""
    return [{"id": p, "descrizione": d} for p, d in permessi.PERMESSI.items()]


@router.get("/ruoli")
async def elenco_ruoli():
    return depositi.ruoli.elenco()


@router.post("/ruoli", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def salva_ruolo(ruolo: Dict[str, Any]):
    """Crea o modifica un ruolo.

    I predefiniti si modificano — e' voluto: chi vuole togliere le serrature
    agli adulti deve poterlo fare senza inventarsi un ruolo nuovo. Quello che
    non si puo' fare e' cancellarli, o togliere all'amministratore il potere
    di gestire i profili: sarebbe il modo piu' rapido di chiudersi fuori.
    """
    identificativo = (ruolo.get("id") or "").strip().lower()
    if not identificativo:
        identificativo = re.sub(r"[^a-z0-9_]+", "_", (ruolo.get("nome") or "").strip().lower())
    if not identificativo:
        raise HTTPException(status_code=400, detail="Il ruolo deve avere un nome.")

    scelti = [p for p in (ruolo.get("permessi") or []) if p in permessi.PERMESSI]
    if identificativo == "admin" and permessi.GESTISCI_UTENTI not in scelti:
        raise HTTPException(
            status_code=400,
            detail="L'amministratore deve poter gestire i profili: senza, nessuno potrebbe piu' farlo.",
        )

    esistente = depositi.ruoli.per_id(identificativo)
    salvato = depositi.ruoli.salva(
        {
            "id": identificativo,
            "nome": ruolo.get("nome") or identificativo,
            "descrizione": ruolo.get("descrizione") or "",
            "permessi": scelti,
            "predefinito": bool(esistente["predefinito"]) if esistente else False,
        }
    )
    registro.registra(
        "ruolo.modificato" if esistente else "ruolo.creato",
        dettagli={"ruolo": identificativo, "permessi": scelti},
    )
    return {"success": True, "ruolo": salvato}


@router.delete("/ruoli/{id_ruolo}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def cancella_ruolo(id_ruolo: str):
    ruolo = depositi.ruoli.per_id(id_ruolo)
    if ruolo is None:
        raise HTTPException(status_code=404, detail="Ruolo non trovato.")
    if ruolo.get("predefinito"):
        raise HTTPException(status_code=400, detail="I ruoli predefiniti non si cancellano: si modificano.")

    assegnati = [u.name for u in user_manager.get_users() if u.role == id_ruolo]
    if assegnati:
        raise HTTPException(
            status_code=400,
            detail=f"Il ruolo e' assegnato a {', '.join(assegnati)}: cambia prima il loro ruolo.",
        )

    depositi.ruoli.cancella(id_ruolo)
    registro.registra("ruolo.cancellato", dettagli={"ruolo": id_ruolo})
    return {"success": True}


# --- DISPOSITIVI FIDATI ---
@router.get("/dispositivi")
async def elenco_dispositivi(
    request: Request, chiamante: Optional[UserProfile] = Depends(richiedi_autenticazione)
):
    """I dispositivi ricordati.

    Chi amministra li vede tutti; chiunque altro vede i propri. Sapere quali
    telefoni entrano in casa e' informazione di casa, non pubblica.

    Ogni riga dice anche se e' quella da cui si sta guardando: senza, l'elenco
    e' una fila di nomi identici e revocare il proprio e' l'errore piu'
    facile da fare.
    """
    righe = (
        dispositivi.elenco()
        if (chiamante is None or chiamante.role == "admin")
        else dispositivi.elenco(chiamante.id)
    )
    corrente = dispositivi.identificativo_di(request.cookies.get(dispositivi.NOME_COOKIE))
    for riga in righe:
        riga["questo"] = riga["id"] == corrente
    return righe


@router.delete("/dispositivi/{id_dispositivo}")
async def revoca_dispositivo(
    id_dispositivo: str, chiamante: Optional[UserProfile] = Depends(richiedi_autenticazione)
):
    proprietari = {d["id"]: d["user_id"] for d in dispositivi.elenco()}
    if id_dispositivo not in proprietari:
        raise HTTPException(status_code=404, detail="Dispositivo non trovato.")
    if chiamante is not None and chiamante.role != "admin" and proprietari[id_dispositivo] != chiamante.id:
        raise HTTPException(status_code=403, detail="Puoi revocare solo i tuoi dispositivi.")

    dispositivi.revoca(id_dispositivo)
    registro.registra("dispositivo.revocato", dettagli={"dispositivo": id_dispositivo})
    return {"success": True}


@router.post("/dispositivi/revoca-tutti")
async def revoca_tutti_i_dispositivi(
    request: Request, chiamante: Optional[UserProfile] = Depends(richiedi_autenticazione)
):
    """Il telefono perso.

    Tiene in vita quello da cui si sta chiedendo: chi ha perso il telefono lo
    fa dal computer di casa, e restare chiusi fuori nello stesso momento non
    aiuterebbe nessuno.
    """
    di_chi = None if (chiamante is None or chiamante.role == "admin") else chiamante.id
    revocati = dispositivi.revoca_tutti(
        di_chi, tranne_credenziale=request.cookies.get(dispositivi.NOME_COOKIE)
    )
    registro.registra("dispositivi.revocati", dettagli={"quanti": revocati})
    return {"success": True, "revocati": revocati}
