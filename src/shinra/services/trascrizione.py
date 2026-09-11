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
        in_memoria = stato.in_casa and whisper.caricato(settings.voce.modello)
        return {
            "motore": stato.motore,
            "in_casa": stato.in_casa,
            "pronto": stato.pronto,
            "motivo": stato.motivo,
            "spiegazione": dominio.spiega(stato.motivo),
            "modello": dominio.modello_valido(settings.voce.modello) if stato.in_casa else "",
            "megabyte_massimi": dominio.MEGABYTE_MASSIMI,
            # Il motore c'e' ma il modello puo' non essere ancora in memoria:
            # sono due cose diverse, e la dashboard deve poterle distinguere
            # per non far parlare qualcuno dentro un'attesa di minuti.
            "modello_caricato": in_memoria,
            "in_preparazione": whisper.in_preparazione(),
            # Il messaggio si scrive qui, non nella pagina: «sto preparando» e
            # «ci ho provato e non ci sono riuscito» sono due cose diverse, e
            # una frase scritta a mano nel JavaScript non puo' distinguerle.
            "spiegazione_modello": (
                "" if in_memoria or not stato.in_casa else self.perche_il_modello_non_e_pronto()
            ),
        }

    def perche_il_modello_non_e_pronto(self) -> str:
        """Cosa dire a chi preme il microfono mentre i pesi non ci sono.

        «Sto preparando, riprova fra un minuto — succede una volta sola» e'
        vero finche' il caricamento sta andando. Se e' gia' morto, la stessa
        frase si ripete identica a ogni pressione e tiene qualcuno ad
        aspettare una cosa che non arrivera'.
        """
        guasto = whisper.perche_non_e_pronto()
        if guasto:
            return dominio.spiega_caricamento_fallito(guasto)
        return dominio.spiega(dominio.MODELLO_IN_PREPARAZIONE)

    def prepara(self) -> bool:
        """Comincia a caricare il modello, se ha senso farlo.

        Si chiama all'avvio del servizio: e' l'unico momento in cui nessuno
        sta aspettando una risposta.
        """
        from shinra.config.settings import settings

        if not self.stato().in_casa:
            return False
        return whisper.prepara(settings.voce.modello)

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

        # Il modello non e' in memoria: caricarlo qui vorrebbe dire tenere
        # aperta questa richiesta per tutto il tempo del caricamento — minuti,
        # la prima volta, perche' i pesi si scaricano. Nessun proxy aspetta
        # tanto: Cloudflare taglia a cento secondi e restituisce un 524, che
        # non spiega niente e non dice di riprovare.
        #
        # Meglio rispondere subito e dire cosa sta succedendo, mettendo in
        # moto il caricamento per la volta dopo. E' un rifiuto che scade da
        # solo.
        if not whisper.caricato(settings.voce.modello):
            # Il motivo si legge **prima** di rimettere in moto: far ripartire
            # la preparazione azzera il guasto precedente, ed e' proprio
            # quello che qui bisogna raccontare.
            messaggio = self.perche_il_modello_non_e_pronto()
            whisper.prepara(settings.voce.modello)
            raise NonSiPuo(messaggio)

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
