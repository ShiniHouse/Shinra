import io
import re
import logging
from typing import Dict, Any, List, Optional
import edge_tts

logger = logging.getLogger(__name__)

# Voci neurali italiane ad alta fedelta
NEURAL_VOICES = [
    {
        "id": "it-IT-DiegoNeural",
        "name": "👨 Diego (Maschile / Stile Jarvis HD)",
        "gender": "male",
        "desc": "Voce maschile calda, naturale e profonda — ideale per assistenti stile Jarvis"
    },
    {
        "id": "it-IT-ElsaNeural",
        "name": "👩 Elsa (Femminile / Stile Shinra HD)",
        "gender": "female",
        "desc": "Voce femminile brillante, espressiva ed empatica"
    },
    {
        "id": "it-IT-IsabellaNeural",
        "name": "👩 Isabella (Femminile Conversazionale)",
        "gender": "female",
        "desc": "Voce femminile calma, colloquiale e rilassante"
    },
    {
        "id": "it-IT-GiuseppeNeural",
        "name": "👨 Giuseppe (Maschile Formale)",
        "gender": "male",
        "desc": "Voce maschile chiara, precisa e istituzionale"
    }
]

def clean_text_for_tts(text: str) -> str:
    """Pulisce il testo da markdown, URL ed emoji prima di inviarlo al motore TTS."""
    if not text:
        return ""
    clean = text
    clean = re.sub(r"```[\s\S]*?```", "", clean)
    clean = re.sub(r"`.*?`", "", clean)
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"[*_~#>[\]]", "", clean)
    clean = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u26FF\u2700-\u27BF]", "", clean)
    clean = re.sub(r"\bHA\b", "Home Assistant", clean)
    clean = re.sub(r"\b°C\b", " gradi ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

async def generate_speech_mp3(
    text: str,
    voice: str = "it-IT-DiegoNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> bytes:
    """
    Genera uno stream audio MP3 ad alta fedelta a partire dal testo fornito.
    """
    cleaned = clean_text_for_tts(text)
    if not cleaned:
        cleaned = "Pronto."

    valid_ids = [v["id"] for v in NEURAL_VOICES]
    if voice not in valid_ids:
        voice = "it-IT-DiegoNeural"

    communicate = edge_tts.Communicate(
        text=cleaned,
        voice=voice,
        rate=rate,
        pitch=pitch
    )

    audio_bytes = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_bytes.extend(chunk["data"])

    return bytes(audio_bytes)
