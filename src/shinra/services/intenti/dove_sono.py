"""«Dove sono?»: in quale luogo registrato si trova chi chiede (#343).

Risponde col **nome del luogo** e mai con le coordinate, e solo a chi ha collegato la propria posizione: chi non l'ha
fatto riceve la spiegazione di come si fa, non una posizione inventata.
"""

from __future__ import annotations

from typing import Optional

from shinra.services import posizione
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra


class DoveSono(Intento):
    nome = "dove_sono"
    # Prima di tutto il resto: e' una frase intera e breve, e non somiglia a nient'altro.
    priorita = 5

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p.search(richiesta.testo) for p in richiesta.schemi.inneschi_posizione)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        lingua = richiesta.schemi
        entita = getattr(richiesta.profilo, "entita_posizione", "") or ""
        dove = posizione.dove_sei(entita)

        if dove.stato == posizione.IN_UN_LUOGO:
            return Risposta(lingua.dice("posizione_in_luogo", luogo=dove.luogo))
        chiave = {
            posizione.SPENTA: "posizione_spenta",
            posizione.IGNOTA: "posizione_ignota",
            posizione.IN_GIRO: "posizione_in_giro",
        }[dove.stato]
        return Risposta(lingua.dice(chiave))


registra(DoveSono())
