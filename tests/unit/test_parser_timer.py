"""Test del parser di timer e promemoria in linguaggio naturale.

E' logica pura, senza IO ne' rete: e' il pezzo del progetto piu' facile da
coprire e oggi non ha alcun test.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from core.timer_engine import TimerEngine


@pytest.fixture()
def motore() -> TimerEngine:
    return TimerEngine()


# --------------------------------------------------------------------------
# Timer
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("frase", "secondi_attesi"),
    [
        ("metti un timer di 9 minuti per la pasta", 9 * 60),
        ("timer 30 secondi", 30),
        ("imposta un timer di 2 ore", 2 * 3600),
        ("avvia timer di 5 minuti", 5 * 60),
    ],
)
def test_riconosce_i_timer(motore: TimerEngine, frase: str, secondi_attesi: int) -> None:
    risultato = motore.parse_timer_or_reminder(frase)
    assert risultato is not None, f"non riconosciuto: {frase!r}"
    assert risultato["type"] == "timer"
    assert risultato["duration_seconds"] == secondi_attesi


def test_estrae_l_etichetta_del_timer(motore: TimerEngine) -> None:
    risultato = motore.parse_timer_or_reminder("metti un timer di 9 minuti per la pasta")
    assert risultato is not None
    assert "pasta" in risultato["label"].lower()


# --------------------------------------------------------------------------
# Promemoria
# --------------------------------------------------------------------------


def test_riconosce_il_promemoria_a_orario(motore: TimerEngine) -> None:
    risultato = motore.parse_timer_or_reminder("ricordami di prendere le medicine alle 17:30")
    assert risultato is not None
    assert risultato["type"] == "reminder"
    assert "medicine" in risultato["text"].lower()
    momento = datetime.fromisoformat(risultato["remind_at"])
    assert (momento.hour, momento.minute) == (17, 30)


def test_riconosce_il_promemoria_relativo(motore: TimerEngine) -> None:
    risultato = motore.parse_timer_or_reminder("ricordami di comprare il pane tra 20 minuti")
    assert risultato is not None
    assert risultato["type"] == "reminder"
    assert "pane" in risultato["text"].lower()


def test_orario_gia_passato_slitta_al_giorno_dopo(motore: TimerEngine) -> None:
    """Un promemoria per un'ora gia' trascorsa vale per domani, non per il passato."""
    risultato = motore.parse_timer_or_reminder("ricordami di chiamare il medico alle 00:01")
    assert risultato is not None
    assert datetime.fromisoformat(risultato["remind_at"]) > datetime.now()


# --------------------------------------------------------------------------
# Non deve riconoscere
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "frase",
    ["che ore sono", "accendi la luce del salotto", "che tempo fa domani", ""],
)
def test_ignora_le_frasi_non_pertinenti(motore: TimerEngine, frase: str) -> None:
    assert motore.parse_timer_or_reminder(frase) is None


# --------------------------------------------------------------------------
# Lacune note del parser — issue v0.2.0 #17
# --------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Il parser richiede una cifra: 'un minuto' non e' riconosciuto — issue v0.2.0 #17",
)
def test_riconosce_i_numeri_scritti_in_lettere(motore: TimerEngine) -> None:
    risultato = motore.parse_timer_or_reminder("metti un timer di un minuto")
    assert risultato is not None
    assert risultato["duration_seconds"] == 60


@pytest.mark.xfail(
    strict=True,
    reason="L'orario senza minuti non e' riconosciuto: la regex esige [:.]MM — issue v0.2.0 #17",
)
def test_riconosce_l_orario_senza_minuti(motore: TimerEngine) -> None:
    risultato = motore.parse_timer_or_reminder("ricordami di uscire alle 18")
    assert risultato is not None
    assert datetime.fromisoformat(risultato["remind_at"]).hour == 18
