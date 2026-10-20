"""Una voce che gira in casa: Piper, senza rete e senza che il testo delle risposte esca dal server.

Le voci di Microsoft (`edge-tts`) hanno bisogno di internet, mandano fuori ogni frase che Shinra dice, e quando la rete e' lenta
l'audio arriva a pezzi. Piper e' un motore neurale che sta sul server: la voce e' un file `.onnx` con il suo `.onnx.json`, e la
sintesi per una frase di sei secondi richiede una frazione di secondo (misurato su un PC da scrivania; sul server va rimisurato).

Facoltativa come Whisper (`voce` in `pyproject.toml`): se la libreria o i file mancano, la voce locale semplicemente non compare
nell'elenco, e una richiesta per una voce locale ripiega su quella di rete — mai in silenzio con un errore al posto dell'audio.

Come si aggiunge una voce: `docs/VOCE.md`.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import threading
import wave
from pathlib import Path
from typing import Any, Optional

from shinra.config.settings import settings

logger = logging.getLogger("Shinra.TTS.Locale")

PREFISSO = "piper:"
LUNGHEZZA_MIN = 0.6  # piu' veloce di cosi' le parole si mangiano
LUNGHEZZA_MAX = 1.6

_caricate: dict[str, Any] = {}
_blocco = (
    threading.Lock()
)  # una sintesi alla volta: la CPU e' di tutta la casa, e la sessione ONNX non si divide


def libreria() -> Optional[Any]:
    """Il modulo `piper`, o `None` se non e' installato."""
    try:
        import piper
    except ImportError:  # pragma: no cover - dipende dall'ambiente
        return None
    return piper


def cartella() -> Path:
    return Path(settings.voce.cartella_voci)


def _trovate() -> dict[str, Path]:
    """Le voci sul disco: nome del file senza estensione -> percorso del `.onnx`, solo se c'e' anche il suo `.onnx.json`."""
    base = cartella()
    if not base.is_dir():
        return {}
    return {
        p.stem: p
        for p in sorted(base.glob("*.onnx"))
        if p.with_name(p.name + ".json").is_file() and re.fullmatch(r"[\w.\-]+", p.stem)
    }


def voci_disponibili() -> list[dict[str, str]]:
    """Le voci locali che si possono usare adesso, nella stessa forma di `NEURAL_VOICES`. Vuoto se manca la libreria."""
    if libreria() is None:
        return []
    return [
        {
            "id": PREFISSO + nome,
            "name": f"🏠 {nome.replace('_', ' ')} (locale)",
            "gender": "",
            "desc": "Voce che gira sul server di casa: senza internet, il testo non esce.",
        }
        for nome in _trovate()
    ]


def e_locale(voce: str) -> bool:
    return bool(voce) and voce.startswith(PREFISSO)


def lunghezza_dalla_velocita(rate: str) -> float:
    """`+10%` (piu' veloce) diventa una lunghezza dei fonemi minore di 1; `-10%` maggiore. Illeggibile vale 1."""
    trovato = re.fullmatch(r"\s*([+-]?\d{1,3})\s*%\s*", rate or "")
    if not trovato:
        return 1.0
    fattore = 1 + int(trovato.group(1)) / 100
    if fattore <= 0:
        return LUNGHEZZA_MAX
    return min(LUNGHEZZA_MAX, max(LUNGHEZZA_MIN, 1 / fattore))


def _voce(nome: str) -> Any:
    """La voce caricata, la prima volta dal disco (qualche secondo: poi resta in memoria)."""
    if nome not in _caricate:
        percorso = _trovate().get(nome)
        if percorso is None:
            raise FileNotFoundError(f"voce locale '{nome}' non trovata in {cartella()}")
        modulo = libreria()
        if modulo is None:
            raise RuntimeError("piper-tts non e' installato")
        _caricate[nome] = modulo.PiperVoice.load(str(percorso))
    return _caricate[nome]


def _sintetizza(testo: str, nome: str, lunghezza: float) -> bytes:
    with _blocco:
        voce = _voce(nome)
        from piper import SynthesisConfig

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            voce.synthesize_wav(testo, wav, syn_config=SynthesisConfig(length_scale=lunghezza))
        return buf.getvalue()


async def genera_wav(testo: str, voce: str, rate: str = "+0%") -> bytes:
    """L'audio WAV di `testo` con la voce locale `voce` (`piper:nome`). Solleva se non si puo': chi chiama ripiega."""
    nome = voce[len(PREFISSO) :]
    return await asyncio.to_thread(_sintetizza, testo, nome, lunghezza_dalla_velocita(rate))
