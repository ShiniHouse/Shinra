"""Le regole su un luogo (#346): cosa aggiungere all'evento, perche' scatta, e perche' non scattera'.

Sta fuori dal motore (`services/regole.py`) per non farlo crescere. Home Assistant dice dove e' una persona con il **nome della
zona** in cui si trova; qui quel nome diventa l'identificativo di un luogo registrato. Mai coordinate: l'evento porta solo
identificativi, e il registro dice il nome del luogo.
"""

from __future__ import annotations

from typing import Any, Mapping

from shinra.domain import regole as dominio
from shinra.domain.eventi import HA_STATO_CAMBIATO, Evento


def con_i_luoghi(evento: Evento) -> dict[str, Any]:
    """Per le persone di Home Assistant, in piu' i luoghi registrati di prima e di adesso (solo identificativi)."""
    dati = dict(evento.dati or {})
    entita = str(dati.get("entity_id") or "")
    if evento.tipo == HA_STATO_CAMBIATO and entita.startswith(("person.", "device_tracker.")):
        from shinra.services import posizione

        dati["luogo_precedente"] = posizione.luogo_dallo_stato(str(dati.get("stato_precedente") or ""))
        dati["luogo_nuovo"] = posizione.luogo_dallo_stato(str(dati.get("stato") or ""))
    return dati


def motivo(regola: dominio.Regola, evento: Evento) -> str:
    """Perche' e' scattata, per il registro: per un luogo il suo nome («arrivo Casa al mare»), mai le coordinate."""
    trigger = regola.trigger or {}
    if str(trigger.get("tipo") or "") == dominio.LUOGO:
        from shinra.services import luoghi

        nome = next((x["nome"] for x in luoghi.elenco() if x["id"] == trigger.get("luogo_id")), "un luogo")
        return f"{trigger.get('evento') or dominio.ARRIVO} {nome}"
    return f"evento {evento.tipo}"


def nome_del_luogo(luogo_id: Any) -> str:
    from shinra.services import luoghi

    return next((str(x["nome"]) for x in luoghi.elenco() if x["id"] == luogo_id), "")


def perche_non_scattera(trigger: Mapping[str, Any], attiva: bool) -> str:
    """Se una regola su un luogo non puo' scattare, perche': meglio dirlo che lasciarla ferma in silenzio.

    Servono la persona nota a Home Assistant e, in Home Assistant, una zona che si chiami come il luogo (`home` per il
    principale): Home Assistant dice dove e' una persona con il nome della zona, e Shinra riusa quello.
    """
    if str(trigger.get("tipo") or "") != dominio.LUOGO or not attiva:
        return ""
    from shinra.infra.homeassistant.stati import cache_stati
    from shinra.services import luoghi, posizione

    if cache_stati.stato(str(trigger.get("entity_id") or "")) is None:
        return "Home Assistant non conosce questa persona (o la posizione è spenta): la regola non scatterà."
    luogo = next((x for x in luoghi.elenco() if x["id"] == trigger.get("luogo_id")), None)
    if luogo is None:
        return "Il luogo non esiste più: la regola non scatterà."
    if not posizione.zona_di_home_assistant(str(luogo["nome"]), bool(luogo.get("principale"))):
        return f"In Home Assistant manca una zona che si chiami «{luogo['nome']}»: la regola non scatterà."
    return ""
