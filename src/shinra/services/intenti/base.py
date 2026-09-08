"""Un intento: riconoscere cosa vuole chi parla, e farlo.

`process_user_input` era lunga duecentocinquanta righe e conteneva, una dopo
l'altra: intervista, timer, promemoria, modalita', controllo dei
dispositivi, meteo, notizie, Wikipedia, costruzione del prompt e ciclo dei
tool. Non era verificabile a pezzi, e ogni intento nuovo la allungava.

Qui ogni intento e' un oggetto con tre cose: quanto e' prioritario, se si
riconosce nella frase, e cosa fa. L'agente non li conosce: scorre il
registro. Aggiungerne uno vuol dire scrivere una classe e registrarla.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:  # pragma: no cover
    from shinra.services.memory import ConversationMemory
    from shinra.services.user_manager import UserProfile

logger = logging.getLogger("Shinra.Intenti")


@dataclass
class Richiesta:
    """Cio' che un intento riceve."""

    testo: str
    profilo: Optional["UserProfile"] = None
    memoria: Optional["ConversationMemory"] = None
    azioni: list[dict[str, Any]] = field(default_factory=list)
    # Frammenti da mettere nel prompt quando nessuno risponde da solo: e' il
    # caso di Wikipedia, che non risponde all'utente ma informa il modello.
    contesto: list[str] = field(default_factory=list)

    @property
    def minuscolo(self) -> str:
        return self.testo.lower()

    @property
    def id_utente(self) -> str:
        return self.profilo.id if self.profilo else "alessio"

    def annota(self, tool: str, argomenti: dict[str, Any], risultato: Any) -> None:
        self.azioni.append({"tool": tool, "args": argomenti, "result": risultato})


@dataclass
class Risposta:
    """Cio' che un intento restituisce quando ha risolto la richiesta."""

    testo: str
    extra: dict[str, Any] = field(default_factory=dict)


class Intento(ABC):
    """La forma comune. `priorita` piu' bassa significa «guarda prima me»."""

    nome: str = "senza-nome"
    priorita: int = 100

    @abstractmethod
    def applicabile(self, richiesta: Richiesta) -> bool:
        """Se questa frase riguarda questo intento. Deve essere veloce e non fare rete."""

    @abstractmethod
    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        """Esegue.

        Restituire `None` significa «alla fine non era per me»: la ricerca
        continua con gli intenti successivi. Serve a chi si accorge solo
        strada facendo di non poter rispondere — il meteo quando il servizio
        non risponde — e a chi arricchisce il contesto senza rispondere.
        """


_INTENTI: list[Intento] = []


def registra(intento: Intento) -> Intento:
    """Aggiunge un intento al registro, tenendolo ordinato per priorita'."""
    _INTENTI.append(intento)
    _INTENTI.sort(key=lambda i: i.priorita)
    return intento


def intenti() -> list[Intento]:
    return list(_INTENTI)


def azzera() -> None:
    """Solo per i test."""
    _INTENTI.clear()


async def instrada(richiesta: Richiesta) -> Optional[Risposta]:
    """Il primo intento che si riconosce e risponde vince.

    Un intento che solleva non blocca gli altri: al massimo la richiesta
    finisce al modello, che e' il comportamento di prima della v0.1.0 e non
    lascia comunque la persona senza risposta.
    """
    for intento in _INTENTI:
        try:
            if not intento.applicabile(richiesta):
                continue
            risposta = await intento.esegui(richiesta)
            if risposta is not None:
                logger.info("Intento '%s' ha risposto.", intento.nome)
                return risposta
        except Exception as e:
            logger.error("Intento '%s' non riuscito: %s", intento.nome, e, exc_info=True)
    return None
