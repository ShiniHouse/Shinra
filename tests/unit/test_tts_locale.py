"""La voce locale (Piper): compare solo se c'e', e se non si puo' usare Shinra non resta muta."""

from __future__ import annotations

import pytest

from shinra.config.settings import settings
from shinra.infra import tts, tts_locale


@pytest.fixture()
def cartella(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.voce, "cartella_voci", str(tmp_path))
    monkeypatch.setattr(tts_locale, "_caricate", {})
    return tmp_path


def _voce_finta(cartella, nome):
    (cartella / f"{nome}.onnx").write_bytes(b"x")
    (cartella / f"{nome}.onnx.json").write_text("{}")


@pytest.mark.parametrize(
    ("rate", "atteso"),
    [
        ("+0%", 1.0),
        ("+25%", 0.8),
        ("-20%", 1.25),
        ("", 1.0),
        ("veloce", 1.0),
        ("+900%", 0.6),
        ("-99%", 1.6),
        ("-100%", 1.6),
    ],
)
def test_la_velocita_diventa_la_lunghezza_dei_fonemi(rate, atteso):
    assert tts_locale.lunghezza_dalla_velocita(rate) == pytest.approx(atteso)


def test_senza_la_libreria_non_compare_nessuna_voce_locale(cartella, monkeypatch):
    _voce_finta(cartella, "it_IT-paola-medium")
    monkeypatch.setattr(tts_locale, "libreria", lambda: None)
    assert tts_locale.voci_disponibili() == []


def test_compaiono_solo_le_voci_con_il_loro_file_di_configurazione(cartella, monkeypatch):
    monkeypatch.setattr(tts_locale, "libreria", lambda: object())
    _voce_finta(cartella, "it_IT-paola-medium")
    (cartella / "orfana.onnx").write_bytes(b"x")  # senza .onnx.json: non e' una voce
    assert [v["id"] for v in tts_locale.voci_disponibili()] == ["piper:it_IT-paola-medium"]


def test_senza_cartella_non_succede_niente(tmp_path, monkeypatch):
    monkeypatch.setattr(settings.voce, "cartella_voci", str(tmp_path / "non-esiste"))
    monkeypatch.setattr(tts_locale, "libreria", lambda: object())
    assert tts_locale.voci_disponibili() == []


async def test_un_percorso_nel_nome_non_esce_dalla_cartella(cartella, monkeypatch):
    """`piper:../segreto` non e' fra le voci trovate: non si apre, e Shinra ripiega."""
    monkeypatch.setattr(tts_locale, "libreria", lambda: object())
    with pytest.raises(FileNotFoundError):
        await tts_locale.genera_wav("ciao", "piper:../segreto")


async def test_se_la_voce_locale_non_va_si_ripiega_su_diego(monkeypatch):
    chiamate = {}

    async def guasta(*_a, **_k):
        raise RuntimeError("piper-tts non e' installato")

    async def rete(testo, voce, rate, pitch):
        chiamate["voce"] = voce
        return b"mp3"

    monkeypatch.setattr(tts_locale, "genera_wav", guasta)
    monkeypatch.setattr(tts, "generate_speech_mp3", rete)
    assert await tts.generate_speech("ciao", "piper:x") == (b"mp3", "audio/mpeg")
    assert chiamate["voce"] == "it-IT-DiegoNeural"


async def test_la_voce_locale_che_va_resta_locale_e_non_chiama_la_rete(monkeypatch):
    async def locale(testo, voce, rate):
        assert (voce, rate) == ("piper:x", "+10%")
        return b"RIFF"

    async def rete(*_a, **_k):
        raise AssertionError("la rete non andava toccata")

    monkeypatch.setattr(tts_locale, "genera_wav", locale)
    monkeypatch.setattr(tts, "generate_speech_mp3", rete)
    assert await tts.generate_speech("ciao", "piper:x", rate="+10%") == (b"RIFF", "audio/wav")


async def test_una_voce_di_rete_non_passa_dalla_locale(monkeypatch):
    async def locale(*_a, **_k):
        raise AssertionError("era una voce di rete")

    async def rete(testo, voce, rate, pitch):
        return b"mp3"

    monkeypatch.setattr(tts_locale, "genera_wav", locale)
    monkeypatch.setattr(tts, "generate_speech_mp3", rete)
    assert await tts.generate_speech("ciao", "it-IT-ElsaNeural") == (b"mp3", "audio/mpeg")


def test_l_elenco_unisce_le_voci_di_rete_e_le_locali(monkeypatch):
    monkeypatch.setattr(tts_locale, "voci_disponibili", lambda: [{"id": "piper:x", "name": "x"}])
    ids = [v["id"] for v in tts.voci_disponibili()]
    assert ids[-1] == "piper:x" and "it-IT-DiegoNeural" in ids
