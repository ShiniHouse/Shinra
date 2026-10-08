# -*- coding: utf-8 -*-
"""Una routine detta a parole, controllata contro la casa vera (#210).

«La sera chiudo le tapparelle e accendo la luce del corridoio» e' un'abitudine.
Il modello la trasforma in una proposta; **il modello non e' fidato**: inventa
dispositivi, scrive azioni che non esistono, chiede cose che nessuna routine
deve poter fare. Qui la proposta passa da quattro filtri prima di arrivare
alla persona:

1. ogni dispositivo deve esistere davvero in Home Assistant (o essere un alias
   che ne indica uno): quelli inventati si scartano e si dice quali;
2. ogni azione deve essere di un tipo noto, con valori nei limiti;
3. niente di sensibile (serrature, allarme, garage): una routine non le apre,
   a prescindere dalla conferma che avrebbe poi;
4. la routine, trasformata nel grafo dell'editor, deve reggere la validazione e
   percorrersi fino in fondo con la prova a secco: **nessun servizio viene
   chiamato**, e la casa non cambia.

Le funzioni di controllo non leggono niente da sole: ricevono le entita' e gli
alias. Chi le usa (il motore dell'intervista) li prende da Home Assistant.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from shinra.domain import grafo, sensibilita
from shinra.services.intervista_comune import dice, sezione

logger = logging.getLogger("Shinra.Interview")

COMANDI = ("turn_on", "turn_off", "toggle", "open_cover", "close_cover", "stop_cover")
DOMINI = ("light", "switch", "cover", "climate", "fan", "media_player")
MAX_AZIONI = 12
MAX_PAUSA_S = 3600
MAX_MESSAGGIO = 200


def _normalizza(testo: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zà-ÿ0-9]+", " ", (testo or "").lower())).strip()


def _entita_di(riferimento: str, entita: Dict[str, str], alias: List[Dict[str, Any]]) -> Optional[str]:
    """Da cio' che ha scritto il modello a un `entity_id` vero, o `None`."""
    if riferimento in entita:
        return riferimento
    voluto = _normalizza(riferimento)
    if not voluto:
        return None
    for a in alias:
        if _normalizza(str(a.get("alias") or "")) == voluto and a.get("entity_id") in entita:
            return str(a["entity_id"])
    return None


def _numero(valore: Any, minimo: float, massimo: float) -> Optional[float]:
    try:
        n = float(valore)
    except (TypeError, ValueError):
        return None
    return n if minimo <= n <= massimo else None


def controlla_routine(
    grezza: Optional[Dict[str, Any]], entita: Dict[str, str], alias: List[Dict[str, Any]], lingua: str = ""
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """La routine ripulita e l'elenco di cosa si e' scartato (e perche').

    `entita` e' `entity_id -> nome`: l'unico elenco di dispositivi che vale.
    Se non resta nessuna azione la routine non e' proponibile: `None`. Le ragioni
    dello scarto sono scritte nella lingua di chi risponde (#207).
    """
    if not grezza or not grezza.get("name"):
        return None, []
    scartate: List[str] = []
    azioni: List[Dict[str, Any]] = []

    for a in (grezza.get("actions") or [])[:MAX_AZIONI]:
        if not isinstance(a, dict):
            continue
        tipo = str(a.get("type") or "ha_device")
        if tipo in ("ha_device", "ha_service"):
            rif = str(a.get("entity_id") or (a.get("data") or {}).get("entity_id") or "")
            reale = _entita_di(rif, entita, alias)
            if not reale:
                scartate.append(dice(lingua, "r_ignoto", rif=rif or "?"))
                continue
            comando = str(a.get("action") or a.get("service") or "turn_on")
            if comando not in COMANDI:
                scartate.append(dice(lingua, "r_comando", nome=entita[reale], comando=comando))
                continue
            if reale.split(".")[0] not in DOMINI or sensibilita.entita_sensibile(reale, comando):
                scartate.append(dice(lingua, "r_delicato", nome=entita[reale]))
                continue
            nuova: Dict[str, Any] = {"type": "ha_device", "entity_id": reale, "action": comando}
            luminosita = _numero(a.get("brightness"), 0, 100)
            if luminosita is not None:
                nuova["brightness"] = int(luminosita)
            temperatura = _numero(a.get("temperature"), 5, 35)
            if temperatura is not None:
                nuova["temperature"] = temperatura
            azioni.append(nuova)
        elif tipo == "delay":
            secondi = _numero(a.get("seconds") or a.get("delay_seconds"), 1, MAX_PAUSA_S)
            if secondi is None:
                scartate.append(dice(lingua, "r_pausa"))
                continue
            azioni.append({"type": "delay", "seconds": secondi})
        elif tipo == "tts":
            messaggio = str(a.get("message") or "").strip()
            if not messaggio or len(messaggio) > MAX_MESSAGGIO:
                scartate.append(dice(lingua, "r_annuncio"))
                continue
            azioni.append({"type": "tts", "message": messaggio})
        else:
            scartate.append(dice(lingua, "r_tipo", tipo=tipo))

    if not any(a["type"] != "delay" for a in azioni):
        return None, scartate
    routine = dict(grezza)
    routine["actions"] = azioni
    return routine, scartate


def routine_come_grafo(routine: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Il grafo dell'editor: l'innesco vocale, poi le azioni in fila."""
    nodi: List[Dict[str, Any]] = [{"id": "n0", "type": grafo.TRIGGER, "data": {}, "x": 80, "y": 80}]
    archi: List[Dict[str, Any]] = []
    for i, a in enumerate(routine.get("actions") or [], start=1):
        dati = {k: v for k, v in a.items() if k != "type"}
        nodi.append({"id": f"n{i}", "type": a["type"], "data": dati, "x": 80 + i * 260, "y": 80})
        archi.append({"from": f"n{i - 1}", "to": f"n{i}"})
    return nodi, archi


async def prova_a_secco(routine: Dict[str, Any], lingua: str = "") -> Tuple[bool, str]:
    """La routine regge il grafo e si percorre fino in fondo, senza eseguire niente."""
    from shinra.skills.ha_tools import percorso_del_grafo

    nodi, archi = routine_come_grafo(routine)
    problemi = grafo.valida(nodi, archi)
    if problemi:
        return False, grafo.descrivi_problemi(problemi)
    passi, _ = await percorso_del_grafo(nodi, archi)
    attesi = len(routine.get("actions") or [])
    if len(passi) != attesi:
        return False, dice(lingua, "r_prova_ferma", fatti=len(passi), attesi=attesi)
    return True, dice(lingua, "r_prova_ok", n=attesi)


def descrivi(routine: Dict[str, Any], entita: Dict[str, str], lingua: str = "") -> str:
    """I passi nella lingua di chi risponde, come li direbbe chi ha descritto l'abitudine."""
    comandi = sezione(lingua)["comandi"]
    righe = []
    for i, a in enumerate(routine.get("actions") or [], start=1):
        if a["type"] == "ha_device":
            nome = entita.get(a["entity_id"], a["entity_id"])
            extra = dice(lingua, "r_luminosita", valore=a["brightness"]) if "brightness" in a else ""
            extra += (
                dice(lingua, "r_temperatura", valore=f"{a['temperature']:g}") if "temperature" in a else ""
            )
            righe.append(f"{i}. {comandi.get(a['action'], a['action'])} «{nome}»{extra}")
        elif a["type"] == "delay":
            righe.append(f"{i}. " + dice(lingua, "r_pausa_voce", secondi=f"{a['seconds']:g}"))
        else:
            righe.append(f"{i}. " + dice(lingua, "r_dice", messaggio=a["message"]))
    return "\n".join(righe)


async def leggi_la_casa(archivio: Any) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """I dispositivi veri (`entity_id -> nome`) e gli alias, da Home Assistant e dal database.

    Se Home Assistant non risponde solleva: senza l'elenco vero non si puo'
    controllare niente, e una routine non controllata non si propone.
    """
    from shinra.skills.entita import stati_noti

    stati = await stati_noti()
    entita = {
        str(s["entity_id"]): str((s.get("attributes") or {}).get("friendly_name") or s["entity_id"])
        for s in stati
        if s.get("entity_id")
    }
    if not entita:
        raise ConnectionError("Home Assistant non ha dato nessun dispositivo")
    return entita, archivio.get_aliases()


async def controlla_proposta(
    grezza: Optional[Dict[str, Any]], archivio: Any, lingua: str = ""
) -> Optional[Dict[str, Any]]:
    """La proposta del modello, controllata contro la casa vera (#210).

    Senza una routine valida non si propone niente; con Home Assistant spento
    neppure: una routine che non si puo' controllare non si mostra.
    """
    if not grezza:
        return None
    try:
        entita, alias = await leggi_la_casa(archivio)
    except Exception as e:
        logger.warning("Routine proposta non controllabile (%s): non la propongo.", e)
        return None
    routine, scartate = controlla_routine(grezza, entita, alias, lingua)
    if routine is None:
        logger.info("Routine «%s» scartata: %s", grezza.get("name"), scartate)
        return None
    riuscita, esito = await prova_a_secco(routine, lingua)
    if not riuscita:
        logger.info("Routine «%s» non regge la prova a secco: %s", routine["name"], esito)
        return None
    routine.update(anteprima=descrivi(routine, entita, lingua), prova=esito, scartate=scartate)
    return routine


async def routine_da_salvare(
    proposta: Dict[str, Any], archivio: Any, lingua: str = ""
) -> Optional[Dict[str, Any]]:
    """Cio' che si salva davvero: la proposta ricontrollata, come grafo dell'editor.

    La proposta torna dal browser, e cio' che torna non e' piu' quello che
    abbiamo mostrato. Si rifa' il controllo contro la casa e si salva il grafo
    che esce dal controllo, non quello che e' arrivato.
    """
    extra = ("anteprima", "prova", "scartate")
    controllata = await controlla_proposta(
        {k: v for k, v in proposta.items() if k not in extra}, archivio, lingua
    )
    if controllata is None:
        return None
    nodi, archi = routine_come_grafo(controllata)
    pulita = {k: v for k, v in controllata.items() if k not in (*extra, "actions")}
    pulita.update(nodes=nodi, edges=archi, actions=[])
    return pulita
