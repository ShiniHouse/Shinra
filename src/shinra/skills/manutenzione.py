"""Le scadenze di casa: filtri, revisione, bollo, garanzie.

`domain/manutenzione.py` sa contare le ricorrenze; qui si scrive e si legge.

La cosa che rende utile questa funzione e' una sola: **una scadenza genera un
promemoria che suona davvero.** Una scadenza che sta in un elenco e aspetta
che qualcuno lo apra e' una scadenza dimenticata — e finche' i promemoria non
suonavano (#92) questo non era possibile prometterlo, quindi non lo si
prometteva.

Riferimento: issue #25.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time
from typing import Any, Dict, Optional

from shinra.domain import manutenzione as dominio
from shinra.domain import quando as tempo

logger = logging.getLogger("Shinra.Manutenzione")

# A che ora suona il promemoria di una scadenza. Le nove: chi deve pagare il
# bollo lo fa di giorno, e una sveglia alle sette non aiuta nessuno.
ORA_AVVISO = time(9, 0)


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


def _dalla_riga(riga: Dict[str, Any]) -> Optional[dominio.Scadenza]:
    prossima = riga.get("prossima")
    if not isinstance(prossima, datetime):
        return None
    return dominio.Scadenza(
        identificativo=str(riga.get("id")),
        titolo=str(riga.get("titolo") or ""),
        prossima=prossima.date(),
        ogni=int(riga.get("ogni") or 0),
        unita=str(riga.get("unita") or dominio.MESI),
        preavviso=int(riga.get("preavviso") or dominio.PREAVVISO_PREDEFINITO),
        documento=str(riga.get("documento") or ""),
    )


def tutte() -> list[dominio.Scadenza]:
    from shinra.infra.db import depositi

    lette = [_dalla_riga(r) for r in depositi.scadenze.elenco()]
    return [s for s in lette if s is not None]


def _unita_detta(parola: str) -> str:
    piatto = tempo.normalizza(parola)
    if piatto.startswith("giorn"):
        return dominio.GIORNI
    if piatto.startswith("ann"):
        return dominio.ANNI
    return dominio.MESI


async def aggiungi_scadenza(
    titolo: str,
    quando_detto: str = "",
    ogni: int = 0,
    unita: str = "mesi",
    preavviso: int = dominio.PREAVVISO_PREDEFINITO,
    documento: str = "",
) -> Dict[str, Any]:
    """Segna una scadenza, e programma l'avviso."""
    from shinra.infra.db import depositi

    nome = (titolo or "").strip()
    if not nome:
        return _fallito("Serve dire che scadenza segnare.")

    momento = tempo.quando(quando_detto) if quando_detto else None
    if momento is None:
        nome_ripulito, momento = tempo.separa(nome)
        if momento is not None and nome_ripulito:
            nome = nome_ripulito

    if momento is None:
        return _fallito(
            f"Non ho capito quando scade «{nome}». Dimmi una data — «il 15 marzo», "
            "«fra sei mesi», «il 30» — e la segno.",
            serve="quando",
        )

    identificativo = f"scad_{uuid.uuid4().hex[:6]}"
    depositi.scadenze.aggiungi(
        {
            "id": identificativo,
            "titolo": nome.capitalize(),
            "prossima": datetime.combine(momento.date(), ORA_AVVISO),
            "ogni": max(0, int(ogni or 0)),
            "unita": _unita_detta(unita),
            "preavviso": max(0, int(preavviso or 0)),
            "documento": (documento or "").strip(),
            "ultima_fatta": None,
            "promemoria_id": None,
        }
    )

    ricorre = ""
    if ogni and int(ogni) > 0:
        ricorre = f", e poi ogni {int(ogni)} {dominio.NOMI_UNITA[_unita_detta(unita)]}"

    return _riuscito(
        f"Segnata la scadenza «{nome}» per {tempo.descrivi(momento)[:-9].strip() or 'quel giorno'}{ricorre}.",
        id=identificativo,
        prossima=momento.date().isoformat(),
    )


async def scadenze_in_arrivo(giorni: int = 0) -> Dict[str, Any]:
    """Cosa scade, e cosa e' gia' scaduto."""
    elenco = tutte()
    if not elenco:
        return _riuscito(
            "Non hai scadenze segnate. Dimmi «segna il cambio filtri fra sei mesi» "
            "e comincio a tenerne conto.",
            scadenze=[],
        )

    oggi = date.today()

    if giorni and int(giorni) > 0:
        dentro = [s for s in elenco if 0 <= s.giorni_mancanti(oggi) <= int(giorni)]
        scadute = [s for s in elenco if s.scaduta(oggi)]
    else:
        scadute, dentro = dominio.da_segnalare(elenco, oggi)

    if not scadute and not dentro:
        prossima = min(elenco, key=lambda s: s.prossima)
        return _riuscito(
            f"Niente in scadenza. La prossima e' {dominio.descrivi(prossima, oggi)}.",
            scadenze=[],
        )

    return _riuscito(
        dominio.riassumi(scadute + dentro, oggi),
        scadute=[s.titolo for s in scadute],
        in_arrivo=[s.titolo for s in dentro],
    )


async def segna_fatta(titolo: str) -> Dict[str, Any]:
    """Fatto. La prossima si conta **da oggi**, non dalla data prevista.

    Contarla dalla data prevista farebbe accumulare ogni ritardo: un cambio
    filtri fatto con due mesi di ritardo terrebbe il calendario indietro per
    sempre.
    """
    from shinra.infra.db import depositi

    cercato = tempo.normalizza(titolo)
    if not cercato:
        return _fallito("Serve dire quale scadenza.")

    for riga in depositi.scadenze.elenco():
        if cercato not in tempo.normalizza(str(riga.get("titolo"))):
            continue

        oggi = date.today()
        prossima = dominio.prossima_dopo(oggi, int(riga.get("ogni") or 0), str(riga.get("unita")))

        if prossima is None:
            depositi.scadenze.cancella(str(riga["id"]))
            return _riuscito(f"«{riga.get('titolo')}» fatta. Non torna, quindi la tolgo.")

        depositi.scadenze.aggiorna(
            str(riga["id"]),
            {
                "prossima": datetime.combine(prossima, ORA_AVVISO),
                "ultima_fatta": datetime.now(),
                "promemoria_id": None,
            },
        )
        return _riuscito(
            f"«{riga.get('titolo')}» fatta. La prossima e' il {prossima.strftime('%d/%m/%Y')}.",
            prossima=prossima.isoformat(),
        )

    return _fallito(f"Non trovo una scadenza che somigli a «{titolo}».")


async def dimentica_scadenza(titolo: str) -> Dict[str, Any]:
    from shinra.infra.db import depositi

    cercato = tempo.normalizza(titolo)
    for riga in depositi.scadenze.elenco():
        if cercato and cercato in tempo.normalizza(str(riga.get("titolo"))):
            depositi.scadenze.cancella(str(riga["id"]))
            return _riuscito(f"Tolta la scadenza «{riga.get('titolo')}».")
    return _fallito(f"Non trovo una scadenza che somigli a «{titolo}».")
