"""Le rotte dei ricordi: cosa sa Shinra, di casa e di me (#249, ADR 0009).

Ognuno vede **solo i propri** ricordi privati: la regola e' applicata dal servizio, non dall'interfaccia, e un identificativo
indovinato di un ricordo altrui riceve «non trovato» (404), come se non esistesse. Il registro delle azioni dice che e'
successo e quale campo, mai il testo.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from shinra.api.sicurezza import richiedi_autenticazione, utente_corrente
from shinra.services import ricordi, ricordi_file

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
    luogo_id: str = ""


class RicordoModifica(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    importanza: Optional[int] = None
    stato: Optional[str] = None
    enabled: Optional[bool] = None
    luogo_id: Optional[str] = None


class Conferma(BaseModel):
    conferma: bool = False


class FileDiRicordi(BaseModel):
    ambito: str = "mio"
    contenuto: str


class ImportaFile(FileDiRicordi):
    conferma: bool = False
    # Cio' che manca dal file: se vero, i ricordi mancanti vengono archiviati (mai cancellati).
    togli: bool = False


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


@router.get("/esporta", response_class=PlainTextResponse)
async def esporta(request: Request, ambito: str = "mio") -> PlainTextResponse:
    """I ricordi di un ambito (`mio` o `casa`) come file Markdown. Contiene dati personali: va tenuto al sicuro."""
    try:
        testo = ricordi_file.esporta(utente_corrente(request), ambito)
    except (ricordi.DatoNonValido, ricordi.NonConsentito) as e:
        raise _errore(e) from e
    return PlainTextResponse(
        testo,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="memorie-{ambito}.md"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/importa/anteprima")
async def anteprima_importazione(corpo: FileDiRicordi, request: Request) -> Dict[str, Any]:
    """Cosa cambierebbe rileggendo un file di ricordi (nuovi, modificati, tolti). Non scrive niente."""
    try:
        return ricordi_file.anteprima(utente_corrente(request), corpo.ambito, corpo.contenuto)
    except (ricordi.DatoNonValido, ricordi.NonConsentito) as e:
        raise _errore(e) from e


@router.post("/importa")
async def importa(corpo: ImportaFile, request: Request) -> Dict[str, Any]:
    """Applica un file di ricordi, dopo l'anteprima e solo con la conferma. Chi manca dal file si archivia solo se lo chiedi."""
    try:
        return {
            "success": True,
            **ricordi_file.applica(
                utente_corrente(request), corpo.ambito, corpo.contenuto, corpo.conferma, corpo.togli
            ),
        }
    except (ricordi.DatoNonValido, ricordi.NonConsentito) as e:
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
                utente_corrente(request),
                corpo.testo,
                corpo.categoria,
                corpo.ambito,
                corpo.importanza,
                corpo.luogo_id,
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
