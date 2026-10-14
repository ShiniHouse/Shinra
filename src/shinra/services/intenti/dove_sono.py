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
        if dove.stato == posizione.SPENTA:
            return Risposta(lingua.dice("posizione_spenta"))
        if dove.stato == posizione.IN_GIRO:
            if dove.vicino and dove.distanza_m is not None:
                return Risposta(
                    lingua.dice(
                        "posizione_in_giro_vicino",
                        luogo=dove.vicino,
                        distanza=_distanza_leggibile(dove.distanza_m, lingua.lingua),
                    )
                )
            return Risposta(lingua.dice("posizione_in_giro"))

        # Ignota: si dice perche', cosi' chi chiede sa cosa guardare.
        chiave = {
            posizione.NON_E_IN_HOME_ASSISTANT: "posizione_ignota_non_in_ha",
            posizione.SENZA_COORDINATE: "posizione_ignota_senza_coordinate",
            posizione.TROPPO_VECCHIA: "posizione_ignota_vecchia",
            posizione.COORDINATE_ILLEGGIBILI: "posizione_ignota_illeggibile",
        }.get(dove.motivo or "", "posizione_ignota")
        return Risposta(lingua.dice(chiave, entita=entita, ore=(dove.eta_minuti or 0) // 60))


def _distanza_leggibile(metri: int, lingua: str) -> str:
    """«450 m» o «3,1 km» (con la virgola in italiano)."""
    if metri < 1000:
        return f"{metri} m"
    km = f"{metri / 1000:.1f}"
    return (km.replace(".", ",") if lingua == "it" else km) + " km"


registra(DoveSono())
