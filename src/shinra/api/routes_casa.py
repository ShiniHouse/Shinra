"""La casa: le entita' di Home Assistant, gli alias, le routine e la presenza.

Riferimento: issue #196 (prima stava tutto in `routes_admin.py`).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from shinra.api.sicurezza import (
    richiedi_autenticazione,
    richiedi_permesso,
)
from shinra.domain import grafo
from shinra.infra.data_store import data_store
from shinra.infra.homeassistant.client import client_home_assistant
from shinra.services import permessi
from shinra.services.regole import motore_regole
from shinra.skills.ha_tools import activate_mode, percorso_del_grafo

logger = logging.getLogger("Shinra.Admin")
# Ogni rotta di questo router richiede una sessione valida: e' il
# comportamento predefinito (SEC-01). Per aprire un varco bisogna
# dichiararlo in sicurezza.ROTTE_PUBBLICHE.
router = APIRouter(
    prefix="/api",
    tags=["Casa e routine"],
    dependencies=[Depends(richiedi_autenticazione)],
)
ha_client = client_home_assistant()


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
    """Restituisce tutte le entità HA raggruppate per dominio.

    Legge dalla cache degli stati quando la connessione agli eventi e' viva
    (issue #19): «Scopri dispositivi» diventa immediato invece di aspettare
    la rete.
    """
    states = await ha_client.stati_correnti()
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
    """Elenca gli alias: i nomi che la casa da' ai dispositivi («luce cucina»)."""
    return data_store.get_aliases()


@router.post("/aliases", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))])
async def save_alias(alias: Dict[str, Any]):
    """Crea o aggiorna un alias di dispositivo."""
    salvato = data_store.salva_alias(alias)
    return {"success": True, "alias": salvato}


@router.delete(
    "/aliases/{alias_id}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_IMPOSTAZIONI))]
)
async def delete_alias(alias_id: str):
    """Cancella un alias."""
    return {"success": data_store.cancella_alias(alias_id)}


# --- MODES ENDPOINTS ---
@router.get("/modes")
async def list_modes():
    """Elenca le routine (modalita') configurate."""
    return data_store.get_modes()


@router.post("/modes/valida")
async def valida_modalita(mode: Dict[str, Any]):
    """Cosa non va in questo grafo, senza salvarlo.

    L'editor la chiama mentre si disegna: sapere di aver lasciato un nodo
    scollegato **mentre** lo si sta facendo e' un'altra cosa dal saperlo al
    salvataggio, quando il disegno e' finito e correggerlo costa di piu'.
    """
    problemi = grafo.valida(mode.get("nodes") or [], mode.get("edges") or [])
    return {
        "valido": not problemi,
        "problemi": [{"tipo": p.tipo, "messaggio": p.messaggio, "nodi": list(p.nodi)} for p in problemi],
    }


@router.post("/modes", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def save_mode(mode: Dict[str, Any]):
    """Salva una routine, se il suo grafo sta in piedi.

    Un grafo con un ciclo o con un nodo scollegato si salva benissimo e poi
    non fa quello che chi l'ha disegnato si aspetta — e il momento in cui se
    ne accorge e' la sera in cui la routine doveva accendere le luci.
    Riferimento: issue #28.
    """
    problemi = grafo.valida(mode.get("nodes") or [], mode.get("edges") or [])
    if problemi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "messaggio": grafo.descrivi_problemi(problemi),
                "problemi": [
                    {"tipo": p.tipo, "messaggio": p.messaggio, "nodi": list(p.nodi)} for p in problemi
                ],
            },
        )

    salvata = data_store.salva_modalita(mode)

    # I nodi trigger diventano regole del motore della #27. La sincronizzazione
    # sta **dopo** il salvataggio perche' ha bisogno dell'identificativo, che
    # per una routine nuova nasce qui.
    regole_dal_grafo = motore_regole.sincronizza_dal_grafo(salvata)

    return {"success": True, "mode": salvata, "regole": regole_dal_grafo}


@router.post("/modes/simula", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def simula_modalita(mode: Dict[str, Any]):
    """Cosa farebbe questa routine adesso, senza farlo.

    Legge la casa vera — e' il punto: una simulazione su stati inventati dice
    quello che si vuole sentire. Non chiama nessun servizio e non manda
    nessun avviso: restituisce i passi in ordine e, per ogni condizione, il
    ramo che prenderebbe e perche'.

    Richiede il permesso di modificare le routine e non quello di attivarle:
    non esegue niente, ma legge lo stato di tutta la casa, e questo e' gia'
    piu' di quanto debba vedere chi puo' solo dire «attiva modalita' cinema».
    """
    nodi, archi = mode.get("nodes") or [], mode.get("edges") or []
    passi, decisioni = await percorso_del_grafo(nodi, archi)

    # I nodi toccati sono i passi, piu' le condizioni — che si attraversano
    # senza eseguirle — piu' gli inneschi da cui si parte. E' l'elenco che
    # serve all'editor per illuminare **solo** quello che succederebbe, e per
    # lasciare spento il ramo che stasera non si percorre.
    visitati = [
        *grafo.Grafo(nodi, archi).inizi(),
        *(n for n, _, _ in decisioni),
        *(p.id for p in passi),
    ]

    return {
        "passi": [{"node_id": p.id, "tipo": p.tipo} for p in passi],
        "decisioni": [{"node_id": n, "ramo": r, "motivo": m} for n, r, m in decisioni],
        "visitati": visitati,
    }


@router.delete("/modes/{mode_id}", dependencies=[Depends(richiedi_permesso(permessi.MODIFICA_MODALITA))])
async def delete_mode(mode_id: str):
    """Cancella una routine, e con lei le regole che il suo grafo aveva generato."""
    # Prima le regole, poi la routine: se cadesse in mezzo, resterebbe una
    # routine senza inneschi — fastidioso — invece di un innesco che ogni
    # mattina prova ad attivare una routine che non esiste piu'.
    rimosse = motore_regole.dimentica_il_grafo(mode_id)
    return {"success": data_store.cancella_modalita(mode_id), "regole_rimosse": rimosse}


@router.post(
    "/modes/{mode_name}/activate", dependencies=[Depends(richiedi_permesso(permessi.ATTIVA_MODALITA))]
)
async def trigger_mode(mode_name: str):
    """Esegue una routine per nome, con i permessi di chi la invoca."""
    result = await activate_mode(mode_name)
    return result


# --- PRESENZA ---
@router.get("/presenza")
async def stato_presenza():
    """Chi c'e' in casa adesso.

    `in_attesa` sono le persone che Home Assistant da' per uscite e a cui non
    crediamo ancora: e' il ritardo contro i buchi del GPS, e vederlo aiuta a
    capire perche' la casa non ha ancora reagito.
    """
    from shinra.services.presenza import presenza

    return presenza.dettaglio()
