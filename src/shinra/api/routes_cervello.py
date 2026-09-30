"""Il Cervello: tutto quello che Shinra sa e fa, come grafo (issue #185)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from shinra.api.sicurezza import richiedi_autenticazione
from shinra.services import cervello
from shinra.services.user_manager import UserProfile

router = APIRouter(prefix="/api", tags=["Cervello"], dependencies=[Depends(richiedi_autenticazione)])


@router.get("/cervello")
async def grafo_del_cervello(
    profilo: Optional[UserProfile] = Depends(richiedi_autenticazione),
) -> Dict[str, Any]:
    """Nodi, collegamenti, cluster, stato dei sistemi e contatori della casa, per chi chiede.

    La conoscenza compare solo a chi ha il permesso di leggerla, e mai col suo
    contenuto: escono l'argomento e il fatto che esiste.
    """
    return await cervello.genera(profilo)
