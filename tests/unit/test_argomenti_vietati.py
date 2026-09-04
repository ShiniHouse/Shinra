"""`restricted_topics` deve avere un effetto.

Il campo esisteva in `UserProfile` da sempre e non era letto da nessuna riga:
il profilo «bambino» cambiava soltanto il tono delle risposte, non cio' a cui
poteva accedere.
"""

from __future__ import annotations

import pytest

from core.argomenti_vietati import argomento_vietato, consenti
from core.user_manager import UserProfile


@pytest.fixture()
def figlio() -> UserProfile:
    return UserProfile(
        id="figlio",
        name="Thomas",
        role="child",
        age_group="child",
        restricted_topics=["armi", "alcol", "politica"],
    )


def test_riconosce_un_argomento_vietato(figlio: UserProfile) -> None:
    assert consenti("parlami delle armi da fuoco", figlio) == "armi"


def test_non_e_sensibile_alle_maiuscole(figlio: UserProfile) -> None:
    assert consenti("Cos'e' l'ALCOL?", figlio) == "alcol"


@pytest.mark.parametrize(
    "richiesta",
    ["accendi la luce della cameretta", "che tempo fa domani", "metti un timer di 5 minuti"],
)
def test_le_richieste_normali_passano(figlio: UserProfile, richiesta: str) -> None:
    assert consenti(richiesta, figlio) is None


def test_le_parole_non_corrispondono_a_pezzi(figlio: UserProfile) -> None:
    """Il caso che rende inutilizzabile un filtro fatto male.

    Con un confronto per sottostringa, "armi" corrisponde ad "armadio" e la
    cameretta diventa un argomento proibito. A quel punto il filtro viene
    disattivato, e non protegge piu' nulla.
    """
    assert consenti("apri l'armadio della cameretta", figlio) is None
    assert consenti("la politica aziendale", figlio) == "politica"


def test_un_profilo_senza_limiti_non_e_filtrato() -> None:
    adulto = UserProfile(id="a", name="Alessio", role="admin")
    assert consenti("parlami delle armi", adulto) is None


def test_nessun_profilo_non_solleva() -> None:
    assert consenti("qualsiasi cosa", None) is None


@pytest.mark.parametrize("argomenti", [None, [], ["", "   "]])
def test_elenchi_vuoti_non_bloccano_nulla(argomenti) -> None:
    assert argomento_vietato("parlami di tutto", argomenti) is None


@pytest.mark.asyncio
async def test_l_agente_si_ferma_prima_di_agire(figlio: UserProfile, monkeypatch) -> None:
    """Il controllo deve precedere il fast-path.

    Se arrivasse dopo, una richiesta vietata potrebbe comunque accendere una
    luce o attivare una modalita' prima di essere rifiutata.
    """
    from core.agent import ShinraAgent
    from core.memory import ConversationMemory

    agente = ShinraAgent()

    async def non_deve_essere_chiamato(*a, **k):
        raise AssertionError("l'agente ha agito su una richiesta vietata")

    monkeypatch.setattr(agente.ollama, "chat", non_deve_essere_chiamato)

    esito = await agente.process_user_input(
        "accendi le armi", user_profile=figlio, session_memory=ConversationMemory()
    )
    assert esito["success"] is True
    assert esito["actions"] == []
    assert "preferisco non parlare" in esito["response"]
