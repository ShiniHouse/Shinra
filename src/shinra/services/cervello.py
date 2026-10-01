"""Mette insieme il grafo del Cervello: legge la casa e chiede al dominio di disegnarla.

Il dominio (`domain/cervello.py`) sa costruire il grafo ma non sa dove stanno
i dati. Questo servizio li raccoglie — il database, il catalogo degli
strumenti, lo stato dei sistemi — rispettando i permessi di chi chiede, e passa
tutto al dominio.

**Lo stato dei sistemi si legge da quello che il programma sa gia'.** Una regola
disattivata sta nel database; Home Assistant ha un canale degli eventi che e'
connesso o no; i modelli di Ollama si chiedono. Niente di questo si indovina nel
browser: il browser riceve `attivo`, `fermo` o `non_raggiungibile`, con il
motivo.

**La rete ha un tetto.** L'unica domanda che esce dal programma e' a Ollama, e
ha quattro decimi di secondo per rispondere: con un modello spento la scheda non deve
aspettare il timeout del client (trenta secondi) per dire che e' spento. La
risposta si tiene venti secondi, cosi' una dashboard che si aggiorna da sola non
bombarda Ollama.

Riferimento: issue #185.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
import time
from typing import Any, Dict, List, Optional, Tuple

from shinra.config.settings import settings
from shinra.domain import cervello as dominio
from shinra.infra.db import depositi
from shinra.infra.llm.ollama import OllamaClient
from shinra.services import eventi_casa, permessi

logger = logging.getLogger("Shinra.Cervello")

ATTESA_OLLAMA = 0.4
DURATA_CACHE = 20.0

_cache_modello: Optional[Tuple[float, Dict[str, Any]]] = None


def strumenti_noti() -> List[Dict[str, str]]:
    """Gli strumenti che il modello vede, ciascuno col suo dominio.

    Il dominio e' il nome del modulo in `skills/catalogo/`: la divisione che
    la #196 ha fatto per tenere ordinato il registro e' la stessa che serve
    qui, e che gli agenti di dominio (#190) riusano.
    """
    catalogo = importlib.import_module("shinra.skills.catalogo")

    trovati: List[Dict[str, str]] = []
    for info in pkgutil.iter_modules(catalogo.__path__):
        modulo = importlib.import_module(f"shinra.skills.catalogo.{info.name}")
        for schema in getattr(modulo, "SCHEMI", []):
            trovati.append({"nome": schema["function"]["name"], "dominio": info.name})
    return trovati


def agenti_noti() -> List[Dict[str, Any]]:
    """Gli agenti di dominio. Non esistono ancora: li portera' la #190.

    Il grafo e i contatori sono gia' pronti a riceverli: quando ci saranno,
    basta che questa funzione li elenchi.
    """
    return []


def modello_come_agente(modello: Dict[str, Any], strumenti: List[Dict[str, str]]) -> Dict[str, Any]:
    """Il modello di Ollama come nodo del grafo: e' lui che riceve la richiesta e sceglie gli strumenti.

    Senza questo nodo gli eventi dell'agente (#188) non avrebbero un punto da cui
    partire, e un errore del modello non avrebbe un posto in cui farsi vedere.
    Usa tutti gli strumenti, ed e' vero: li vede tutti a ogni richiesta con azione.
    """
    return {
        "id": "modello",
        "nome": "Modello (Ollama)",
        "pronto": modello.get("stato") == dominio.ATTIVO,
        "strumenti": [s["nome"] for s in strumenti],
    }


async def _stato_del_modello() -> Dict[str, Any]:
    global _cache_modello
    adesso = time.monotonic()
    if _cache_modello and adesso - _cache_modello[0] < DURATA_CACHE:
        return _cache_modello[1]

    cliente = OllamaClient()
    try:
        modelli = await asyncio.wait_for(cliente.get_available_models(), timeout=ATTESA_OLLAMA)
    except Exception as errore:  # un timeout o una connessione rifiutata: stesso significato
        logger.debug("Ollama non risponde: %s", errore)
        modelli = []

    if not modelli:
        esito = {
            "id": "modello",
            "nome": "Modello (Ollama)",
            "cluster": "agenti",
            "stato": dominio.NON_RAGGIUNGIBILE,
            "motivo": f"Ollama non risponde su {cliente.base_url}.",
        }
    elif cliente.model not in modelli:
        esito = {
            "id": "modello",
            "nome": "Modello (Ollama)",
            "cluster": "agenti",
            "stato": dominio.FERMO,
            "motivo": f"Il modello configurato «{cliente.model}» non e' fra quelli di Ollama: ollama pull {cliente.model}.",
        }
    else:
        esito = {"id": "modello", "nome": "Modello (Ollama)", "cluster": "agenti", "stato": dominio.ATTIVO}

    _cache_modello = (adesso, esito)
    return esito


def dimentica_il_modello() -> None:
    """Solo per i test: la cache dello stato di Ollama."""
    global _cache_modello
    _cache_modello = None


def _stato_di_home_assistant() -> Dict[str, Any]:
    base = {"id": "home_assistant", "nome": "Home Assistant", "cluster": "dispositivi"}
    if not settings.home_assistant.enabled:
        return {**base, "stato": dominio.FERMO, "motivo": "Home Assistant e' disattivato nelle impostazioni."}
    if eventi_casa.in_ascolto():
        return {**base, "stato": dominio.ATTIVO}
    return {
        **base,
        "stato": dominio.NON_RAGGIUNGIBILE,
        "motivo": "Il canale degli eventi di Home Assistant non e' connesso.",
    }


def _stato_delle_regole(regole: List[Dict[str, Any]]) -> Dict[str, Any]:
    base = {"id": "regole", "nome": "Regole", "cluster": "regole"}
    spente = [r.get("nome") or r.get("id") for r in regole if not r.get("attiva", True)]
    if spente:
        elenco = ", ".join(str(n) for n in spente[:5]) + (" e altre" if len(spente) > 5 else "")
        return {**base, "stato": dominio.FERMO, "motivo": f"Regole disattivate: {elenco}."}
    return {**base, "stato": dominio.ATTIVO}


def _stato_delle_notizie() -> Dict[str, Any]:
    base = {"id": "notizie", "nome": "Notizie", "cluster": "strumenti"}
    if any(f.get("enabled", True) for f in depositi.fonti.elenco()):
        return {**base, "stato": dominio.ATTIVO}
    return {**base, "stato": dominio.FERMO, "motivo": "Nessuna fonte di notizie attiva."}


def _stato_delle_notifiche() -> Dict[str, Any]:
    base = {"id": "notifiche", "nome": "Notifiche push", "cluster": "regole"}
    if depositi.sottoscrizioni_push.elenco():
        return {**base, "stato": dominio.ATTIVO}
    return {**base, "stato": dominio.FERMO, "motivo": "Nessun dispositivo iscritto alle notifiche."}


async def genera(profilo: Any = None) -> Dict[str, Any]:
    """Il grafo della casa, come lo puo' vedere `profilo`.

    La conoscenza compare solo a chi ha il permesso di leggerla: il resto — gli
    alias, le routine, le regole — e' quello che la stessa persona vede gia'
    nelle altre schede, e il Cervello non deve mostrare una porta laterale
    verso cose che l'interfaccia le nasconde.
    """
    regole = depositi.regole.elenco()
    modello = await _stato_del_modello()
    strumenti = strumenti_noti()

    return dominio.costruisci(
        alias=depositi.alias.elenco(),
        routine=depositi.modalita.elenco(),
        regole=regole,
        fatti=depositi.fatti.elenco(),
        strumenti=strumenti,
        agenti=[modello_come_agente(modello, strumenti), *agenti_noti()],
        sistemi=[
            _stato_di_home_assistant(),
            modello,
            _stato_delle_regole(regole),
            _stato_delle_notizie(),
            _stato_delle_notifiche(),
        ],
        vede_conoscenza=permessi.ha_permesso(profilo, permessi.LEGGI_CONOSCENZA),
    )
