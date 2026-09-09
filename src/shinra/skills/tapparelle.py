"""Comandare e leggere tapparelle, tende e persiane.

`domain/tapparelle.py` decide cosa questo motore sa fare; qui c'e' la
chiamata a Home Assistant e la frase che torna alla persona.

Il verso della percentuale e' la cosa da tenere a mente leggendo questo file:
**cento e' aperta, zero e' chiusa.** «Portala al 40 per cento» vuol dire
aperta al 40, che a occhio e' una tapparella piuttosto abbassata — ed e'
quello che vede anche chi guarda la dashboard di Home Assistant.

Riferimento: issue #21.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from shinra.domain import tapparelle as dominio
from shinra.skills.entita import (
    EntitaSconosciuta,
    attributi_di,
    nome_di,
    stati_noti,
    stato_di,
    verifica,
)

logger = logging.getLogger("Shinra.Tapparelle")


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


async def _chiama(servizio: str, dati: Dict[str, Any]) -> Dict[str, Any]:
    from shinra.infra.homeassistant.client import client_home_assistant

    return await client_home_assistant().call_service(dominio.DOMINIO, servizio, dati)


async def stato_tapparella(entity_id: str) -> Dict[str, Any]:
    stati = await stati_noti()
    try:
        entita = await verifica(entity_id, {dominio.DOMINIO}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    attributi = attributi_di(entita, stati)
    nome = nome_di(entita, stati)

    return _riuscito(
        f"{nome}: {dominio.riassumi(stato_di(entita, stati), attributi)}.",
        entity_id=entita,
        posizione=dominio.posizione(attributi),
    )


async def comanda_tapparella(
    entity_id: str,
    azione: str,
    posizione: Optional[int] = None,
    lamelle: Optional[int] = None,
) -> Dict[str, Any]:
    """Apre, chiude, ferma, posiziona e orienta le lamelle."""
    azione = (azione or "").strip().lower()
    stati = await stati_noti()

    try:
        entita = await verifica(entity_id, {dominio.DOMINIO}, stati)
    except EntitaSconosciuta as e:
        return _fallito(str(e), suggerimenti=e.suggerimenti)

    nome = nome_di(entita, stati)
    sapute = dominio.capacita(attributi_di(entita, stati))

    if azione in ("stato", "leggi", "verifica"):
        return await stato_tapparella(entita)

    try:
        if azione in ("posizione", "imposta_posizione", "porta", "abbassa_a", "apri_a"):
            if posizione is None:
                return _fallito("Serve dire a che percentuale portarla.")
            dove = dominio.posiziona(posizione, sapute)
            return await _semplice(
                "set_cover_position",
                {"position": dove},
                entita,
                nome,
                _come_si_dice(dove),
            )

        if azione in ("lamelle", "orientamento", "inclina"):
            if lamelle is None:
                return _fallito("Serve dire a che percentuale orientare le lamelle.")
            dove = dominio.orienta(lamelle, sapute)
            return await _semplice(
                "set_cover_tilt_position",
                {"tilt_position": dove},
                entita,
                nome,
                f"lamelle al {dove} per cento",
            )

        if azione in ("ferma", "stop", "arresta"):
            dominio.ferma(sapute)
            return await _semplice("stop_cover", {}, entita, nome, "fermata")

        if azione in ("apri", "alza", "open"):
            # «Apri al 40» e' una posizione, non un'apertura: chi lo dice
            # vuole fermarsi al 40, non spalancare.
            if posizione is not None:
                dove = dominio.posiziona(posizione, sapute)
                return await _semplice(
                    "set_cover_position", {"position": dove}, entita, nome, _come_si_dice(dove)
                )
            return await _semplice("open_cover", {}, entita, nome, "aperta")

        if azione in ("chiudi", "abbassa", "close"):
            if posizione is not None:
                dove = dominio.posiziona(posizione, sapute)
                return await _semplice(
                    "set_cover_position", {"position": dove}, entita, nome, _come_si_dice(dove)
                )
            return await _semplice("close_cover", {}, entita, nome, "chiusa")

    except dominio.NonSaFarlo as e:
        return _fallito(str(e))

    return _fallito(f"Azione «{azione}» non prevista per una tapparella.")


def _come_si_dice(dove: int) -> str:
    if dove <= dominio.CHIUSA:
        return "chiusa"
    if dove >= dominio.APERTA:
        return "aperta del tutto"
    return f"aperta al {dove} per cento"


async def _semplice(
    servizio: str, dati: Dict[str, Any], entita: str, nome: str, detto: str
) -> Dict[str, Any]:
    esito = await _chiama(servizio, {"entity_id": entita, **dati})
    return (
        _riuscito(f"{nome} {detto}.")
        if esito.get("success")
        else _fallito(f"Non sono riuscito a mettere {nome} {detto}.")
    )
