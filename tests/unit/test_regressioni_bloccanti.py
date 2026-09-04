"""I due difetti bloccanti della revisione tecnica, e la guardia che li tiene chiusi.

Entrambi erano chiamate a metodi inesistenti:

- **BLK-01** — `interview_engine` chiamava `data_store.add_knowledge_item()`.
  Fuori da qualsiasi `try`, quindi l'AttributeError arrivava all'utente come
  un HTTP 500 a ogni risposta dell'intervista.
- **BLK-02** — chiamava `self.ollama.generate()`. L'eccezione era catturata,
  quindi si cadeva **sempre** nel ripiego: il prompt di estrazione dei fatti,
  con la proposta automatica di routine, non e' mai stato eseguito.

Erano marcati `xfail(strict=True)`: quando le correzioni sono arrivate, i test
sono diventati rossi obbligando a rimuovere il marcatore. E' successo davvero,
ed e' il motivo per cui questo file ora verifica il comportamento invece
dell'esistenza dei metodi.
"""

from __future__ import annotations

import inspect

from core.data_store import DataStore
from core.interview_engine import LearningInterviewEngine
from core.ollama_client import OllamaClient


def test_data_store_espone_add_knowledge_item() -> None:
    """BLK-01, risolto: il metodo esiste e ha la firma che il chiamante usa."""
    assert hasattr(DataStore, "add_knowledge_item")
    parametri = inspect.signature(DataStore.add_knowledge_item).parameters
    assert "text" in parametri and "category" in parametri


def test_l_intervista_usa_solo_metodi_esistenti() -> None:
    """BLK-02, risolto — e la guardia contro il ripetersi del difetto.

    Invece di verificare l'esistenza di un metodo con un nome preciso, si
    controlla che ogni metodo che l'intervista invoca su `self.ollama` e su
    `data_store` esista davvero. Cosi' il test regge anche se domani quei
    metodi cambiano nome, e continua a intercettare la classe di errore che
    ha prodotto entrambi i bloccanti.
    """
    sorgente = inspect.getsource(LearningInterviewEngine)

    import re

    su_ollama = set(re.findall(r"self\.ollama\.(\w+)\s*\(", sorgente))
    su_datastore = set(re.findall(r"data_store\.(\w+)\s*\(", sorgente))

    assert su_ollama, "nessuna chiamata a self.ollama trovata: aggiornare questo test"

    mancanti = [f"OllamaClient.{m}" for m in su_ollama if not hasattr(OllamaClient, m)]
    mancanti += [f"DataStore.{m}" for m in su_datastore if not hasattr(DataStore, m)]

    assert not mancanti, (
        "LearningInterviewEngine chiama metodi che non esistono: "
        + ", ".join(sorted(mancanti))
        + ". E' esattamente il difetto di BLK-01 e BLK-02."
    )


def test_nessun_modulo_chiama_metodi_inesistenti_sui_propri_client() -> None:
    """Estende il controllo oltre l'intervista.

    Entrambi i bloccanti erano nello stesso file per caso, non per natura:
    la stessa svista puo' ripetersi ovunque si usi un client condiviso.
    """
    import re
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent.parent
    mancanti: list[str] = []

    for percorso in (radice / "core").rglob("*.py"):
        if "__pycache__" in percorso.parts:
            continue
        testo = percorso.read_text(encoding="utf-8")
        for metodo in set(re.findall(r"self\.ollama\.(\w+)\s*\(", testo)):
            if not hasattr(OllamaClient, metodo):
                mancanti.append(f"{percorso.name}: OllamaClient.{metodo}")
        for metodo in set(re.findall(r"data_store\.(\w+)\s*\(", testo)):
            if not hasattr(DataStore, metodo):
                mancanti.append(f"{percorso.name}: DataStore.{metodo}")

    assert not mancanti, "Chiamate a metodi inesistenti:\n  " + "\n  ".join(sorted(mancanti))
