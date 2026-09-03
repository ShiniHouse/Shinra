"""Test della pulizia del testo prima della sintesi vocale.

Logica pura. Cio' che passa di qui viene letto ad alta voce in casa: un URL o
una parentesi quadra non pronunciabili sono difetti percepibili.
"""

from __future__ import annotations

import pytest

from core.tts_engine import clean_text_for_tts


@pytest.mark.parametrize(
    ("grezzo", "non_deve_contenere"),
    [
        ("Ecco il **risultato** richiesto", "*"),
        ("Vedi https://example.com per i dettagli", "http"),
        ("Il valore e' `42` gradi", "`"),
        ("Casa pronta 🏠 tutto acceso ✅", "🏠"),
        ("Elenco [primo] elemento", "["),
    ],
)
def test_rimuove_gli_elementi_non_pronunciabili(grezzo: str, non_deve_contenere: str) -> None:
    assert non_deve_contenere not in clean_text_for_tts(grezzo)


def test_espande_le_abbreviazioni() -> None:
    assert "Home Assistant" in clean_text_for_tts("HA e' connesso")


def test_converte_i_gradi() -> None:
    risultato = clean_text_for_tts("Fuori ci sono 20°C")
    assert "°C" not in risultato
    assert "gradi" in risultato


def test_normalizza_gli_spazi() -> None:
    assert "  " not in clean_text_for_tts("testo    con     spazi")


def test_testo_vuoto_non_solleva_eccezioni() -> None:
    assert clean_text_for_tts("") == ""
    assert clean_text_for_tts(None) == ""  # type: ignore[arg-type]
