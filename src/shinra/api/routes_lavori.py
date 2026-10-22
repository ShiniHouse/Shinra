"""I lavori in background: cosa sta facendo Shinra per me, e come fermarlo (#431, ADR 0013).

Ognuno vede **solo i propri** lavori; l'identificativo di un lavoro altrui riceve «non trovato» (404), come se non esistesse. Annullare
un lavoro e' un diritto di chi lo ha chiesto, e non serve altro permesso.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.services.lavori import LavoroNonTrovato, servizio_lavori

router = APIRouter(
    prefix="/api/lavori",
    tags=["Lavori"],
    dependencies=[Depends(richiedi_autenticazione)],
)


def _proprietario(request: Request) -> str:
    utente = utente_corrente(request)
    identificativo = str(getattr(utente, "id", "") or "")
    if not identificativo:
        # Senza un profilo non c'e' «i miei lavori»: nessuno vede niente.
        raise HTTPException(status_code=403, detail="Serve un profilo per vedere i propri lavori.")
    return identificativo


@router.get("")
async def elenco(request: Request) -> Dict[str, Any]:
    """I miei lavori, i piu' recenti per primi."""
    return {"lavori": servizio_lavori.elenco(_proprietario(request))}


@router.get("/{identificativo}")
async def dettaglio(identificativo: str, request: Request) -> Dict[str, Any]:
    """Un mio lavoro: a che punto e', e l'esito quando c'e'."""
    try:
        return servizio_lavori.trova(_proprietario(request), identificativo)
    except LavoroNonTrovato as e:
        raise HTTPException(status_code=404, detail="Lavoro non trovato.") from e


@router.post("/{identificativo}/annulla")
async def annulla(identificativo: str, request: Request) -> Dict[str, Any]:
    """Annulla un mio lavoro in coda o in corso. Uno gia' finito resta com'e'."""
    try:
        return await servizio_lavori.annulla(_proprietario(request), identificativo)
    except LavoroNonTrovato as e:
        raise HTTPException(status_code=404, detail="Lavoro non trovato.") from e
