"""Le rotte delle notifiche: registrare un telefono, scegliere cosa sentire.

Il giro dal lato del browser e' questo: chiede la chiave pubblica del server,
si registra presso il proprio servizio push, e ci consegna l'indirizzo e le
chiavi con cui cifrare. Da quel momento il telefono e' raggiungibile anche a
applicazione chiusa.

La chiave **pubblica** e' pubblica per mestiere — sta nel browser di chi si
registra — quindi la sua rotta e' l'unica leggibile da una sessione qualunque.
La privata non esce mai da `config/vapid.json`.

Riferimento: issue #29.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shinra.api.sicurezza import richiedi_autenticazione
from shinra.domain import notifiche as dominio
from shinra.services.notifiche import servizio_notifiche
from shinra.services.user_manager import UserProfile

logger = logging.getLogger("Shinra.Notifiche")

router = APIRouter(
    prefix="/api/notifiche",
    tags=["Notifiche"],
    dependencies=[Depends(richiedi_autenticazione)],
)


def _chi(profilo: Optional[UserProfile]) -> str:
    return profilo.id if profilo else "alessio"


class Sottoscrizione(BaseModel):
    """Cio' che il browser restituisce da `PushManager.subscribe()`."""

    endpoint: str
    p256dh: str
    auth: str
    nome: str = "Dispositivo"


class Preferenza(BaseModel):
    chiave: str = Field(description="`silenzioso`, `canale.push`, `categoria.energia`...")
    valore: bool


class Prova(BaseModel):
    titolo: str = "Prova"
    testo: str = "Se leggi questo, le notifiche funzionano."


@router.get("/chiave")
async def chiave_pubblica() -> Dict[str, Any]:
    """La chiave con cui il browser si registra.

    Se torna `null`, le notifiche non sono disponibili: o `pywebpush` non e'
    installato, o le chiavi non si sono potute generare. Il browser deve
    dirlo invece di mostrare un pulsante che non fa niente.
    """
    chiave = servizio_notifiche.chiave_pubblica()
    return {"chiave": chiave, "disponibile": chiave is not None}


@router.post("/sottoscrivi")
async def sottoscrivi(
    dati: Sottoscrizione, profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    """Registra questo telefono per la persona della sessione."""
    if not dati.endpoint.startswith("https://"):
        raise HTTPException(status_code=400, detail="Endpoint non valido.")

    voce = servizio_notifiche.registra_dispositivo(
        _chi(profilo), dati.endpoint, dati.p256dh, dati.auth, dati.nome
    )
    return {"success": True, "sottoscrizione": {"id": voce.get("id"), "nome": voce.get("nome")}}


@router.post("/dimentica")
async def dimentica(
    dati: Dict[str, str], profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    """Toglie un telefono, **solo se e' di chi lo chiede**.

    Senza quel vincolo chiunque avesse una sessione potrebbe togliere il
    telefono di un altro conoscendone l'endpoint, e l'altro smetterebbe di
    ricevere gli allarmi senza accorgersene.
    """
    endpoint = dati.get("endpoint") or ""
    if not endpoint:
        raise HTTPException(status_code=400, detail="Serve l'endpoint da dimenticare.")
    return {"success": servizio_notifiche.dimentica_dispositivo(endpoint, utente=_chi(profilo))}


@router.get("/dispositivi")
async def dispositivi(
    profilo: Optional[UserProfile] = Depends(richiedi_autenticazione),
) -> Dict[str, Any]:
    """I telefoni registrati di chi chiede."""
    return {"dispositivi": servizio_notifiche.dispositivi_di(_chi(profilo))}


@router.get("/preferenze")
async def leggi_preferenze(
    profilo: Optional[UserProfile] = Depends(richiedi_autenticazione),
) -> Dict[str, Any]:
    preferenze = servizio_notifiche.preferenze_di(_chi(profilo))
    return {
        "silenzioso": preferenze.silenzioso,
        "canali": {c: preferenze.vuole_canale(c) for c in dominio.CANALI},
        "categorie": {c: preferenze.vuole_categoria(c) for c in dominio.CATEGORIE},
        "non_silenziabili": sorted(dominio.NON_SILENZIABILI),
    }


@router.post("/preferenze")
async def imposta_preferenza(
    dati: Preferenza, profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    """Cambia una preferenza.

    Le categorie non silenziabili si rifiutano qui e non solo nel dominio:
    un'interfaccia che mostra un interruttore per la sicurezza e poi non lo
    rispetta e' peggio di un'interfaccia che non lo mostra.
    """
    if dati.chiave.startswith("categoria."):
        categoria = dati.chiave.split(".", 1)[1]
        if categoria in dominio.NON_SILENZIABILI and not dati.valore:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Gli avvisi di {categoria} non si possono silenziare: un allarme "
                    "che si puo' zittire per sbaglio non e' un allarme."
                ),
            )

    servizio_notifiche.imposta(_chi(profilo), dati.chiave, dati.valore)
    return {"success": True}


@router.post("/prova")
async def prova(
    dati: Prova, profilo: Optional[UserProfile] = Depends(richiedi_autenticazione)
) -> Dict[str, Any]:
    """Manda una notifica di prova a chi la chiede.

    Serve a rispondere alla domanda piu' frequente su un sistema di
    notifiche — «ma funziona?» — senza aspettare che scatti un allarme.
    """
    avviso = dominio.Avviso(
        categoria=dominio.PROMEMORIA,
        titolo=dati.titolo,
        testo=dati.testo,
        priorita=dominio.IMPORTANTE,
    )
    esito = await servizio_notifiche.avvisa(avviso, utente=_chi(profilo))
    return {"success": esito["inviate"] > 0, **esito}
