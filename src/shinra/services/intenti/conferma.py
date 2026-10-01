"""«Si'» o «no» a una domanda di conferma (issue #192).

Viene **prima di tutto**, modello compreso: se la persona ha una conferma in sospeso e
risponde con un si' o un no — solo quello, o poco piu' — la risposta e' per la conferma.
Il modello non la vede, quindi non puo' darla da solo.

Se la frase e' altro, l'intento non si riconosce e la conferma resta dov'e': scade da
sola. Una frase come «si', ma prima chiudi la finestra» non e' una conferma, e un «si'»
che apre una porta deve essere inequivocabile.

Riferimento: issue #192.
"""

from __future__ import annotations

import re
from typing import Optional

from shinra.services import conferme
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra

_PUNTEGGIATURA = re.compile(r"[^\w\s']", re.UNICODE)


def _normalizza(testo: str) -> str:
    return " ".join(_PUNTEGGIATURA.sub(" ", testo.lower()).split())


class ConfermaAzione(Intento):
    nome = "conferma"
    priorita = 1

    def applicabile(self, richiesta: Richiesta) -> bool:
        if conferme.in_attesa() is None:
            return False
        frase = _normalizza(richiesta.testo)
        s = richiesta.schemi
        return frase in s.conferma_accetta or frase in s.conferma_rifiuta

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        s = richiesta.schemi
        accettata = _normalizza(richiesta.testo) in s.conferma_accetta
        esito = await conferme.rispondi(accettata)

        if esito["esito"] == "nessuna":
            return Risposta(s.dice("conferma_nessuna"))
        if esito["esito"] == "scaduta":
            return Risposta(s.dice("conferma_scaduta"))
        if esito["esito"] == "rifiutata":
            return Risposta(s.dice("conferma_rifiutata"))

        risultato = esito["risultato"]
        # Gli argomenti non tornano nella risposta: possono contenere il codice dell'allarme.
        richiesta.annota(esito["tool"], {}, risultato)
        if isinstance(risultato, dict) and (risultato.get("error") or risultato.get("success") is False):
            return Risposta(str(risultato.get("message") or risultato.get("error")))
        return Risposta(str((risultato or {}).get("message") or s.dice("conferma_eseguita")))


registra(ConfermaAzione())
