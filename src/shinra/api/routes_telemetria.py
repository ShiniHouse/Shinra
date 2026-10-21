"""Quanto lavora il server di casa (la colonna «server» della console). Solo percentuali: niente nomi, indirizzi o processi."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from shinra.api.sicurezza import richiedi_autenticazione
from shinra.services import telemetria

router = APIRouter(
    prefix="/api/telemetria",
    tags=["Telemetria"],
    dependencies=[Depends(richiedi_autenticazione)],
)


@router.get("")
async def stato_del_server() -> Dict[str, Any]:
    """CPU, memoria, disco e temperatura adesso. `disponibile: false` dove non si possono leggere (non Linux)."""
    return await telemetria.campiona()
