# -*- coding: utf-8 -*-
"""Il luogo principale dalla citta' detta nell'intervista (#345).

La domanda «in quale citta' si trova la casa?» non lascia soltanto una frase fra i ricordi: se la casa non ha ancora un luogo
principale, ne nasce uno (`luoghi.registra_dalla_citta`). Sta qui, e non nel motore, per non appesantirlo e perche' non
dipende dal modello: la citta' si legge dalla risposta con le espressioni della lingua, il resto lo fa il codice.
"""

import logging
from typing import Any, Dict

from shinra.infra.lingue import schemi
from shinra.services.intervista_comune import dice

logger = logging.getLogger("Shinra.Intervista")

PASSO_DELLA_CITTA = "casa_citta"


def citta_detta(risposta: str, lingua: str = "") -> str:
    """La citta' in una risposta come «vivo ad Arezzo» («Arezzo» da sola va bene); vuota se non si riconosce."""
    trovata = schemi(lingua or None).citta.search(risposta or "")
    if trovata:
        return " ".join(trovata.group(1).split()).strip(" .,?!")
    breve = " ".join((risposta or "").split()).strip(" .,?!")
    return breve if 0 < len(breve.split()) <= 3 and len(breve) <= 40 else ""


def ricorda_la_citta(session: Dict[str, Any], passo_id: str) -> None:
    """Annota nella sessione la citta' da registrare, dopo che la risposta alla domanda e' stata salvata."""
    if passo_id != PASSO_DELLA_CITTA:
        return
    citta = citta_detta(session["answers"].get(passo_id, ""), session.get("lingua", ""))
    if citta:
        session["luogo_da_registrare"] = citta


async def registra_il_luogo(session: Dict[str, Any], esito: Dict[str, Any]) -> Dict[str, Any]:
    """Registra il luogo annotato, se c'e', e lo dice a chi risponde. Mai un errore: l'intervista prosegue."""
    from shinra.services import luoghi

    citta = session.pop("luogo_da_registrare", "")
    if not citta:
        return esito
    try:
        luogo = await luoghi.registra_dalla_citta(citta)
    except Exception:
        logger.warning("Luogo dall'intervista non registrato", exc_info=True)
        return esito
    if luogo is not None:
        esito["message"] = (esito.get("message") or "") + dice(
            session.get("lingua", ""),
            "luogo_registrato",
            nome=luogo["nome"],
            citta=luogo.get("citta") or citta,
        )
    return esito
