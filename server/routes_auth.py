"""Accesso e sessioni. E' l'unico router pubblico del progetto.

Ogni rotta qui dentro deve poter essere raggiunta da chi non e' ancora
autenticato — altrimenti nessuno potrebbe mai autenticarsi. Per questo sono
poche, e nessuna restituisce dati di casa.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from core.user_manager import user_manager
from server import sicurezza

logger = logging.getLogger("Shinra.Auth")
router = APIRouter(prefix="/api/auth", tags=["Accesso"])


class RichiestaAccesso(BaseModel):
    pin: str
    user_id: Optional[str] = None


@router.get("/status")
async def stato_autenticazione(request: Request):
    """Dice al client se deve autenticarsi e, se lo e' gia', chi e'."""
    attiva = sicurezza.autenticazione_attiva()
    profilo = sicurezza.utente_corrente(request) if attiva else None
    return {
        "auth_enabled": attiva,
        "authenticated": (profilo is not None) if attiva else True,
        "protect_dashboard": True,
        "utente": profilo.model_dump(exclude={"pin"}) if profilo else None,
    }


@router.get("/profili")
async def profili_per_accesso():
    """Chi puo' accedere, per la schermata di scelta.

    Restituisce solo cio' che serve a disegnare la lista: identificativo, nome
    e avatar. Mai il PIN, mai le note, mai le preferenze. E' un elenco di nomi
    di famiglia visibile a chi raggiunge il servizio: accettabile su una rete
    domestica, e necessario perche' si possa scegliere chi si e'.
    """
    return [
        {
            "id": u.id,
            "name": u.name,
            "avatar_type": u.avatar_type,
            "role": u.role,
            "ha_pin": bool(u.pin),
        }
        for u in user_manager.get_users()
    ]


@router.post("/login")
async def accedi(req: RichiestaAccesso, request: Request, response: Response):
    """Verifica identita' e PIN, e apre una sessione."""
    if sicurezza.tentativi_esauriti(request):
        logger.warning(
            "Troppi tentativi di accesso falliti da %s", request.client.host if request.client else "?"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Troppi tentativi errati. Riprova fra cinque minuti.",
        )

    pin = (req.pin or "").strip()
    if not pin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inserisci il PIN.")

    # Chi sta provando ad accedere: il profilo indicato, o l'unico che ha un PIN.
    candidati = [u for u in user_manager.get_users() if u.pin]
    if req.user_id:
        candidati = [u for u in candidati if u.id == req.user_id]

    profilo = next((u for u in candidati if sicurezza.verifica_pin(pin, u.pin)), None)

    if not profilo:
        sicurezza.registra_tentativo_fallito(request)
        logger.warning(
            "Accesso rifiutato da %s (profilo richiesto: %s)",
            request.client.host if request.client else "?",
            req.user_id or "non indicato",
        )
        # Un solo messaggio per PIN errato e profilo inesistente: dire quale
        # dei due e' sbagliato aiuterebbe solo chi prova a indovinare.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Profilo o PIN non corretti.")

    sicurezza.azzera_tentativi(request)
    token = sicurezza.crea_sessione(profilo.id)
    sicurezza.imposta_cookie_sessione(response, token)
    logger.info("Accesso riuscito: %s", profilo.name)

    return {
        "success": True,
        "token": token,  # per i client che non usano i cookie
        "utente": profilo.model_dump(exclude={"pin"}),
    }


@router.post("/logout")
async def esci(request: Request, response: Response):
    sicurezza.chiudi_sessione(sicurezza.token_dalla_richiesta(request))
    sicurezza.rimuovi_cookie_sessione(response)
    return {"success": True}
