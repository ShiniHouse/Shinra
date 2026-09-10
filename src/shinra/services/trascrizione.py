"""Trascrivere quello che si dice al microfono della dashboard.

`domain/trascrizione.py` decide quale motore vale e cosa buttare via;
`infra/whisper.py` fa girare il modello. Qui c'e' il resto: i limiti su cio'
che si accetta, e la traduzione degli errori in qualcosa che una persona
possa leggere.

Riferimento: issue #31.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from shinra.domain import trascrizione as dominio
from shinra.infra import whisper

logger = logging.getLogger("Shinra.Trascrizione")


class NonSiPuo(Exception):
    """Il motore locale non e' utilizzabile, e il messaggio dice perche'."""


class AudioRifiutato(Exception):
    """Cio' che e' arrivato non e' audio accettabile."""


class ServizioTrascrizione:
    def stato(self) -> dominio.Stato:
        from shinra.config.settings import settings

        return dominio.scegli_motore(settings.voce.motore, whisper.disponibile())

    def per_l_interfaccia(self) -> dict[str, Any]:
        """Cosa serve alla dashboard per decidere se accendere il microfono.

        Un pulsante che registra e poi fallisce e' peggio di un pulsante
        spento: chi lo preme ha gia' parlato, e scopre dopo che non e'
        servito a niente.
        """
        from shinra.config.settings import settings

        stato = self.stato()
        return {
            "motore": stato.motore,
            "in_casa": stato.in_casa,
            "pronto": stato.pronto,
            "motivo": stato.motivo,
            "spiegazione": dominio.spiega(stato.motivo),
            "modello": dominio.modello_valido(settings.voce.modello) if stato.in_casa else "",
            "megabyte_massimi": dominio.MEGABYTE_MASSIMI,
        }

    def trascrivi(self, audio: bytes, tipo: Optional[str]) -> str:
        """Da audio a comando. Stringa vuota se non c'era niente da capire."""
        from shinra.config.settings import settings

        stato = self.stato()
        if stato.motivo != dominio.PRONTO:
            # Copre due casi con la stessa riga: il motore locale non c'e',
            # oppure la configurazione ha scelto il browser e qui non c'e'
            # niente da trascrivere. `spiega` distingue i due messaggi, ed e'
            # l'unica cosa che cambia — un controllo separato per il browser
            # era codice morto, e l'ho scoperto perche' romperlo non faceva
            # fallire nessun test.
            raise NonSiPuo(dominio.spiega(stato.motivo))

        if not audio:
            raise AudioRifiutato("Non e' arrivato nessun audio.")
        if dominio.troppo_grande(len(audio)):
            raise AudioRifiutato(
                f"La registrazione supera {dominio.MEGABYTE_MASSIMI} MB. "
                "Un comando di casa sta in molto meno: registra piu' corto."
            )
        if not dominio.formato_accettabile(tipo):
            raise AudioRifiutato(f"Formato audio non gestito: {tipo or 'non dichiarato'}.")

        try:
            grezzo = whisper.trascrivi(
                audio,
                modello=settings.voce.modello,
                lingua=settings.voce.lingua,
            )
        except RuntimeError as errore:
            logger.error("Trascrizione fallita: %s", errore)
            raise NonSiPuo(dominio.spiega(dominio.MODELLO_NON_CARICATO)) from errore
        except Exception as errore:  # il modello puo' fallire in molti modi
            logger.exception("Trascrizione fallita: %s", errore)
            raise NonSiPuo(dominio.spiega(dominio.MODELLO_NON_CARICATO)) from errore

        pulito = dominio.pulisci(grezzo)
        if not pulito and grezzo.strip():
            # Il modello ha prodotto qualcosa che il dominio ha buttato: quasi
            # sempre i titoli di coda che inventa sul silenzio. Nel log resta,
            # perche' se un giorno butta via un comando vero bisogna poterlo
            # vedere; nella risposta no, perche' non e' cio' che e' stato
            # detto.
            logger.info("Trascrizione scartata come rumore: %r", grezzo.strip()[:120])
        return pulito


servizio_trascrizione = ServizioTrascrizione()
