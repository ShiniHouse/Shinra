"""Impostazioni, conoscenza, fonti di notizie, modelli, Alexa e registro delle azioni.

Riferimento: issue #196 (prima stava tutto in `routes_admin.py`).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import feedparser
from fastapi import APIRouter, Depends, Query

from shinra.api.sicurezza import (
    richiedi_amministratore,
    richiedi_autenticazione,
    richiedi_permesso,
)
from shinra.config.settings import AppConfig, reload_settings, save_config, settings
from shinra.infra.data_store import data_store
from shinra.services import permessi, registro

logger = logging.getLogger("Shinra.Admin")
# Ogni rotta di questo router richiede una sessione valida: e' il
# comportamento predefinito (SEC-01). Per aprire un varco bisogna
# dichiararlo in sicurezza.ROTTE_PUBBLICHE.
router = APIRouter(
    prefix="/api",
    tags=["Impostazioni e conoscenza"],
    dependencies=[Depends(richiedi_autenticazione)],
)


# --- KNOWLEDGE ENDPOINTS ---
@router.get("/knowledge")
async def list_knowledge():
    """Elenca i fatti della conoscenza di casa."""
    return data_store.get_knowledge()


@router.post("/knowledge", dependencies=[Depends(richiedi_permesso(permessi.SCRIVI_CONOSCENZA))])
async def save_knowledge(item: Dict[str, Any]):
    """Aggiunge o aggiorna un fatto della conoscenza di casa."""
    salvato = data_store.salva_fatto(item)
    return {"success": True, "item": salvato}


@router.delete("/knowledge/{item_id}", dependencies=[Depends(richiedi_permesso(permessi.SCRIVI_CONOSCENZA))])
async def delete_knowledge(item_id: str):
    """Cancella un fatto della conoscenza di casa."""
    return {"success": data_store.cancella_fatto(item_id)}


# --- SOURCES (RSS) ENDPOINTS ---
@router.get("/sources")
async def list_sources():
    """Elenca le fonti di notizie (feed RSS)."""
    return data_store.get_sources()


@router.post("/sources")
async def save_source(source: Dict[str, Any]):
    """Aggiunge o aggiorna una fonte di notizie."""
    salvata = data_store.salva_fonte(source)
    return {"success": True, "source": salvata}


@router.post("/sources/bulk-toggle")
async def bulk_toggle_sources(payload: Dict[str, Any]):
    """Accende o spegne tutte le fonti di notizie in una volta."""
    attive = bool(payload.get("enabled", True))
    quante = data_store.imposta_tutte_le_fonti(attive)
    return {"success": True, "count": quante, "enabled": attive}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Cancella una fonte di notizie."""
    return {"success": data_store.cancella_fonte(source_id)}


@router.get("/sources/test")
async def test_source(url: str = Query(...)):
    """Prova un indirizzo di feed prima di aggiungerlo: dice se e' valido e mostra tre titoli."""
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
    """Le impostazioni lette dal disco, con token e PIN mascherati."""
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
    """Salva le impostazioni. Un token o un PIN rimasti mascherati non sovrascrivono quelli veri."""
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
    from shinra.infra.llm.ollama import OllamaClient

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
