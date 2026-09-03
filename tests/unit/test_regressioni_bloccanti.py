"""Test di regressione dei difetti bloccanti individuati nella revisione tecnica.

Ogni test qui e' marcato `xfail(strict=True)`: **deve** fallire finche' il
difetto e' aperto. Quando la correzione arriva, il test passa e — essendo
strict — pytest lo segnala come errore, obbligando a rimuovere il marcatore.

E' il meccanismo con cui il progetto garantisce che nessun difetto venga
dichiarato risolto senza una prova.
"""

from __future__ import annotations

import inspect

import pytest

from core.data_store import DataStore
from core.interview_engine import LearningInterviewEngine
from core.ollama_client import OllamaClient


@pytest.mark.xfail(
    strict=True,
    reason="BLK-01: DataStore.add_knowledge_item non esiste — issue v0.1.0 #01",
)
def test_data_store_espone_add_knowledge_item() -> None:
    """`interview_engine.py:110` chiama questo metodo.

    Non essendo definito, ogni risposta dell'utente durante la Modalita'
    Apprendimento solleva AttributeError e produce un HTTP 500.
    """
    assert hasattr(DataStore, "add_knowledge_item"), (
        "core/interview_engine.py:110 chiama data_store.add_knowledge_item(), "
        "che non esiste in DataStore"
    )


@pytest.mark.xfail(
    strict=True,
    reason="BLK-02: OllamaClient.generate non esiste — issue v0.1.0 #02",
)
def test_ollama_client_espone_generate() -> None:
    """`interview_engine.py:181` chiama questo metodo.

    L'eccezione e' catturata, quindi il codice cade sempre nel fallback: il
    prompt di estrazione dei fatti non e' mai stato eseguito.
    """
    assert hasattr(OllamaClient, "generate"), (
        "core/interview_engine.py:181 chiama self.ollama.generate(), "
        "che non esiste in OllamaClient"
    )


def test_i_metodi_chiamati_dall_intervista_sono_documentati() -> None:
    """Verifica che le due chiamate difettose siano ancora dove ci aspettiamo.

    Questo test resta verde: serve a far fallire il test suite in modo
    esplicito se il codice viene spostato senza aggiornare i riferimenti,
    invece di lasciare che gli xfail sopra diventino silenziosamente inutili.
    """
    sorgente = inspect.getsource(LearningInterviewEngine)
    assert "add_knowledge_item" in sorgente, (
        "Il riferimento a add_knowledge_item non e' piu' in LearningInterviewEngine: "
        "aggiornare i test di regressione BLK-01"
    )
    assert "self.ollama.generate" in sorgente or "ollama.chat" in sorgente, (
        "La chiamata al modello in LearningInterviewEngine e' cambiata: "
        "aggiornare i test di regressione BLK-02"
    )
