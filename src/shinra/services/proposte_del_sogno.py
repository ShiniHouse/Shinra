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


# ------------------------------------------------------------------ le proposte, per chi le riceve


class PropostaNonTrovata(LookupError):
    """Non esiste, oppure e' di un altro: per chi chiede e' la stessa cosa."""


def _id_profilo(profilo: Any) -> str:
    return str(getattr(profilo, "id", "") or "")


def elenco(profilo: Any) -> list[dict[str, Any]]:
    """Le proposte in attesa di chi chiede. Mai quelle di un altro; senza un profilo, nessuna."""
    chi = _id_profilo(profilo)
    return proposte.del_profilo(chi) if chi else []


def _sua(profilo: Any, identificativo: str) -> dict[str, Any]:
    chi = _id_profilo(profilo)
    trovata = proposte.trova(identificativo) if chi else None
    if trovata is None or trovata["profilo"] != chi:
        raise PropostaNonTrovata(identificativo)
    return trovata


def scarta(profilo: Any, identificativo: str, adesso: Optional[datetime] = None) -> bool:
    """«No, grazie»: non torna piu' (finche' non scade e il registro non la mostra di nuovo)."""
    trovata = _sua(profilo, identificativo)
    fatto = proposte.decidi(trovata["id"], "scartata", _utc(adesso))
    if fatto:
        registro.registra("sogno.proposta_scartata", dettagli={"tipo": trovata["tipo"]})
    return fatto


def accetta(profilo: Any, identificativo: str, adesso: Optional[datetime] = None) -> dict[str, Any]:
    """«Si'»: se l'abitudine si sa scrivere come regola, nasce una regola **spenta**; la accende una persona.

    Ritorna `{"regola": id | None}`. Serve il permesso di creare routine: accettare e' creare.
    """
    from shinra.infra.lingue import schemi
    from shinra.services import permessi
    from shinra.services.regole import motore_regole

    trovata = _sua(profilo, identificativo)
    if trovata["stato"] != "nuova":
        return {"regola": None}
    bozza = abitudini.bozza_di_regola(trovata["dati"] or {}) if trovata["tipo"] == TIPO_ABITUDINE else None
    regola_id = None
    if bozza is not None:
        permessi.esigi(profilo, permessi.MODIFICA_MODALITA)
        dati = trovata["dati"]
        nome = schemi(getattr(profilo, "lingua", "") or "").dice(
            "sogno_regola_nome", bersaglio=dati["bersaglio"], orario=dati["orario"]
        )
        regola_id = motore_regole.crea({**bozza, "nome": nome}, autore=_id_profilo(profilo))["id"]
    proposte.decidi(trovata["id"], "accettata", _utc(adesso))
    registro.registra(
        "sogno.proposta_accettata", dettagli={"tipo": trovata["tipo"], "regola_creata": regola_id is not None}
    )
    return {"regola": regola_id}
