"""I promemoria che il modello imposta, e che devono suonare davvero.

Prima di questo file c'era una lista Python:

    _REMINDERS_DB: List[Dict[str, Any]] = []

`add_reminder` ci scriveva dentro e rispondeva «Promemoria salvato». Non
toccava il database, non programmava niente nello scheduler, e al riavvio del
servizio spariva tutto. Non suonava mai.

Il difetto non aveva nemmeno un errore da leggere — la risposta era che era
andato bene — e conviveva con una strada che invece funziona:
`services/intenti/promemoria.py` intercetta la frase prima del modello e usa
`timer_engine`, che persiste e programma. Ma quella cattura solo due formule,
«alle HH» e «tra N minuti»: tutto il resto cadeva qui, cioe' nel vuoto. Era
il criterio d'uscita della v0.2.0, mai verificato in casa.

Adesso il promemoria si scrive e si programma qui, e da qui passa anche
`timer_engine`, che prima ne aveva una copia sua. **Creare un promemoria e'
una capacita'** — come accendere una luce: servono solo l'archivio e lo
scheduler, che stanno sotto. Ripristinare i job dopo un riavvio, invece, e'
orchestrazione, e resta in `services/timer_engine.py`. E' la stessa divisione
della simulazione di presenza (#23), e il test sull'architettura l'ha chiesta
anche qui.

Quando non capisce quando deve suonare, **chiede** invece di dire «salvato»:
chi non sa a che ora mettere la sveglia non la mette a caso.

Riferimento: issue #92.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

from shinra.domain import quando as tempo

logger = logging.getLogger("Shinra.Promemoria")


def _riuscito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": True, "message": messaggio, **extra}


def _fallito(messaggio: str, **extra: Any) -> Dict[str, Any]:
    return {"success": False, "error": messaggio, "message": messaggio, **extra}


def crea(testo: str, quando_iso: str, utente: str = "alessio") -> Dict[str, Any]:
    """Scrive il promemoria e programma la sveglia. Le due cose insieme.

    Separarle e' il difetto della issue #92 in una forma piu' subdola: una
    riga nel database che nessun job fara' mai suonare e' altrettanto muta di
    un oggetto in memoria, e in piu' si vede nell'elenco.
    """
    from shinra.infra.db import depositi
    from shinra.infra.scheduler.motore import scheduler

    identificativo = f"rem_{uuid.uuid4().hex[:6]}"
    voce = depositi.promemoria.aggiungi(
        {
            "id": identificativo,
            "text": testo,
            "remind_at": quando_iso,
            "user_id": utente,
            "completed": False,
            "created_at": datetime.now().isoformat(),
        }
    )
    scheduler.programma_promemoria(identificativo, voce["text"], quando_iso, utente)
    return voce


def in_attesa() -> List[Dict[str, Any]]:
    from shinra.infra.db import depositi

    return [v for v in depositi.promemoria.elenco() if not v.get("completed")]


def cancella(identificativo: str) -> bool:
    from shinra.infra.db import depositi
    from shinra.infra.scheduler.motore import scheduler

    scheduler.annulla_promemoria(identificativo)
    return depositi.promemoria.cancella(identificativo)


async def add_reminder(text: str, time_info: str = "") -> Dict[str, Any]:
    """Imposta un promemoria che suona all'ora indicata.

    Args:
        text: Cosa ricordare (es. 'comprare il latte', 'chiamare il medico').
        time_info: Quando (es. 'domani mattina', 'alle 18', 'tra 20 minuti',
            'sabato'). Se manca o non e' comprensibile, il promemoria **non**
            viene creato e viene chiesto quando.
    """
    from shinra.domain.contesto import contesto_se_c_e

    testo = (text or "").strip()
    if not testo:
        return _fallito("Serve dire cosa ricordare.")

    # Il «quando» puo' arrivare nel parametro suo, o essere rimasto dentro al
    # testo: il modello scompone la frase come gli pare, e una persona che ha
    # detto «ricordami di chiamare il dentista domani» ha detto tutto.
    momento = tempo.quando(time_info) if time_info else None
    if momento is None:
        testo_ripulito, momento = tempo.separa(testo)
        if momento is not None and testo_ripulito:
            testo = testo_ripulito

    if momento is None:
        return _fallito(
            f"Non ho capito quando ricordarti di {testo.lower()}. Dimmi un orario "
            "o un giorno — «alle 18», «domani mattina», «sabato», «fra due ore» — "
            "e lo imposto.",
            serve="quando",
            testo=testo,
        )

    contesto = contesto_se_c_e()
    attore = contesto.attore if contesto and contesto.attore else "alessio"

    voce = crea(testo.capitalize(), momento.strftime("%Y-%m-%dT%H:%M:%S"), attore)

    logger.info("Promemoria %s per %s: %s", voce.get("id"), attore, momento.isoformat())

    return _riuscito(
        f"Ti ricordero' di {testo.lower()} {tempo.descrivi(momento)}.",
        promemoria=voce,
        quando=momento.isoformat(),
    )


async def list_reminders(solo_attivi: bool = True) -> Dict[str, Any]:
    """Elenca i promemoria impostati.

    Legge il database, che e' dove sono davvero: prima leggeva una lista in
    memoria che si svuotava a ogni riavvio, e rispondeva «nessun promemoria» a
    chi ne aveva sette.
    """
    from shinra.infra.db import depositi

    voci = in_attesa() if solo_attivi else depositi.promemoria.elenco()

    if not voci:
        return _riuscito("Non hai promemoria in attesa.", totale_attivi=0, promemoria=[])

    elenco = ", ".join(f"{v.get('text')} {_quando_di(v)}" for v in voci[:5])
    coda = f" e altri {len(voci) - 5}" if len(voci) > 5 else ""

    return _riuscito(
        f"Hai {len(voci)} promemoria: {elenco}{coda}.",
        totale_attivi=len(voci),
        promemoria=voci,
    )


def _quando_di(voce: Dict[str, Any]) -> str:
    grezzo = str(voce.get("remind_at") or "")
    try:
        return tempo.descrivi(datetime.fromisoformat(grezzo))
    except ValueError:
        return grezzo


async def delete_reminder(reminder_id: str) -> Dict[str, Any]:
    """Cancella un promemoria e il job che lo avrebbe fatto suonare."""
    if cancella(reminder_id):
        return _riuscito("Promemoria cancellato.")
    return _fallito(f"Non trovo il promemoria «{reminder_id}».")


def _promemoria_in_attesa() -> int:
    """Quanti ne sono in attesa. Usato dai test per verificare che il tool
    scriva davvero da qualche parte."""
    return len(in_attesa())


# Il nome storico, per chi lo importava. La lista in memoria non c'e' piu':
# era il difetto, non un'interfaccia.
__all__ = ["add_reminder", "cancella", "crea", "delete_reminder", "in_attesa", "list_reminders"]
