"""Chi trasforma una scadenza in un promemoria che suona.

E' il criterio di accettazione della scheda: «una scadenza di manutenzione
genera un promemoria che scatta davvero». Senza questo servizio le scadenze
sarebbero un elenco che aspetta di essere aperto — cioe' un elenco
dimenticato, che e' esattamente il problema che una scadenza dovrebbe
risolvere.

Fino alla issue #92 non si poteva prometterlo: i promemoria impostati a voce
non suonavano. Adesso si puo', e questo servizio poggia su quella riparazione.

Una volta al giorno si guarda cosa sta per scadere e si crea il promemoria,
uno solo per scadenza: `promemoria_id` sulla riga serve a non ricrearlo a
ogni giro, che vorrebbe dire sette sveglie per un bollo con una settimana di
preavviso.

Riferimento: issue #25.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from shinra.domain import manutenzione as dominio
from shinra.skills import manutenzione as capacita

logger = logging.getLogger("Shinra.Manutenzione")

JOB_CONTROLLO = "manutenzione_controllo"

# Il controllo gira di mattina presto: cosi' il promemoria di una scadenza
# che cade oggi suona nella stessa giornata, e non il giorno dopo.
ORA_CONTROLLO = time(7, 30)


class ServizioManutenzione:
    def __init__(self) -> None:
        self.attivo = False

    def avvia(self) -> bool:
        from shinra.infra.scheduler.motore import scheduler

        if not scheduler.programma_periodico(JOB_CONTROLLO, _controlla, ore=24):
            return False
        self.attivo = True
        logger.info("Controllo scadenze attivo, una volta al giorno.")
        return True

    def ferma(self) -> None:
        from shinra.infra.scheduler.motore import scheduler

        scheduler.annulla(JOB_CONTROLLO)
        self.attivo = False

    def controlla(self, oggi: date | None = None) -> int:
        """Crea i promemoria per le scadenze in arrivo. Torna quanti ne ha fatti."""
        from shinra.infra.db import depositi
        from shinra.skills import reminders

        giorno = oggi or date.today()
        creati = 0

        for riga in depositi.scadenze.elenco():
            scadenza = capacita._dalla_riga(riga)
            if scadenza is None:
                continue

            if not (scadenza.scaduta(giorno) or scadenza.in_arrivo(giorno)):
                continue

            # Uno solo per scadenza: senza questo, un bollo con sette giorni
            # di preavviso produrrebbe sette sveglie.
            if riga.get("promemoria_id"):
                continue

            voce = reminders.crea(
                _come_si_dice(scadenza, giorno),
                _quando_avvisare(scadenza, giorno).strftime("%Y-%m-%dT%H:%M:%S"),
                "alessio",
            )
            depositi.scadenze.aggiorna(str(riga["id"]), {"promemoria_id": voce["id"]})
            creati += 1
            logger.info("Scadenza «%s»: promemoria %s.", scadenza.titolo, voce["id"])

        return creati


def _quando_avvisare(scadenza: dominio.Scadenza, oggi: date) -> datetime:
    """Quando far suonare l'avviso.

    Una scadenza gia' passata si annuncia **subito**, non alla sua data, che
    e' alle spalle: un promemoria programmato nel passato non suona mai, ed e'
    il modo piu' silenzioso di perdere un bollo scaduto.
    """
    if scadenza.scaduta(oggi):
        return datetime.now() + timedelta(minutes=1)
    return datetime.combine(scadenza.prossima, capacita.ORA_AVVISO)


def _come_si_dice(scadenza: dominio.Scadenza, oggi: date) -> str:
    if scadenza.scaduta(oggi):
        return f"{scadenza.titolo} (era scaduta il {scadenza.prossima.strftime('%d/%m')})"
    testo = scadenza.titolo
    if scadenza.documento:
        testo += f" — {scadenza.documento}"
    return testo


async def _controlla() -> None:
    quante = servizio_manutenzione.controlla()
    if quante:
        logger.info("Manutenzione: %d promemoria creati.", quante)


servizio_manutenzione = ServizioManutenzione()
