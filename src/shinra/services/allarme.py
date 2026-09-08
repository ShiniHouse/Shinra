"""Quando l'allarme suona, qualcuno deve accorgersene.

Il tool sa armare e disarmare, ma un allarme che scatta mentre nessuno
guarda la dashboard non ha avvisato nessuno. Qui si ascolta la centrale e si
pubblica sul bus il fatto che conta: e' scattato.

**La notifica vera non c'e' ancora**, ed e' giusto dirlo invece di far
credere il contrario: le notifiche push verso il telefono sono la issue #29,
della v0.4.0. Quello che c'e' oggi arriva alla dashboard aperta attraverso il
WebSocket. L'evento pero' esiste gia' e ha dentro tutto cio' che serve:
quando #29 arrivera' bastera' sottoscriverla.

Riferimento: issue #23.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from shinra.domain.eventi import CASA_INTRUSIONE, HA_STATO_CAMBIATO, Evento, bus

logger = logging.getLogger("Shinra.Allarme")

DOMINIO = "alarm_control_panel"
SCATTATO = "triggered"


class ServizioAllarme:
    def __init__(self) -> None:
        self._annulla_ascolto: Optional[Any] = None

    def avvia(self) -> None:
        self._annulla_ascolto = bus.sottoscrivi(HA_STATO_CAMBIATO, self._su_cambiamento)
        logger.info("Allarme sotto osservazione.")

    def ferma(self) -> None:
        if self._annulla_ascolto is not None:
            self._annulla_ascolto()
            self._annulla_ascolto = None

    def _su_cambiamento(self, evento: Evento) -> None:
        entita = str(evento.dati.get("entity_id", ""))
        if not entita.startswith(f"{DOMINIO}."):
            return

        if str(evento.dati.get("stato") or "").strip().lower() != SCATTATO:
            return

        # Chi c'e' in casa, al momento in cui e' scattato. E' la prima
        # domanda che si fa chi riceve l'avviso, e dopo cinque minuti la
        # risposta non e' piu' recuperabile.
        from shinra.services.presenza import presenza

        logger.warning("ALLARME SCATTATO: %s", entita)
        bus.pubblica_senza_attendere(
            Evento(
                tipo=CASA_INTRUSIONE,
                dati={
                    "entity_id": entita,
                    "nome": evento.dati.get("nome") or entita,
                    "stato_precedente": evento.dati.get("stato_precedente"),
                    "persone_in_casa": presenza.chi_c_e(),
                },
            )
        )


allarme = ServizioAllarme()
