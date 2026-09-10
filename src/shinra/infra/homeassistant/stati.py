"""Gli stati della casa tenuti in memoria, invece che chiesti ogni volta.

Finora ogni frase detta all'assistente costava una chiamata di rete: per
sapere che luci ci sono e come stanno, `get_relevant_entities_summary`
interrogava Home Assistant e aspettava. Con la connessione WebSocket gli
stati arrivano da soli quando cambiano, e questa cache e' il posto dove si
fermano.

Non contiene niente di specifico al trasporto: e' un dizionario con delle
regole, e si prova senza rete. Il riassunto per il modello si costruisce qui
— da questi stati o da quelli appena scaricati via REST, indifferentemente —
perche' due implementazioni della stessa frase divergono, e la differenza si
noterebbe solo quando la connessione cade.

Riferimento: issue #19.
"""

from __future__ import annotations

import threading
from typing import Any, Iterable, Optional

# I domini che l'interfaccia mostra come comandabili. Filtrare qui non e'
# pigrizia: `state_changed` scatta per ogni entita' della casa — sensori di
# batteria, contatori, aggiornamenti firmware — e in una casa popolata sono
# molti eventi al minuto che non interessano a nessuno.
DOMINI_CONTROLLABILI = frozenset({"light", "switch", "climate", "cover", "media_player"})

# Cio' che vale la pena raccontare sul bus degli eventi. Non coincide con i
# comandabili: `person` non si comanda e sapere chi c'e' in casa e'
# l'informazione piu' utile che passi di qui (issue #22). Coincidevano
# finche' l'unico consumatore era la dashboard.
#
# `sun` c'e' perche' `sun.sun` cambia stato esattamente all'alba e al
# tramonto, e sono i due momenti in cui il motore delle regole deve rifare i
# conti: `next_rising` e `next_setting` scivolano al giorno dopo. Senza,
# una regola del sole scattava una volta e restava ferma fino al riavvio.
DOMINI_OSSERVATI = DOMINI_CONTROLLABILI | {"person", "alarm_control_panel", "sun"}

# Quanti dispositivi entrano nel riassunto dato al modello. Non e' un limite
# tecnico ma di attenzione: un elenco lunghissimo peggiora le risposte invece
# di migliorarle.
MASSIMO_NEL_RIASSUNTO = 15

# Stati che significano «non lo so», e che non vanno raccontati come fossero
# una condizione della casa.
NON_PERTINENTI = frozenset({"unavailable", "unknown", ""})


def dominio_di(entity_id: str) -> str:
    return entity_id.split(".", 1)[0] if "." in entity_id else ""


def riassumi(
    stati: Iterable[dict[str, Any]],
    domini: frozenset[str] = DOMINI_CONTROLLABILI,
    massimo: int = MASSIMO_NEL_RIASSUNTO,
) -> str:
    """Il riassunto che finisce nel contesto del modello."""
    righe = []
    for stato in stati:
        entity_id = stato.get("entity_id", "")
        if dominio_di(entity_id) not in domini:
            continue
        valore = stato.get("state", "unknown")
        if valore in NON_PERTINENTI:
            continue
        nome = (stato.get("attributes") or {}).get("friendly_name") or entity_id
        righe.append(f"{nome} ({entity_id}): {valore}")
        if len(righe) >= massimo:
            break
    return "; ".join(righe)


class CacheStati:
    """Gli stati conosciuti, protetti da un lucchetto.

    Il lucchetto serve: chi scrive e' l'anello del WebSocket, chi legge sono
    le richieste HTTP, e girano nello stesso processo ma non nello stesso
    momento.
    """

    def __init__(self) -> None:
        self._stati: dict[str, dict[str, Any]] = {}
        self._lucchetto = threading.Lock()

    # ------------------------------------------------------------ scrittura

    def sostituisci(self, stati: Iterable[dict[str, Any]]) -> int:
        """L'istantanea iniziale: si prende tutto e si riparte da li'."""
        nuovi = {s["entity_id"]: s for s in stati if s.get("entity_id")}
        with self._lucchetto:
            self._stati = nuovi
        return len(nuovi)

    def aggiorna(self, stato: Optional[dict[str, Any]]) -> bool:
        """Un'entita' sola. `None` arriva quando l'entita' viene rimossa."""
        if not stato or not stato.get("entity_id"):
            return False
        with self._lucchetto:
            self._stati[stato["entity_id"]] = stato
        return True

    def dimentica(self, entity_id: str) -> bool:
        with self._lucchetto:
            return self._stati.pop(entity_id, None) is not None

    def svuota(self) -> None:
        """Alla caduta della connessione: meglio nessuno stato che uno vecchio.

        Uno stato di dieci minuti fa raccontato come attuale e' peggio di un
        «non lo so»: l'assistente direbbe che la luce e' accesa mentre e'
        spenta, e nessuno saprebbe perche'.
        """
        with self._lucchetto:
            self._stati.clear()

    # ------------------------------------------------------------- lettura

    @property
    def popolata(self) -> bool:
        with self._lucchetto:
            return bool(self._stati)

    def quanti(self) -> int:
        with self._lucchetto:
            return len(self._stati)

    def stato(self, entity_id: str) -> Optional[dict[str, Any]]:
        with self._lucchetto:
            return self._stati.get(entity_id)

    def tutti(self) -> list[dict[str, Any]]:
        with self._lucchetto:
            return list(self._stati.values())

    def riassunto(self) -> str:
        return riassumi(self.tutti())


cache_stati = CacheStati()
