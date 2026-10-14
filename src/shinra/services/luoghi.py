"""I luoghi registrati (#342): la casa principale, altre abitazioni, il lavoro.

Le coordinate sono un dato delicato e qui valgono tre regole che i test difendono:

- **non finiscono mai nel registro delle azioni ne' nei log**: si scrive che un luogo e' stato registrato o cancellato,
  con il suo identificativo e il suo tipo, mai il nome (che puo' dire dove abita qualcuno) ne' le coordinate;
- **non escono in un salvataggio** (vedi `salvataggio.FUORI`): un archivio si copia, si manda, si perde;
- **si registrano con un gesto di chi e' sul posto**: dalla posizione che Home Assistant conosce di una persona, o dalla
  geolocalizzazione del browser. Non si scrive una citta' a mano.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from shinra.domain import luoghi as dominio
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import registro

logger = logging.getLogger("Shinra.Luoghi")


class LuogoNonTrovato(LookupError):
    pass


def elenco() -> list[dict[str, Any]]:
    return deposito.elenco()


def principale() -> Optional[dict[str, Any]]:
    return deposito.principale()


def registra(dati: Mapping[str, Any]) -> dict[str, Any]:
    """Registra un luogo dalle coordinate che un telefono o un browser hanno letto."""
    r = dominio.valida(dati)
    luogo = deposito.crea(
        {
            "nome": r.nome,
            "tipo": r.tipo,
            "latitudine": r.latitudine,
            "longitudine": r.longitudine,
            "raggio_m": r.raggio_m,
            "citta": r.citta,
            "origine": r.origine,
            "precisione_m": r.precisione_m,
        },
        principale=bool(dati.get("principale")),
    )
    registro.registra(
        "luogo.registrato", dettagli={"id": luogo["id"], "tipo": luogo["tipo"], "origine": r.origine}
    )
    return luogo


async def registra_da_persona(entita: str, dati: Mapping[str, Any]) -> dict[str, Any]:
    """Come `dalla_posizione_di_una_persona`, leggendo gli stati da Home Assistant."""
    from shinra.infra.homeassistant.client import client_home_assistant

    return dalla_posizione_di_una_persona(await client_home_assistant().stati_correnti(), entita, dati)


def dalla_posizione_di_una_persona(
    stati: list[dict[str, Any]], entita: str, dati: Mapping[str, Any]
) -> dict[str, Any]:
    """Registra un luogo dalla posizione che Home Assistant conosce di una `person` o di un `device_tracker`."""
    if not entita.startswith(("person.", "device_tracker.")):
        raise dominio.LuogoNonValido("entita: serve una persona o un telefono di Home Assistant")
    stato = next((s for s in stati if s.get("entity_id") == entita), None)
    if stato is None:
        raise dominio.LuogoNonValido("entita: Home Assistant non la conosce")
    attributi = stato.get("attributes") or {}
    if attributi.get("latitude") is None or attributi.get("longitude") is None:
        raise dominio.LuogoNonValido(
            "entita: Home Assistant non conosce la sua posizione (app aperta? posizione accesa?)"
        )
    return registra(
        {
            **dati,
            "latitudine": attributi["latitude"],
            "longitudine": attributi["longitude"],
            "precisione_m": attributi.get("gps_accuracy"),
            "origine": "telefono",
        }
    )


def aggiorna(identificativo: str, dati: Mapping[str, Any]) -> dict[str, Any]:
    """Cambia nome, tipo, raggio o citta' di un luogo. Le coordinate non si ritoccano: si registra di nuovo."""
    attuale = deposito.per_id(identificativo)
    if attuale is None:
        raise LuogoNonTrovato(identificativo)
    r = dominio.valida(
        {**attuale, **{k: v for k, v in dati.items() if k in ("nome", "tipo", "raggio_m", "citta")}}
    )
    aggiornato = deposito.aggiorna(
        identificativo, {"nome": r.nome, "tipo": r.tipo, "raggio_m": r.raggio_m, "citta": r.citta}
    )
    if dati.get("principale"):
        aggiornato = deposito.imposta_principale(identificativo)
    if aggiornato is None:
        raise LuogoNonTrovato(identificativo)
    registro.registra("luogo.modificato", dettagli={"id": identificativo})
    return aggiornato


def cancella(identificativo: str) -> bool:
    """Cancella un luogo, e con lui le sue coordinate."""
    fatto = deposito.cancella_e_riassegna(identificativo)
    if fatto:
        registro.registra("luogo.cancellato", dettagli={"id": identificativo})
    return fatto
