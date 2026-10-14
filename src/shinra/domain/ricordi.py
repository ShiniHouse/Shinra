"""Chi vede un ricordo, e quando entra nel prompt (ADR 0009).

Un ricordo ha un **proprietario**: vuoto vuol dire che e' *della casa* e lo vede chiunque possa leggere la conoscenza;
altrimenti e' l'identificativo di un profilo, e **lo vede solo lui**. Scelta del proprietario di casa (2026-10-14):
ognuno vede solo i propri ricordi privati, quindi nemmeno un amministratore legge quelli di un altro, e un adulto non legge
quelli di un minore. Non c'e' un'eccezione «per emergenza».

Questo modulo e' puro: dice di chi e' un ricordo e se serve. Chi lo usa (il recupero, le rotte, l'intervista, i plugin) lo
chiama **sempre** prima di mostrare o di mettere nel prompt il testo di un ricordo: e' un punto solo, cosi' la regola non
si dimentica in un posto.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

CASA = ""

STATO_ATTIVO = "attivo"
STATO_PROPOSTO = "proposto"
STATO_ARCHIVIATO = "archiviato"


def proprietario_di(ricordo: Mapping[str, Any]) -> str:
    return str(ricordo.get("proprietario") or CASA)


def e_della_casa(ricordo: Mapping[str, Any]) -> bool:
    return proprietario_di(ricordo) == CASA


def e_visibile_a(ricordo: Mapping[str, Any], profilo_id: Optional[str]) -> bool:
    """Un ricordo della casa lo vedono tutti; uno privato solo il suo proprietario. Senza profilo, solo quelli della casa."""
    proprietario = proprietario_di(ricordo)
    return proprietario == CASA or (bool(profilo_id) and proprietario == profilo_id)


def entra_nel_prompt(ricordo: Mapping[str, Any]) -> bool:
    """Solo un ricordo attivo e non disattivato a mano. Un ricordo solo *proposto* (da una persona o dal sogno) aspetta di
    essere accettato: finche' non lo e', non cambia le risposte di nessuno."""
    return bool(ricordo.get("enabled", True)) and str(ricordo.get("stato") or STATO_ATTIVO) == STATO_ATTIVO


def puo_modificare(ricordo: Mapping[str, Any], profilo_id: Optional[str], puo_scrivere_la_casa: bool) -> bool:
    """Chi puo' cambiare o cancellare un ricordo: uno privato solo il suo proprietario; uno della casa chi puo' scriverla."""
    if not e_visibile_a(ricordo, profilo_id):
        return False
    return puo_scrivere_la_casa if e_della_casa(ricordo) else True
