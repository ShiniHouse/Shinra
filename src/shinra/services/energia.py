"""Chi legge i contatori mentre nessuno guarda.

Home Assistant tiene lo stato di adesso, non quello di ieri: se nessuno
annota le letture, «quanto ho consumato la settimana scorsa» non ha risposta
possibile. Questo servizio annota, un'ora alla volta.

Un'ora e non meno, ed e' una scelta: la granularita' utile e' quella delle
fasce, e leggere ogni cinque minuti non renderebbe il conto piu' esatto —
riempirebbe il database di dodici volte le righe per rispondere alle stesse
domande.

Le letture grezze si scrivono sempre; il consumo, che e' la differenza dalla
lettura precedente, si calcola qui perche' interrogare lo storico non debba
rifare le sottrazioni ogni volta. La fascia si scrive insieme al resto:
ARERA puo' cambiare gli orari, e una bolletta di due anni fa deve restare
divisa come lo era allora.

Riferimento: issue #24.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from shinra.config.settings import settings
from shinra.domain import fasce
from shinra.skills import energia as capacita

logger = logging.getLogger("Shinra.Energia")

JOB_CAMPIONE = "energia_campione"
JOB_PULIZIA = "energia_pulizia"


class ServizioEnergia:
    def __init__(self) -> None:
        self.attivo = False

    def avvia(self) -> bool:
        from shinra.infra.scheduler.motore import scheduler

        if not settings.energia.enabled:
            logger.info("Monitoraggio energia disattivato dalla configurazione.")
            return False

        minuti = max(5, int(settings.energia.intervallo_minuti or 60))
        scheduler.programma_periodico(JOB_CAMPIONE, _campiona, ore=minuti / 60.0)
        scheduler.programma_periodico(JOB_PULIZIA, _pulisci, ore=24)
        self.attivo = True
        logger.info("Monitoraggio energia attivo, un campione ogni %d minuti.", minuti)
        return True

    def ferma(self) -> None:
        from shinra.infra.scheduler.motore import scheduler

        scheduler.annulla(JOB_CAMPIONE)
        scheduler.annulla(JOB_PULIZIA)
        self.attivo = False

    async def campiona(self) -> int:
        """Una lettura per ogni contatore. Torna quanti ne ha annotati."""
        from shinra.infra.db import depositi

        stati = await capacita._stati()
        contatori = capacita.sensori_energia(stati)
        if not contatori:
            logger.debug("Nessun sensore di energia esposto da Home Assistant.")
            return 0

        adesso = datetime.now(timezone.utc)
        fascia = fasce.fascia(adesso)
        annotate = 0

        for stato in stati:
            entita = str(stato.get("entity_id", ""))
            if entita not in contatori:
                continue

            valore = capacita._valore(stato)
            if valore is None:
                # `unavailable` o `unknown`: si salta invece di scrivere zero.
                # Uno zero in mezzo a un contatore cumulativo diventa un
                # azzeramento, e il conto della giornata salta.
                continue

            precedente = depositi.letture_energia.ultima(entita)
            consumo = _differenza(precedente, valore)
            depositi.letture_energia.registra(entita, valore, consumo, fascia, adesso)
            annotate += 1

        return annotate


def _differenza(precedente: dict[str, Any] | None, valore: float) -> float:
    """Quanto e' passato dall'ultima lettura.

    La prima lettura di un contatore vale zero: dice a che punto e', non
    quanto e' stato consumato. Contarla come consumo attribuirebbe a
    quest'ora tutto lo storico del dispositivo.
    """
    if precedente is None:
        return 0.0

    prima = float(precedente.get("valore") or 0.0)
    salto = valore - prima

    if salto >= 0:
        return round(salto, 4)
    if valore < prima / 2:
        # Il contatore e' ripartito da zero: quel che segna adesso e' quel
        # che ha consumato da quando e' ripartito.
        return round(max(0.0, valore), 4)
    # Un salto indietro piccolo e' un guasto del sensore, non un consumo
    # negativo: non si sottrae niente.
    return 0.0


async def _campiona() -> None:
    quante = await servizio_energia.campiona()
    if quante:
        logger.debug("Energia: %d contatori annotati.", quante)


async def _pulisci() -> None:
    from shinra.infra.db import depositi

    giorni = int(settings.energia.retention_giorni or 400)
    if giorni <= 0:
        return
    tolte = depositi.letture_energia.pulisci(datetime.now(timezone.utc) - timedelta(days=giorni))
    if tolte:
        logger.info("Energia: tolte %d letture piu' vecchie di %d giorni.", tolte, giorni)


servizio_energia = ServizioEnergia()
