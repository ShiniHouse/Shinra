"""Profili, ruoli, permessi e dispositivi fidati: chi c'e' in casa e cosa puo' fare.

Riferimento: issue #196 (prima stava tutto in `routes_admin.py`).
"""

import logging
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api import dispositivi
from shinra.api.sicurezza import (
    chiudi_sessioni_di,
    richiedi_autenticazione,
    richiedi_permesso,
)
from shinra.infra.db import depositi
from shinra.services import permessi, registro
from shinra.services.user_manager import UltimoAmministratore, UserProfile, user_manager

logger = logging.getLogger("Shinra.Admin")
# Ogni rotta di questo router richiede una sessione valida: e' il
# comportamento predefinito (SEC-01). Per aprire un varco bisogna
# dichiararlo in sicurezza.ROTTE_PUBBLICHE.
router = APIRouter(
    prefix="/api",
    tags=["Utenti e permessi"],
    dependencies=[Depends(richiedi_autenticazione)],
)


# --- User Models ---
class IdentifyRequest(BaseModel):
    text: str


# --- USERS ENDPOINTS ---
@router.get("/users")
async def list_users():
    """Elenca i profili della casa. Il PIN non esce mai."""
    return user_manager.get_users()


@router.get("/lingue")
async def list_lingue():
    """Le lingue che Shinra sa parlare, per il menu del profilo (issue #36)."""
    from shinra.services.intenti.lingue import elenco_lingue

    return elenco_lingue()


@router.post("/users", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def save_user(user: UserProfile):
    """Crea o aggiorna un profilo. Declassare l'ultimo amministratore e' rifiutato."""
    try:
        user_manager.upsert_user(user)
    except UltimoAmministratore as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    registro.registra("profilo.modificato", dettagli={"profilo": user.id, "ruolo": user.role})
    return {"success": True, "user": user}


@router.delete("/users/{user_id}", dependencies=[Depends(richiedi_permesso(permessi.GESTISCI_UTENTI))])
async def delete_user(user_id: str):
    """Cancella un profilo."""
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
    """Riconosce un profilo dal nome detto e restituisce il saluto adatto alla sua fascia d'eta'."""
    profile = user_manager.find_user_by_name(req.text)
    if profile.age_group == "child":
        greeting = f"Ciao {profile.name}! Come posso aiutarti oggi?"
    elif profile.role == "admin":
        greeting = f"{profile.name}. Sono online. Dimmi pure."
    else:
        greeting = f"Ciao {profile.name}, a tua disposizione."
    return {"user": profile, "greeting": greeting}


# --- RUOLI E PERMESSI ---
@router.get("/permessi")
async def elenco_permessi():
    """Il catalogo dei permessi: serve alla schermata dei ruoli."""
    return [{"id": p, "descrizione": d} for p, d in permessi.PERMESSI.items()]


@router.get("/ruoli")
async def elenco_ruoli():
    """Elenca i ruoli con i loro permessi."""
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
    """Cancella un ruolo personalizzato: i cinque predefiniti, e quelli con persone assegnate, no."""
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
    """Revoca un dispositivo fidato. Chi non e' amministratore puo' revocare solo i propri."""
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
