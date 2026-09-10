"""La casa che finge di essere abitata.

`domain/simulazione.py` decide *cosa* accendere e *quando*, senza toccare
niente. Qui c'e' il resto della capacita': da dove si prendono le luci, come
si trova il tramonto, chi esegue il piano, e il tool con cui la si accende a
voce.

Sta fra le capacita' e non fra i servizi perche' e' una cosa che la casa sa
fare — come accendere una luce o dire che tempo fa. L'unica parte che
reagisce da sola, smettere appena qualcuno rientra, e' in
`services/simulazione.py`, che sta sopra e chiama qui.

**La simulazione si rifiuta di partire con qualcuno in casa.** Una casa che
finge mentre ci vive qualcuno accende e spegne le luci addosso alle persone,
ed e' il modo piu' rapido perche' la funzione venga disattivata per sempre.

Riferimento: issue #23.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional, Sequence

from shinra.domain import presenza as presenza_dominio
from shinra.domain import simulazione as dominio
from shinra.domain import sole as sole_dominio

logger = logging.getLogger("Shinra.Simulazione")

PREFISSO_JOB = "simulazione_"
JOB_RIPIANIFICA = "simulazione_ripianifica"

# Nel pomeriggio: il piano di stasera si fa prima che faccia buio, e prima
# del tramonto piu' presto dell'anno in Italia.
ORA_DI_RIPIANIFICARE = 15

# Se Home Assistant non espone `sun.sun`, si usa un tramonto plausibile per
# l'Italia: meglio un'ora ragionevole che nessuna simulazione. L'ora sta in
# `domain/sole.py`, insieme alla lettura vera.


class ControlloSimulazione:
    """Lo stato della finzione: se e' accesa e cosa succedera' stasera."""

    def __init__(self) -> None:
        self.attiva = False
        self._piano: list[dominio.Accensione] = []
        self._ieri: list[dominio.Accensione] = []

    # ----------------------------------------------------------- lettura

    def dettaglio(self) -> dict[str, Any]:
        return {
            "attiva": self.attiva,
            "accensioni": [
                {
                    "entity_id": a.entity_id,
                    "accendi_alle": a.accendi_alle.isoformat(),
                    "spegni_alle": a.spegni_alle.isoformat(),
                }
                for a in self._piano
            ],
        }

    # ------------------------------------------------- accendere, spegnere

    async def accendi(self, luci: Optional[list[str]] = None) -> dict[str, Any]:
        """Comincia a fingere. Rifiuta se in casa c'e' qualcuno."""
        stati = await self._stati()

        if self._casa_abitata(stati):
            return {
                "success": False,
                "message": (
                    "In casa c'e' qualcuno: la simulazione accenderebbe e spegnerebbe "
                    "le luci addosso alle persone. Riprova quando la casa e' vuota."
                ),
            }

        disponibili = list(luci) if luci else self._luci_disponibili(stati)
        if not disponibili:
            return {
                "success": False,
                "message": "Non trovo luci da usare per la simulazione.",
            }

        self.attiva = True
        quante = self._programma(disponibili, self._tramonto(stati))
        return {
            "success": True,
            "message": f"Simulazione di presenza attiva: {quante} accensioni previste stasera.",
            "accensioni": quante,
        }

    async def spegni(self, motivo: str = "richiesta") -> dict[str, Any]:
        from shinra.infra.scheduler.motore import scheduler

        for accensione in self._piano:
            scheduler.annulla(f"{PREFISSO_JOB}on_{accensione.entity_id}")
            scheduler.annulla(f"{PREFISSO_JOB}off_{accensione.entity_id}")
        scheduler.annulla(JOB_RIPIANIFICA)
        self._piano = []
        self.attiva = False
        logger.info("Simulazione di presenza spenta (%s).", motivo)
        return {"success": True, "message": "Simulazione di presenza disattivata."}

    async def pianifica_la_serata(self, luci: Optional[list[str]] = None) -> int:
        """Il piano di stasera, per chi ripianifica ogni giorno."""
        if not self.attiva:
            return 0
        stati = await self._stati()
        disponibili = list(luci) if luci else self._luci_disponibili(stati)
        if not disponibili:
            return 0
        return self._programma(disponibili, self._tramonto(stati))

    # ----------------------------------------------- lettura della casa
    #
    # Una sola lettura degli stati per tutte e tre le domande — chi c'e',
    # quali luci ci sono, quando tramonta — invece di tre giri identici a
    # Home Assistant. Le funzioni che seguono sono pure: ricevono gli stati.

    async def _stati(self) -> list[dict[str, Any]]:
        from shinra.infra.homeassistant.client import client_home_assistant

        return list(await client_home_assistant().stati_correnti())

    @staticmethod
    def _casa_abitata(stati: Sequence[dict[str, Any]]) -> bool:
        """Adesso, non secondo il servizio di presenza.

        Il servizio smorza i rimbalzi perche' deve annunciare i rientri, e
        annunciarne uno falso e' peggio che annunciarlo tardi. Qui la domanda
        e' un'altra — «posso far finta?» — e la risposta giusta e' quella di
        questo istante: uno smorzamento vorrebbe dire far partire la
        simulazione in una casa dove qualcuno e' appena entrato.
        """
        stato = presenza_dominio.leggi(presenza_dominio.persone_dagli_stati(list(stati)))
        return stato.conosciuta and stato.abitata

    @staticmethod
    def _luci_disponibili(stati: Sequence[dict[str, Any]]) -> list[str]:
        return [
            str(s["entity_id"])
            for s in stati
            if str(s.get("entity_id", "")).startswith("light.")
            and str(s.get("state", "")).lower() not in ("unavailable", "unknown")
        ]

    @staticmethod
    def _tramonto(stati: Sequence[dict[str, Any]]) -> datetime:
        """A che ora tramonta, e se non si sa un'ora plausibile.

        La lettura di `sun.sun` sta in `domain/sole.py` e non piu' qui: la
        facevano in due — questo modulo e il motore delle regole — e due
        letture dello stesso attributo divergono. Il ripiego invece resta una
        scelta di **questa** funzione: qui sbagliare di mezz'ora accende una
        luce un po' presto, mentre per una regola vorrebbe dire una casa che
        fa le cose al momento sbagliato senza che niente lo spieghi.
        """
        tramonto = sole_dominio.dagli_stati(stati).tramonto
        return tramonto or sole_dominio.tramonto_plausibile(datetime.now().astimezone())

    # ---------------------------------------------------------- lo scheduler

    def _programma(self, luci: list[str], tramonto: datetime) -> int:
        from shinra.infra.scheduler.motore import scheduler

        self._ieri = self._piano
        self._piano = dominio.pianifica(luci, tramonto, ieri=self._ieri)

        programmate = 0
        for accensione in self._piano:
            acceso = scheduler.programma_azione(
                f"{PREFISSO_JOB}on_{accensione.entity_id}",
                _accendi,
                [accensione.entity_id],
                accensione.accendi_alle,
            )
            spento = scheduler.programma_azione(
                f"{PREFISSO_JOB}off_{accensione.entity_id}",
                _spegni,
                [accensione.entity_id],
                accensione.spegni_alle,
            )
            programmate += 1 if (acceso and spento) else 0

        # L'appuntamento per il piano di domani. Senza, la simulazione
        # durerebbe una sera sola, e una casa illuminata la prima notte e
        # buia le successive dice «qui non c'e' nessuno» piu' chiaramente di
        # una casa sempre spenta.
        scheduler.programma_azione(
            JOB_RIPIANIFICA,
            _ripianifica,
            [],
            prossimo_giorno(datetime.now().astimezone()),
        )

        logger.info("Simulazione: %d accensioni programmate fino a domani.", programmate)
        return programmate


def prossimo_giorno(adesso: datetime) -> datetime:
    """Quando rifare il piano: domani pomeriggio."""
    return (adesso + timedelta(days=1)).replace(hour=ORA_DI_RIPIANIFICARE, minute=0, second=0, microsecond=0)


async def _ripianifica() -> None:
    await simulazione.pianifica_la_serata()


async def _accendi(entity_id: str) -> None:
    from shinra.infra.homeassistant.client import client_home_assistant

    await client_home_assistant().call_service("light", "turn_on", {"entity_id": entity_id})


async def _spegni(entity_id: str) -> None:
    from shinra.infra.homeassistant.client import client_home_assistant

    await client_home_assistant().call_service("light", "turn_off", {"entity_id": entity_id})


simulazione = ControlloSimulazione()


# ------------------------------------------------------ il tool per il modello


async def comanda_simulazione(azione: str) -> dict[str, Any]:
    """Accende o spegne la finta presenza per quando si e' via."""
    azione = (azione or "").strip().lower()

    if azione in ("stato", "verifica"):
        d = simulazione.dettaglio()
        messaggio = (
            f"Simulazione attiva: {len(d['accensioni'])} accensioni previste stasera."
            if d["attiva"]
            else "La simulazione di presenza e' spenta."
        )
        return {"success": True, "message": messaggio, **d}

    if azione in ("accendi", "attiva", "parti"):
        esito = await simulazione.accendi()
        if not esito.get("success"):
            esito["error"] = esito["message"]
        return esito

    if azione in ("spegni", "disattiva", "ferma"):
        return await simulazione.spegni()

    messaggio = f"Azione «{azione}» non prevista per la simulazione di presenza."
    return {"success": False, "error": messaggio, "message": messaggio}
