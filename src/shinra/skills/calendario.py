"""«Cosa ho oggi»: gli impegni, da dove sono.

Come per le liste, la regola e' **una sola verita'**: dove ci sono entita'
`calendar` in Home Assistant, gli impegni si leggono di li'. Gli eventi di
casa, sul database, sono per chi non ha calendari collegati — e si sommano,
non si sovrappongono: se hai il calendario di Google e in piu' hai segnato
qualcosa qui, «cosa ho oggi» deve dirti tutte e due le cose.

Gli eventi di Home Assistant non stanno negli attributi dell'entita': si
chiedono a `/api/calendars/<entita>?start=...&end=...`. E' il motivo per cui
il client ha una lettura generica.

Riferimento: issue #25.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict

from shinra.domain import calendario as dominio
from shinra.domain import quando as tempo

logger = logging.getLogger("Shinra.Calendario")


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


async def _calendari() -> list[str]:
    from shinra.infra.homeassistant.client import client_home_assistant

    elenco = await client_home_assistant().leggi("calendars")
    if not isinstance(elenco, list):
        return []
    return [str(c.get("entity_id")) for c in elenco if c.get("entity_id")]


async def _eventi_ha(da: datetime, a: datetime) -> list[dominio.Evento]:
    from shinra.infra.homeassistant.client import client_home_assistant

    client = client_home_assistant()
    tutti: list[dominio.Evento] = []

    for entita in await _calendari():
        grezzi = await client.leggi(f"calendars/{entita}", {"start": da.isoformat(), "end": a.isoformat()})
        if isinstance(grezzi, list):
            tutti.extend(dominio.da_home_assistant(grezzi, entita))

    return tutti


def _eventi_di_casa(da: datetime, a: datetime) -> list[dominio.Evento]:
    from shinra.infra.db import depositi

    fuori: list[dominio.Evento] = []
    for riga in depositi.eventi_calendario.fra(da, a):
        inizio = riga.get("inizio")
        if not isinstance(inizio, datetime):
            continue
        fine = riga.get("fine")
        fuori.append(
            dominio.Evento(
                titolo=str(riga.get("titolo") or "Impegno"),
                inizio=inizio,
                fine=fine if isinstance(fine, datetime) else None,
                tutto_il_giorno=bool(riga.get("tutto_il_giorno")),
                luogo=str(riga.get("luogo") or ""),
                calendario="casa",
            )
        )
    return fuori


def _giorno_detto(detto: str) -> tuple[date, str]:
    """Da «oggi», «domani», «sabato» al giorno e a come ridirlo."""
    piatto = tempo.normalizza(detto or "oggi")
    oggi = date.today()

    if not piatto or piatto == "oggi":
        return oggi, "oggi"

    momento = tempo.quando(piatto)
    if momento is None:
        return oggi, "oggi"

    giorni = (momento.date() - oggi).days
    if giorni == 0:
        return oggi, "oggi"
    if giorni == 1:
        return momento.date(), "domani"
    if giorni == 2:
        return momento.date(), "dopodomani"
    return momento.date(), momento.strftime("il %d/%m")


async def impegni(quando_detto: str = "oggi") -> Dict[str, Any]:
    """Gli impegni di un giorno, da tutti i calendari messi insieme."""
    giorno, detto = _giorno_detto(quando_detto)

    # Si chiede una finestra piu' larga del giorno: un evento cominciato
    # ieri e finito domani e' un impegno anche oggi, e chiedendo solo il
    # giorno Home Assistant non lo restituirebbe.
    da = datetime.combine(giorno - timedelta(days=30), datetime.min.time())
    a = datetime.combine(giorno + timedelta(days=1), datetime.min.time())

    tutti = await _eventi_ha(da, a) + _eventi_di_casa(da, a)
    del_giorno = dominio.del_giorno(tutti, giorno)

    return _riuscito(
        dominio.riassumi(del_giorno, detto),
        giorno=giorno.isoformat(),
        impegni=[
            {
                "titolo": e.titolo,
                "inizio": e.inizio.isoformat(),
                "tutto_il_giorno": e.tutto_il_giorno,
                "luogo": e.luogo,
                "calendario": e.calendario,
            }
            for e in del_giorno
        ],
    )


async def prossimi_impegni(giorni: int = 7) -> Dict[str, Any]:
    """Cosa c'e' nei prossimi giorni, giorno per giorno."""
    quanti = max(1, min(30, int(giorni or 7)))
    oggi = date.today()
    da = datetime.combine(oggi - timedelta(days=30), datetime.min.time())
    a = datetime.combine(oggi + timedelta(days=quanti), datetime.min.time())

    tutti = await _eventi_ha(da, a) + _eventi_di_casa(da, a)

    per_giorno: list[str] = []
    totale = 0
    for scarto in range(quanti):
        giorno = oggi + timedelta(days=scarto)
        del_giorno = dominio.del_giorno(tutti, giorno)
        if not del_giorno:
            continue
        totale += len(del_giorno)
        etichetta = "oggi" if scarto == 0 else "domani" if scarto == 1 else giorno.strftime("%d/%m")
        per_giorno.append(f"{etichetta}: " + "; ".join(dominio.descrivi(e) for e in del_giorno))

    if not per_giorno:
        return _riuscito(f"Non hai impegni nei prossimi {quanti} giorni.", impegni=[])

    return _riuscito(". ".join(per_giorno) + ".", totale=totale)


async def aggiungi_impegno(
    titolo: str, quando_detto: str, luogo: str = "", tutto_il_giorno: bool = False
) -> Dict[str, Any]:
    """Segna un impegno sul calendario di casa.

    Non scrive sui calendari di Home Assistant: quelli sono di Google, di
    iCloud, di chi li possiede, e una casa che scrive nell'agenda di lavoro
    di qualcuno fa un danno che non sa di fare. Se serve li', si scrive di
    li'.
    """
    from shinra.domain.contesto import contesto_se_c_e
    from shinra.infra.db import depositi

    nome = (titolo or "").strip()
    if not nome:
        return _fallito("Serve dire che impegno segnare.")

    momento = tempo.quando(quando_detto)
    if momento is None:
        nome_ripulito, momento = tempo.separa(nome)
        if momento is not None and nome_ripulito:
            nome = nome_ripulito

    if momento is None:
        return _fallito(
            f"Non ho capito quando mettere «{nome}». Dimmi un giorno o un orario — "
            "«domani alle 15», «sabato», «il 22» — e lo segno.",
            serve="quando",
        )

    contesto = contesto_se_c_e()
    autore = contesto.attore if contesto and contesto.attore else None

    depositi.eventi_calendario.aggiungi(
        {
            "id": f"evt_{uuid.uuid4().hex[:6]}",
            "titolo": nome.capitalize(),
            "inizio": momento,
            "fine": None,
            "tutto_il_giorno": bool(tutto_il_giorno),
            "luogo": (luogo or "").strip(),
            "autore": autore,
        }
    )

    return _riuscito(f"Segnato: {nome} {tempo.descrivi(momento)}.", quando=momento.isoformat())
