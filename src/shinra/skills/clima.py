"""Comandare e leggere il clima.

`domain/clima.py` decide cosa si puo' chiedere a questo termostato e cosa
no. Qui c'e' la chiamata a Home Assistant e la frase che torna alla persona.

Il rifiuto e' la parte che conta. Un termostato che non deumidifica, a cui si
manda `dry`, non risponde «non so farlo»: non fa niente. La persona sente
«fatto», va a dormire, e la mattina scopre che l'umidita' era la stessa. Per
questo ogni rifiuto porta con se' l'elenco di cosa il dispositivo sa fare
davvero.

Riferimento: issue #21.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from shinra.domain import clima as dominio
from shinra.skills.entita import (
    EntitaSconosciuta,
    attributi_di,
    nome_di,
    stati_noti,
    stato_di,
    verifica,
)

logger = logging.getLogger("Shinra.Clima")


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


def _con_alternative(errore: dominio.NonSaFarlo) -> Dict[str, Any]:
    messaggio = str(errore)
    if errore.alternative:
        messaggio += " Sa fare: " + ", ".join(errore.alternative) + "."
    return _fallito(messaggio, alternative=errore.alternative)


async def _chiama(servizio: str, dati: Dict[str, Any]) -> Dict[str, Any]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().call_service(dominio.DOMINIO, servizio, dati)


async def stato_clima(entity_id: str) -> Dict[str, Any]:
    """Com'e' impostato adesso, temperatura obiettivo compresa."""
    stati = await stati_noti()
    try:
        entita = await verifica(entity_id, {dominio.DOMINIO}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    attributi = attributi_di(entita, stati)
    nome = nome_di(entita, stati)
    riassunto = dominio.riassumi(stato_di(entita, stati), attributi)

    return _riuscito(
        f"{nome}: {riassunto}",
        entity_id=entita,
        temperatura_obiettivo=attributi.get("temperature"),
        temperatura_misurata=attributi.get("current_temperature"),
        modalita=stato_di(entita, stati),
    )


async def comanda_clima(
    entity_id: str,
    azione: str,
    modalita: Optional[str] = None,
    temperatura: Optional[float] = None,
    ventola: Optional[str] = None,
    umidita: Optional[int] = None,
    preset: Optional[str] = None,
) -> Dict[str, Any]:
    """Modalita', temperatura, ventola, umidita' obiettivo e preset."""
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {dominio.DOMINIO}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)
    sapute = dominio.capacita(attributi_di(entita, stati))

    if azione in ("stato", "leggi", "verifica"):
        return await stato_clima(entita)

    try:
        if azione in ("modalita", "imposta_modalita", "modo"):
            return await _modalita(entita, nome, modalita or "", sapute)

        if azione in ("temperatura", "imposta_temperatura", "gradi"):
            return await _temperatura(entita, nome, temperatura, sapute)

        if azione in ("ventola", "ventilazione", "velocita"):
            scelta = dominio.scegli_fra(ventola or "", sapute.ventole, "velocita' di ventola")
            return await _semplice("set_fan_mode", {"fan_mode": scelta}, entita, nome, f"ventola su {scelta}")

        if azione in ("umidita", "imposta_umidita", "deumidifica"):
            if umidita is None:
                return _fallito("Serve dire a che umidita' portarlo, in percentuale.")
            valore = dominio.umidifica(umidita, sapute)
            return await _semplice(
                "set_humidity",
                {"humidity": valore},
                entita,
                nome,
                f"umidita' obiettivo al {valore} per cento",
            )

        if azione in ("preset", "profilo"):
            scelta = dominio.scegli_fra(preset or "", sapute.preset, "modalita' predefinite")
            return await _semplice("set_preset_mode", {"preset_mode": scelta}, entita, nome, f"su «{scelta}»")

        if azione in ("spegni", "off"):
            return await _modalita(entita, nome, "off", sapute)

        if azione in ("accendi", "on"):
            # Senza dire quale modalita', si sceglie la prima che non sia
            # «spento»: accendere un termostato mettendolo su spento sarebbe
            # una risposta soddisfatta a una richiesta non eseguita.
            accese = [m for m in sapute.modalita if m != "off"]
            if not accese:
                return await _semplice("turn_on", {}, entita, nome, "acceso")
            return await _modalita(entita, nome, accese[0], sapute)

    except dominio.NonSaFarlo as e:
        return _con_alternative(e)

    return _fallito(f"Azione «{azione}» non prevista per il clima.")


async def _modalita(entita: str, nome: str, parola: str, sapute: dominio.Capacita) -> Dict[str, Any]:
    codice = dominio.scegli_modalita(parola, sapute)
    esito = await _chiama("set_hvac_mode", {"entity_id": entita, "hvac_mode": codice})
    detto = dominio.NOMI.get(codice, codice)
    return (
        _riuscito(f"{nome} in {detto}.")
        if esito.get("success")
        else _fallito(f"Non sono riuscito a mettere {nome} in {detto}.")
    )


async def _temperatura(
    entita: str, nome: str, valore: Optional[float], sapute: dominio.Capacita
) -> Dict[str, Any]:
    if valore is None:
        return _fallito("Serve dire a che temperatura portarlo.")

    gradi = dominio.tempera(valore, sapute)
    esito = await _chiama("set_temperature", {"entity_id": entita, "temperature": gradi})
    if not esito.get("success"):
        return _fallito(f"Non sono riuscito a cambiare la temperatura di {nome}.")

    # Se la richiesta e' stata accorciata, si dice: chi ha chiesto trenta
    # gradi e sente «fatto» crede di averne trenta.
    if abs(gradi - float(valore)) >= 0.1:
        return _riuscito(
            f"{nome} a {dominio.arrotonda(gradi)} gradi: e' il massimo che regge "
            f"(da {dominio.arrotonda(sapute.temperatura_minima)} a "
            f"{dominio.arrotonda(sapute.temperatura_massima)})."
        )
    return _riuscito(f"{nome} a {dominio.arrotonda(gradi)} gradi.")


async def _semplice(
    servizio: str, dati: Dict[str, Any], entita: str, nome: str, detto: str
) -> Dict[str, Any]:
    esito = await _chiama(servizio, {"entity_id": entita, **dati})
    return (
        _riuscito(f"{nome}: {detto}.")
        if esito.get("success")
        else _fallito(f"Non sono riuscito a mettere {nome} {detto}.")
    )
