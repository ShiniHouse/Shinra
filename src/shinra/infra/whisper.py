"""L'involucro attorno a `faster-whisper`.

Tutto cio' che tocca il modello sta qui, e nient'altro. Sopra si parla di
audio e di testo; qui di segmenti, campionamento e VAD.

**E' una dipendenza facoltativa, ma non e' opzionale la scelta che rappresenta.**
Se manca, il microfono della dashboard non funziona e lo dice — non ripiega in
silenzio sulla Web Speech API, che manderebbe la voce di casa a Google. Il
peso e' il motivo per cui non e' obbligatoria: `faster-whisper` porta con se'
CTranslate2 e PyAV, e il modello si scarica al primo uso.

Riferimento: issue #31.
"""

from __future__ import annotations

import io
import logging
import threading
from typing import Any, Optional

from shinra.domain import trascrizione as dominio

logger = logging.getLogger("Shinra.Whisper")

# Il modello si carica una volta e resta in memoria: caricarlo a ogni frase
# costerebbe piu' della trascrizione stessa. Il lucchetto serve perche' due
# richieste vicine non lo carichino due volte — su un server di casa vorrebbe
# dire il doppio della memoria per qualche secondo, che e' abbastanza per
# finirla.
_lucchetto = threading.Lock()
_modello: Optional[Any] = None
_modello_caricato: str = ""

# `int8` invece di `float16`: su una CPU e' l'unica combinazione che dia una
# latenza sopportabile, e la perdita di precisione su frasi brevi in italiano
# non si nota. Su GPU si potrebbe fare meglio, ma un hub domotico che pretende
# una GPU non e' un hub domotico.
CALCOLO = "int8"


def libreria() -> Optional[Any]:
    """Il modulo `faster_whisper`, o `None` se non e' installato."""
    try:
        import faster_whisper
    except ImportError:  # pragma: no cover - dipende dall'ambiente
        return None
    return faster_whisper


def disponibile() -> bool:
    return libreria() is not None


def carica(nome: str) -> Any:
    """Il modello, caricandolo la prima volta.

    Il primo caricamento scarica i pesi e puo' volerci qualche minuto: e' il
    motivo per cui l'errore che ne deriva dev'essere distinguibile da «la
    libreria non c'e'», perche' il rimedio e' aspettare, non installare.
    """
    global _modello, _modello_caricato

    modulo = libreria()
    if modulo is None:
        raise RuntimeError("faster-whisper non e' installato.")

    voluto = dominio.modello_valido(nome)
    if voluto != (nome or "").strip().lower():
        logger.warning("Modello '%s' sconosciuto: uso '%s'.", nome, voluto)

    with _lucchetto:
        if _modello is None or _modello_caricato != voluto:
            logger.info("Carico il modello di trascrizione '%s' (%s)...", voluto, CALCOLO)
            _modello = modulo.WhisperModel(voluto, device="cpu", compute_type=CALCOLO)
            _modello_caricato = voluto
            logger.info("Modello '%s' pronto.", voluto)
    return _modello


def scarica() -> None:
    """Dimentica il modello. Serve ai test e a chi cambia modello a caldo."""
    global _modello, _modello_caricato
    with _lucchetto:
        _modello = None
        _modello_caricato = ""


def trascrivi(audio: bytes, modello: str, lingua: str = dominio.LINGUA_PREDEFINITA) -> str:
    """Da byte di audio a testo grezzo. La pulizia sta nel dominio.

    `vad_filter` toglie i silenzi prima di darli al modello: e' il rimedio
    principale ai titoli di coda che Whisper inventa quando non sente niente.
    Non basta da solo — `domain.trascrizione.e_allucinazione` esiste per
    quello che passa comunque — ma toglie la maggior parte dei casi e fa
    risparmiare tempo su una registrazione fatta di attesa.
    """
    motore = carica(modello)

    segmenti, _ = motore.transcribe(
        io.BytesIO(audio),
        language=(lingua or dominio.LINGUA_PREDEFINITA),
        vad_filter=True,
        # `beam_size=1` e' la ricerca piu' povera e la piu' veloce. Su comandi
        # di casa — frasi brevi, vocabolario ristretto — il guadagno di una
        # ricerca larga non si sente, l'attesa si'.
        beam_size=1,
        condition_on_previous_text=False,
    )

    return "".join(segmento.text for segmento in segmenti)
