"""Le rotte dei ricordi: cosa sa Shinra, di casa e di me (#249, ADR 0009).

Ognuno vede **solo i propri** ricordi privati: la regola e' applicata dal servizio, non dall'interfaccia, e un identificativo
indovinato di un ricordo altrui riceve «non trovato» (404), come se non esistesse. Il registro delle azioni dice che e'
successo e quale campo, mai il testo.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.services import ricordi

router = APIRouter(
    prefix="/api/ricordi",
    tags=["Ricordi"],
    dependencies=[Depends(richiedi_autenticazione)],
)


class RicordoIn(BaseModel):
    testo: str
    categoria: str = "generale"
    ambito: str = "mio"
    importanza: int = 3


class RicordoModifica(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    importanza: Optional[int] = None
    stato: Optional[str] = None
    enabled: Optional[bool] = None


class Conferma(BaseModel):
    conferma: bool = False


def _errore(e: Exception) -> HTTPException:
    if isinstance(e, ricordi.RicordoNonTrovato):
        return HTTPException(status_code=404, detail="Ricordo non trovato.")
    if isinstance(e, ricordi.NonConsentito):
        return HTTPException(status_code=403, detail=str(e))
    return HTTPException(status_code=422, detail=str(e))


@router.get("")
async def elenco(
    request: Request,
    ambito: str = "tutti",
    origine: Optional[str] = None,
    stato: Optional[str] = None,
    importanza_min: Optional[int] = None,
) -> Dict[str, Any]:
    """I ricordi che chi chiede vede: della casa e propri, con i filtri per ambito, origine, stato e importanza."""
    try:
        return {"ricordi": ricordi.elenco(utente_corrente(request), ambito, origine, stato, importanza_min)}
    except ricordi.DatoNonValido as e:
        raise _errore(e) from e


@router.get("/miei")
async def miei(request: Request) -> Dict[str, Any]:
    """Solo i ricordi privati di chi chiede."""
    return {"ricordi": ricordi.elenco(utente_corrente(request), "mio")}


@router.post("")
async def scrivi(corpo: RicordoIn, request: Request) -> Dict[str, Any]:
    """Scrive un ricordo, della casa o proprio. Serve il permesso di insegnare cose nuove all'assistente."""
    try:
        return {
            "success": True,
            "ricordo": ricordi.crea(
                utente_corrente(request), corpo.testo, corpo.categoria, corpo.ambito, corpo.importanza
            ),
        }
    except (ricordi.NonConsentito, ricordi.DatoNonValido) as e:
        raise _errore(e) from e


@router.patch("/{identificativo}")
async def correggi(identificativo: str, corpo: RicordoModifica, request: Request) -> Dict[str, Any]:
    """Corregge un ricordo (testo, categoria, importanza, stato, acceso/spento). Il privato di un altro non esiste."""
    try:
        return {
            "success": True,
            "ricordo": ricordi.modifica(
                utente_corrente(request), identificativo, corpo.model_dump(exclude_none=True)
            ),
        }
    except (ricordi.RicordoNonTrovato, ricordi.NonConsentito, ricordi.DatoNonValido) as e:
        raise _errore(e) from e


@router.delete("/{identificativo}")
async def dimentica(identificativo: str, request: Request) -> Dict[str, Any]:
    """Cancella un ricordo e il suo vettore. Il proprio privato sempre; quelli della casa solo chi puo' scriverla."""
    try:
        return {"success": ricordi.cancella(utente_corrente(request), identificativo)}
    except (ricordi.RicordoNonTrovato, ricordi.NonConsentito) as e:
        raise _errore(e) from e


@router.post("/dimentica-tutto-di-me")
async def dimentica_tutto(corpo: Conferma, request: Request) -> Dict[str, Any]:
    """Cancella tutti i ricordi privati di chi chiede (non quelli della casa). Serve la conferma esplicita."""
    if not corpo.conferma:
        raise HTTPException(status_code=422, detail="Serve la conferma: «conferma»: true.")
    try:
        return {"success": True, "cancellati": ricordi.dimentica_tutto_di_me(utente_corrente(request))}
    except ricordi.NonConsentito as e:
        raise _errore(e) from e
