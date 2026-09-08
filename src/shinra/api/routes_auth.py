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

from shinra.api import dispositivi, sicurezza
from shinra.services import permessi, registro
from shinra.services.user_manager import user_manager

logger = logging.getLogger("Shinra.Auth")
router = APIRouter(prefix="/api/auth", tags=["Accesso"])


class RichiestaAccesso(BaseModel):
    pin: str
    user_id: Optional[str] = None
    # «Ricorda questo dispositivo»: il compromesso che rende sopportabile un
    # PIN per persona su un telefono. Senza, la protezione verrebbe
    # disattivata dall'uso quotidiano nel giro di una settimana.
    ricorda_dispositivo: bool = False
    nome_dispositivo: Optional[str] = None


@router.get("/status")
async def stato_autenticazione(request: Request):
    """Dice al client se deve autenticarsi, chi e', e cosa puo' fare.

    I permessi viaggiano insieme all'identita' perche' la dashboard deve
    poter nascondere cio' che non serve: mostrare a un ragazzo il pannello
    dei ruoli, che poi il server rifiuta, non protegge nulla e fa solo
    sembrare rotta l'applicazione. Resta una comodita' visiva — chi decide
    e' sempre il server, su ogni singola rotta.

    Ad autenticazione spenta l'elenco e' completo: e' la stessa scelta che
    `permessi.ha_permesso` fa con un profilo assente, ed e' bene che
    l'interfaccia dica la verita' su com'e' configurata la casa.
    """
    attiva = sicurezza.autenticazione_attiva()
    profilo = sicurezza.utente_corrente(request) if attiva else None
    if not attiva:
        concessi = list(permessi.TUTTI)
    elif profilo is not None:
        concessi = sorted(permessi.permessi_del_ruolo(profilo.role))
    else:
        concessi = []
    return {
        "auth_enabled": attiva,
        "authenticated": (profilo is not None) if attiva else True,
        # Non e' piu' un'opzione: la dashboard non viene servita a chi non
        # e' entrato, e basta. Era una casella nelle impostazioni che non
        # comandava niente — questa riga era gia' `True` fissa — e prometteva
        # di poter *disattivare* la protezione, cioe' di riaprire il difetto
        # SEC-03 chiuso nella v0.1.0: il blocco era un rettangolo CSS sopra
        # dati gia' inviati. Resta nella risposta perche' la pagina la legge.
        "protect_dashboard": True,
        "utente": profilo.model_dump(exclude={"pin"}) if profilo else None,
        "permessi": concessi,
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
        registro.registra("accesso.bloccato", esito=registro.ESITO_NEGATO, canale="web")
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
        # Nel registro finisce quale profilo e' stato tentato, mai il PIN
        # provato: un registro che raccoglie PIN sbagliati e' un elenco di
        # quasi-PIN giusti.
        registro.registra(
            "accesso.rifiutato",
            esito=registro.ESITO_NEGATO,
            dettagli={"profilo_richiesto": req.user_id or "non indicato"},
            canale="web",
        )
        # Un solo messaggio per PIN errato e profilo inesistente: dire quale
        # dei due e' sbagliato aiuterebbe solo chi prova a indovinare.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Profilo o PIN non corretti.")

    sicurezza.azzera_tentativi(request)
    token = sicurezza.crea_sessione(profilo.id)
    sicurezza.imposta_cookie_sessione(response, token)
    logger.info("Accesso riuscito: %s", profilo.name)
    registro.imposta_attore(profilo.id)
    registro.registra("accesso.riuscito", dettagli={"nome": profilo.name}, canale="web")

    ricordato = False
    if req.ricorda_dispositivo:
        credenziale = dispositivi.ricorda(
            profilo.id,
            nome=req.nome_dispositivo or "Dispositivo",
            indirizzo=request.client.host if request.client else "",
            firma=sicurezza.firma_credenziale,
        )
        sicurezza.imposta_cookie_dispositivo(response, credenziale)
        registro.registra(
            "dispositivo.ricordato", dettagli={"nome": req.nome_dispositivo or ""}, canale="web"
        )
        ricordato = True

    return {
        "success": True,
        "token": token,  # per i client che non usano i cookie
        "utente": profilo.model_dump(exclude={"pin"}),
        "dispositivo_ricordato": ricordato,
    }


@router.post("/logout")
async def esci(request: Request, response: Response):
    profilo = sicurezza.utente_corrente(request)
    sicurezza.chiudi_sessione(sicurezza.token_dalla_richiesta(request))
    registro.registra("uscita", attore=profilo.id if profilo else None, canale="web")
    # Uscire non revoca il dispositivo: si esce per cambiare persona, non
    # perche' il telefono non sia piu' di casa. Per quello c'e' la revoca.
    sicurezza.rimuovi_cookie_sessione(response)
    return {"success": True}
