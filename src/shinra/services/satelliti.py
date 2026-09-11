"""Il registro dei punti di ascolto, e chi risponde quando sentono in due.

`domain/satelliti.py` decide; qui si tiene l'elenco e si applica.

**Sta in memoria, e non e' una svista.** Un satellite si annuncia quando si
accende: la dashboard lo fa a ogni caricamento della pagina, un dispositivo
vero lo farebbe all'avvio. Salvare l'elenco su disco vorrebbe dire, dopo un
riavvio del server, un elenco di punti di ascolto che non ci sono — e
attribuire una stanza a un satellite spento e' peggio che non conoscerlo:
significa mandare una risposta in una stanza vuota.

Cio' che invece deve sopravvivere e' la **stanza scelta**, e sopravvive dove
e' stata scelta: nel dispositivo, che la ridichiara ogni volta che si
annuncia.

Riferimento: issue #33.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Optional

from shinra.domain import satelliti as dominio

logger = logging.getLogger("Shinra.Satelliti")


class RegistroSatelliti:
    """Chi sta ascoltando, dove, e cosa ha appena sentito.

    Il lucchetto c'e' perche' due satelliti che sentono la stessa frase
    arrivano davvero insieme — e' il caso normale, non quello raro — e senza
    di esso la finestra dell'eco si leggerebbe mentre l'altro la sta
    scrivendo. Il risultato sarebbe che entrambi si credono i primi e
    rispondono in due: esattamente cio' che tutto questo deve impedire.
    """

    def __init__(self) -> None:
        self._satelliti: dict[str, dominio.Satellite] = {}
        self._ascolti: list[dominio.Ascolto] = []
        self._lucchetto = threading.Lock()

    # ---------------------------------------------------------- il registro

    def annuncia(
        self, identificativo: str, nome: str = "", stanza: str = "", adesso: Optional[datetime] = None
    ) -> dominio.Satellite:
        """Un punto di ascolto si presenta, o si ripresenta con una stanza nuova."""
        quando = adesso or datetime.now()
        satellite = dominio.Satellite(
            identificativo=identificativo,
            nome=nome.strip() or identificativo,
            stanza=stanza.strip(),
            visto_il=quando,
        )
        with self._lucchetto:
            prima = self._satelliti.get(identificativo)
            self._satelliti[identificativo] = satellite

        if prima is None or prima.stanza != satellite.stanza:
            logger.info(
                "Satellite «%s» in ascolto da: %s.", satellite.nome, satellite.stanza or "stanza non detta"
            )
        return satellite

    def dimentica(self, identificativo: str) -> bool:
        with self._lucchetto:
            return self._satelliti.pop(identificativo, None) is not None

    def elenco(self, adesso: Optional[datetime] = None) -> list[dominio.Satellite]:
        with self._lucchetto:
            tutti = list(self._satelliti.values())
        return dominio.presenti(tutti, adesso or datetime.now())

    def stanza_di(self, identificativo: str) -> str:
        with self._lucchetto:
            tutti = list(self._satelliti.values())
        return dominio.stanza_di(tutti, identificativo)

    # ------------------------------------------------------------ l'ascolto

    def prende_in_carico(self, identificativo: str, frase: str, adesso: Optional[datetime] = None) -> bool:
        """Tocca a questo satellite rispondere, o l'ha gia' fatto un altro?

        Registra l'ascolto **e** decide, sotto lo stesso lucchetto: fare le
        due cose separatamente aprirebbe la finestra in cui due satelliti si
        credono entrambi i primi.
        """
        quando = adesso or datetime.now()
        ascolto = dominio.Ascolto(satellite=identificativo, frase=frase, quando=quando)

        with self._lucchetto:
            self._ascolti = dominio.solo_recenti(self._ascolti, quando)
            tocca = dominio.deve_rispondere(ascolto, self._ascolti)
            if tocca:
                self._ascolti.append(ascolto)

        if not tocca and frase.strip():
            logger.info("«%s» era gia' stata presa in carico da un altro satellite.", frase[:60])
        return tocca

    def per_l_interfaccia(self, adesso: Optional[datetime] = None) -> list[dict[str, Any]]:
        return [
            {
                "id": s.identificativo,
                "nome": s.nome,
                "stanza": s.stanza,
                "visto_il": s.visto_il.isoformat() if s.visto_il else None,
            }
            for s in self.elenco(adesso)
        ]

    def svuota(self) -> None:
        """Solo per i test: un registro in memoria non si svuota da solo."""
        with self._lucchetto:
            self._satelliti.clear()
            self._ascolti.clear()


registro_satelliti = RegistroSatelliti()
