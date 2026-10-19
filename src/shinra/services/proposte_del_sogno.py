"""Le proposte del sogno: le abitudini notate di notte (#261, #263).

Di notte il codice conta nel registro le azioni che una persona ripete alla stessa ora (`domain/abitudini.py`) e ne fa delle
**proposte**, con le prove. Non accende niente, non crea regole, non chiede al modello: una persona le vede e le accetta o le
scarta. Chi scarta non se le sente riproporre.

Non serve il modello: e' un conteggio. Gira comunque di notte, quando la casa dorme.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from shinra.domain import abitudini
from shinra.infra.db.proposte import proposte
from shinra.services import registro

logger = logging.getLogger("Shinra.Sogno")

TIPO_ABITUDINE = "abitudine"
GIORNI_DI_VALIDITA = 14
VOCI_AL_GIORNO = 1000
TETTO_SECONDI = 5 * 60


def _utc(adesso: Optional[datetime]) -> datetime:
    return (adesso or datetime.now(timezone.utc)).replace(tzinfo=None)


def _nel_fuso_di_casa(momento: str) -> Optional[datetime]:
    """Una data del registro (UTC, senza fuso) all'ora che segnava l'orologio di casa."""
    try:
        return datetime.fromisoformat(momento).replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def _voci_degli_ultimi_giorni(fine: datetime) -> list[dict[str, Any]]:
    voci: list[dict[str, Any]] = []
    for indietro in range(abitudini.FINESTRA_GIORNI + 1):
        al = fine - timedelta(days=indietro)
        dal = al - timedelta(days=1)
        for v in registro.voci(limite=VOCI_AL_GIORNO, dal=dal, al=al):
            if not v.get("attore") or v["attore"] == "guest":
                continue  # senza una persona non c'e' un'abitudine; gli ospiti non hanno memoria
            locale = _nel_fuso_di_casa(str(v["momento"]))
            if locale is not None:
                voci.append({**v, "momento": locale})
    return voci


def proponi_abitudini(adesso: Optional[datetime] = None) -> dict[str, int]:
    """Cerca le abitudini e scrive le proposte nuove. Ritorna quante ne ha viste e quante ne ha scritte."""
    fine = _utc(adesso)
    scade = fine + timedelta(days=GIORNI_DI_VALIDITA)
    locale = _nel_fuso_di_casa(fine.isoformat())
    if locale is None:
        return {"viste": 0, "scritte": 0}
    trovate = abitudini.trova(_voci_degli_ultimi_giorni(fine), locale)
    scritte = 0
    for a in trovate:
        dati = {
            "strumento": a.strumento,
            "bersaglio": a.bersaglio,
            "verbo": a.verbo,
            "orario": a.orario,
            "giorni": [g.isoformat() for g in a.giorni],
        }
        if proposte.proponi(a.profilo, TIPO_ABITUDINE, a.chiave, dati, fine, scade) is not None:
            scritte += 1
    # Mai un profilo, un bersaglio o un orario nel log: dice solo quanto ha fatto.
    logger.info("Sogno: %d abitudini notate, %d proposte nuove", len(trovate), scritte)
    return {"viste": len(trovate), "scritte": scritte}


async def _notte() -> None:
    from shinra.services.compito_notturno import compito_notturno

    async def lavoro() -> dict[str, int]:
        quante = proposte.purga_scadute(_utc(None))
        if quante:
            logger.info("Proposte del sogno scadute tolte: %d", quante)
        return proponi_abitudini()

    await compito_notturno.esegui("sogno_abitudini", lavoro, TETTO_SECONDI, serve_il_modello=False)


def avvia() -> bool:
    from shinra.infra.scheduler.motore import scheduler

    return scheduler.programma_giornaliero("sogno:abitudini", _notte, ora=4, minuto=10)


def ferma() -> None:
    from shinra.infra.scheduler.motore import scheduler

    scheduler.annulla("sogno:abitudini")
