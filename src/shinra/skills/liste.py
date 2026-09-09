"""Liste della spesa e delle cose da fare.

Il bivio che governa tutto il file: **se in Home Assistant c'e' una lista
`todo` che corrisponde, si scrive li' e si legge di li'.** Le liste di casa,
sul database, esistono solo per chi non ha `todo` configurato.

Non e' pigrizia: una copia sincronizzata sarebbe due verita' che divergono al
primo conflitto — la spesa aggiunta dal telefono mentre la casa e' offline,
la voce spuntata da tutti e due — e una lista della spesa sbagliata e' peggio
di nessuna lista, perche' ci si va al supermercato e si torna senza il latte.

Riferimento: issue #25.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from shinra.domain import liste as dominio

logger = logging.getLogger("Shinra.Liste")


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


async def _stati() -> list[dict[str, Any]]:
    from shinra.infra.homeassistant.client import client_home_assistant

    try:
        return list(await client_home_assistant().stati_correnti())
    except Exception as e:  # la casa deve funzionare anche senza Home Assistant
        logger.warning("Home Assistant non raggiungibile: %s", e)
        return []


async def _entita_todo() -> list[dict[str, Any]]:
    return [s for s in await _stati() if str(s.get("entity_id", "")).startswith(f"{dominio.DOMINIO_HA}.")]


# ------------------------------------------------------- Home Assistant


async def _voci_ha(entita: str) -> list[dominio.Voce]:
    from shinra.infra.homeassistant.client import client_home_assistant

    esito = await client_home_assistant().chiama_con_risposta(
        dominio.DOMINIO_HA, "get_items", {"entity_id": entita}
    )
    if not esito.get("success"):
        return []
    per_entita = (esito.get("risposta") or {}).get(entita) or {}
    return dominio.voci_da_ha(per_entita.get("items") or [])


async def _servizio_ha(servizio: str, dati: Dict[str, Any]) -> bool:
    from shinra.infra.homeassistant.client import client_home_assistant

    esito = await client_home_assistant().call_service(dominio.DOMINIO_HA, servizio, dati)
    return bool(esito.get("success"))


# ------------------------------------------------------- liste di casa


def _lista_di_casa(nome: str) -> dict[str, Any]:
    from shinra.infra.db import depositi

    esistente = depositi.liste.per_nome(nome)
    if esistente:
        return esistente
    return depositi.liste.aggiungi({"id": f"lst_{uuid.uuid4().hex[:6]}", "nome": nome})


def _voci_di_casa(lista_id: str) -> list[dominio.Voce]:
    from shinra.infra.db import depositi

    return [
        dominio.Voce(str(r.get("testo") or ""), bool(r.get("fatta")))
        for r in depositi.voci_lista.della_lista(lista_id)
    ]


# ------------------------------------------------------------------ tool


async def aggiungi_a_lista(voce: str, lista: str = "") -> Dict[str, Any]:
    """Aggiunge una o piu' voci a una lista.

    «Latte, pane e uova» sono tre voci: chi detta la spesa non si ferma dopo
    il primo articolo, e una riga sola costringe a rileggerla al
    supermercato.
    """
    from shinra.domain.contesto import contesto_se_c_e
    from shinra.infra.db import depositi

    da_aggiungere = dominio.separa_voci(voce)
    if not da_aggiungere:
        return _fallito("Serve dire cosa aggiungere.")

    nome = dominio.nome_canonico(lista)
    entita = dominio.scegli_entita(lista, await _entita_todo())

    if entita:
        presenti = await _voci_ha(entita)
        aggiunte, gia_c_erano = [], []
        for testo in da_aggiungere:
            if dominio.gia_presente(testo, presenti):
                gia_c_erano.append(testo)
                continue
            if await _servizio_ha("add_item", {"entity_id": entita, "item": testo}):
                aggiunte.append(testo)
                presenti.append(dominio.Voce(testo))
        return _esito_aggiunta(aggiunte, gia_c_erano, nome, dove=entita)

    contesto = contesto_se_c_e()
    autore = contesto.attore if contesto and contesto.attore else None

    riga_lista = _lista_di_casa(nome)
    presenti = _voci_di_casa(riga_lista["id"])
    aggiunte, gia_c_erano = [], []
    for testo in da_aggiungere:
        if dominio.gia_presente(testo, presenti):
            gia_c_erano.append(testo)
            continue
        depositi.voci_lista.aggiungi(
            {
                "id": f"vc_{uuid.uuid4().hex[:6]}",
                "lista_id": riga_lista["id"],
                "testo": testo,
                "fatta": False,
                "autore": autore,
            }
        )
        aggiunte.append(testo)
        presenti.append(dominio.Voce(testo))

    return _esito_aggiunta(aggiunte, gia_c_erano, nome, dove="casa")


def _esito_aggiunta(aggiunte: list[str], gia_c_erano: list[str], nome: str, dove: str) -> Dict[str, Any]:
    if not aggiunte and gia_c_erano:
        detto = ", ".join(gia_c_erano)
        return _riuscito(f"{detto} c'era gia' nella lista {nome}.", aggiunte=[], gia_presenti=gia_c_erano)
    if not aggiunte:
        return _fallito(f"Non sono riuscito ad aggiungere niente alla lista {nome}.")

    detto = ", ".join(aggiunte)
    coda = f" ({', '.join(gia_c_erano)} c'era gia')" if gia_c_erano else ""
    return _riuscito(
        f"Aggiunto alla lista {nome}: {detto}.{coda}",
        aggiunte=aggiunte,
        gia_presenti=gia_c_erano,
        dove=dove,
    )


async def leggi_lista(lista: str = "") -> Dict[str, Any]:
    """Dice cosa c'e' in una lista."""
    from shinra.infra.db import depositi

    nome = dominio.nome_canonico(lista)
    entita = dominio.scegli_entita(lista, await _entita_todo())

    if entita:
        voci = await _voci_ha(entita)
        return _riuscito(
            dominio.riassumi(nome, voci), voci=[v.testo for v in voci if not v.fatta], dove=entita
        )

    riga_lista = depositi.liste.per_nome(nome)
    if not riga_lista:
        return _riuscito(f"La lista {nome} e' vuota.", voci=[], dove="casa")

    voci = _voci_di_casa(riga_lista["id"])
    return _riuscito(dominio.riassumi(nome, voci), voci=[v.testo for v in voci if not v.fatta], dove="casa")


async def togli_da_lista(voce: str, lista: str = "") -> Dict[str, Any]:
    """Spunta una voce: comprata, o fatta."""
    from shinra.infra.db import depositi

    testo = (voce or "").strip()
    if not testo:
        return _fallito("Serve dire cosa togliere.")

    nome = dominio.nome_canonico(lista)
    entita = dominio.scegli_entita(lista, await _entita_todo())

    if entita:
        presenti = await _voci_ha(entita)
        trovata = dominio.gia_presente(testo, presenti)
        if not trovata:
            return _fallito(f"Non trovo «{testo}» nella lista {nome}.")
        if await _servizio_ha("remove_item", {"entity_id": entita, "item": trovata.testo}):
            return _riuscito(f"Tolto {trovata.testo} dalla lista {nome}.")
        return _fallito(f"Non sono riuscito a togliere {trovata.testo}.")

    riga_lista = depositi.liste.per_nome(nome)
    if not riga_lista:
        return _fallito(f"Non ho una lista {nome}.")

    for riga in depositi.voci_lista.della_lista(riga_lista["id"]):
        if dominio.normalizza(str(riga.get("testo"))) == dominio.normalizza(testo):
            depositi.voci_lista.cancella(str(riga["id"]))
            return _riuscito(f"Tolto {riga.get('testo')} dalla lista {nome}.")

    return _fallito(f"Non trovo «{testo}» nella lista {nome}.")


async def quali_liste() -> Dict[str, Any]:
    """Le liste che esistono, ovunque stiano."""
    from shinra.infra.db import depositi

    da_ha = [
        str((s.get("attributes") or {}).get("friendly_name") or s.get("entity_id"))
        for s in await _entita_todo()
    ]
    di_casa = [str(r.get("nome")) for r in depositi.liste.elenco()]

    tutte = da_ha + [n for n in di_casa if n not in da_ha]
    if not tutte:
        return _riuscito(
            "Non hai ancora nessuna lista. Dimmi «aggiungi il latte alla spesa» e la creo.",
            liste=[],
        )
    return _riuscito(f"Le liste: {', '.join(tutte)}.", liste=tutte, da_home_assistant=da_ha)
