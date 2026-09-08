"""La memoria della conversazione, una per persona.

Fino alla v0.2.0 esisteva un'unica `ConversationMemory` globale: la chat del
salotto, quella del telefono e ogni richiesta ad Alexa scrivevano nella
stessa cronologia. Il contesto di un adulto finiva nella sessione di un
bambino, e due persone che parlavano insieme si confondevano a vicenda. Il
parametro `session_memory` esisteva gia' in `process_user_input`, ma nessuno
lo passava mai: il difetto era una riga mancante, non un progetto sbagliato.

**Perche' per persona e non per (persona, canale).** La scheda della issue
proponeva di indicizzare per coppia utente-canale, ma fra i criteri di
accettazione c'e' anche «una conversazione iniziata sull'Echo prosegue sul
telefono per lo stesso utente»: le due cose non stanno insieme. Vince il
criterio, perche' descrive cio' che succede in casa — si chiede una cosa
all'Echo in cucina e si continua dal telefono in salotto. Cio' che va tenuto
separato sono le persone, non i dispositivi.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Shinra.Memoria")

# Dopo quanto una conversazione ferma smette di valere. Mezz'ora: piu' corta
# e «spegnila» smetterebbe di funzionare mentre si e' ancora in cucina; piu'
# lunga e la risposta del mattino verrebbe interpretata alla luce di una
# conversazione della sera prima.
SCADENZA_SECONDI = 30 * 60

# Quante conversazioni tenere in memoria. Una casa ha una manciata di
# persone, ma gli ospiti non registrati creano un profilo ciascuno: senza un
# tetto, un processo che gira per mesi cresce senza motivo.
MASSIME_SESSIONI = 50


class ConversationMemory:
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.ultimo_uso: float = time.time()

    def add_user_message(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        self._tocca()

    def add_assistant_message(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})
        self._tocca()

    def add_tool_interaction(self, tool_name: str, tool_args: Dict[str, Any], tool_result: Any) -> None:
        """Registra un'azione eseguita, perche' l'assistente sappia cosa ha fatto.

        Prima il corpo di questo metodo era `pass`. Conseguenza in casa:
        «accendi la luce della cucina» seguito da «spegnila» non poteva
        funzionare, perche' nella cronologia non restava traccia di quale
        luce fosse stata accesa. L'azione va scritta con i suoi parametri —
        e' li' che vive `light.cucina`.
        """
        riuscita = True
        if isinstance(tool_result, dict):
            riuscita = bool(tool_result.get("success", True)) and not tool_result.get("error")

        parametri = ", ".join(f"{c}={v}" for c, v in (tool_args or {}).items() if v not in (None, ""))
        esito = "eseguita" if riuscita else "non riuscita"
        self.history.append(
            {
                "role": "assistant",
                "content": f"[azione {esito}: {tool_name}({parametri})]",
            }
        )
        self._tocca()

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self.history)

    def clear(self) -> None:
        self.history.clear()
        self._tocca()

    @property
    def scaduta(self) -> bool:
        return (time.time() - self.ultimo_uso) > SCADENZA_SECONDI

    def _tocca(self) -> None:
        self.ultimo_uso = time.time()
        self._trim()

    def _trim(self) -> None:
        if len(self.history) > self.max_history * 2:
            self.history = self.history[-self.max_history * 2 :]


class GestoreMemorie:
    """Tiene una conversazione per persona e libera quelle ferme.

    Protetto da un lock: FastAPI serve le richieste in piu' thread, e la
    dashboard e l'Echo possono parlare nello stesso momento.
    """

    def __init__(self, massime: int = MASSIME_SESSIONI):
        self.massime = massime
        self._memorie: Dict[str, ConversationMemory] = {}
        self._lock = threading.Lock()

    def per_utente(self, user_id: Optional[str]) -> ConversationMemory:
        chiave = (user_id or "ospite").strip().lower() or "ospite"
        with self._lock:
            self._scarta_scadute()
            memoria = self._memorie.get(chiave)
            if memoria is None:
                self._fai_spazio()
                memoria = ConversationMemory(max_history=10)
                self._memorie[chiave] = memoria
                logger.debug("Nuova conversazione per %s", chiave)
            memoria.ultimo_uso = time.time()
            return memoria

    def dimentica(self, user_id: str) -> bool:
        with self._lock:
            return self._memorie.pop((user_id or "").strip().lower(), None) is not None

    def azzera(self) -> None:
        with self._lock:
            self._memorie.clear()

    def attive(self) -> Dict[str, int]:
        """Quante conversazioni ci sono e quanti messaggi contengono."""
        with self._lock:
            return {chiave: len(m.history) for chiave, m in self._memorie.items()}

    def pulisci(self) -> int:
        with self._lock:
            return self._scarta_scadute()

    # ------------------------------------------------------------- interno

    def _scarta_scadute(self) -> int:
        scadute = [c for c, m in self._memorie.items() if m.scaduta]
        for chiave in scadute:
            del self._memorie[chiave]
        if scadute:
            logger.debug("Conversazioni scadute liberate: %s", ", ".join(scadute))
        return len(scadute)

    def _fai_spazio(self) -> None:
        """Se si e' al tetto, esce la conversazione ferma da piu' tempo."""
        while len(self._memorie) >= self.massime:
            piu_vecchia = min(self._memorie.items(), key=lambda voce: voce[1].ultimo_uso)[0]
            del self._memorie[piu_vecchia]
            logger.info("Tetto di %d conversazioni raggiunto: liberata %s", self.massime, piu_vecchia)


gestore_memorie = GestoreMemorie()
