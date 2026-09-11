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
import time
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

# Il filo che sta caricando il modello, quando c'e'. Separato dal lucchetto
# di sopra: `carica` tiene quel lucchetto per tutto il caricamento, e
# chiedere «sta caricando?» non deve mettersi in coda dietro la risposta.
_lucchetto_preparazione = threading.Lock()
_preparazione: Optional[threading.Thread] = None

# Perche' l'ultimo tentativo di caricamento e' fallito, se e' fallito. Un
# caricamento che muore in sottofondo lascia il servizio in uno stato che da
# fuori assomiglia a «sto ancora lavorando» — e chi preme il microfono si
# sente dire «riprova fra un minuto, succede una volta sola» per sempre.
# Questa stringa e' la differenza fra un'attesa e una bugia.
_ultimo_errore: str = ""

# Quando e' cominciata l'ultima preparazione. «Quanto manca» non si puo'
# sapere; «da quanto si aspetta» si', ed e' cio' che distingue un'attesa
# normale da una che non finira' — un caricamento fermo da dodici minuti
# assomiglia a uno appena partito, se nessuno guarda l'orologio.
_iniziata: float = 0.0

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


def _apri(modulo: Any, voluto: str) -> Any:
    """Prima dal disco, e solo se manca qualcosa si va in rete.

    `WhisperModel`, per difetto, contatta comunque huggingface.co anche con
    il modello gia' in cache: controlla se ce n'e' una versione nuova. Se
    quella chiamata non torna — rete filtrata, DNS che non risponde, il
    servizio dall'altra parte che tace — il caricamento resta appeso a tempo
    indeterminato, con i pesi gia' sul disco a mezzo metro di distanza.

    E' successo in casa: 142 MB di modello scaricati, nessun processo al
    lavoro, nessun errore, e il microfono fermo per venticinque minuti.

    Un hub domotico che ha i pesi non deve dipendere da internet per usarli.
    La rete resta la seconda strada, per la prima volta o per un modello
    cambiato in configurazione — non la prima.
    """
    try:
        return modulo.WhisperModel(voluto, device="cpu", compute_type=CALCOLO, local_files_only=True)
    except Exception as manca:
        logger.info("Modello '%s' non ancora in cache (%s): lo scarico.", voluto, manca)
        return modulo.WhisperModel(voluto, device="cpu", compute_type=CALCOLO)


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
            cominciato = time.monotonic()
            _modello = _apri(modulo, voluto)
            _modello_caricato = voluto
            # La durata non e' un vezzo: con i pesi gia' sul disco sono
            # secondi, senza sono minuti. Averla scritta accanto a «pronto»
            # e' cio' che permette, la volta dopo, di capire in un colpo
            # d'occhio se il caricamento era lento o fermo.
            logger.info("Modello '%s' pronto in %.1fs.", voluto, time.monotonic() - cominciato)
    return _modello


def caricato(nome: str) -> bool:
    """Se il modello chiesto e' gia' in memoria, e quindi trascrivere e' svelto."""
    return _modello is not None and _modello_caricato == dominio.modello_valido(nome)


def in_preparazione() -> bool:
    """Se un filo in sottofondo lo sta caricando proprio adesso."""
    return _preparazione is not None and _preparazione.is_alive()


def da_quanto_prepara() -> float:
    """Secondi dall'inizio dell'ultima preparazione, zero se non ne e' partita."""
    if not _iniziata:
        return 0.0
    return max(0.0, time.monotonic() - _iniziata)


def prepara(nome: str) -> bool:
    """Comincia a caricare il modello in sottofondo. Vero se e' partito adesso.

    Il primo caricamento scarica i pesi, e possono volerci minuti. Farlo
    accadere **dentro** la prima richiesta vuol dire una richiesta che non
    risponde per minuti: qualunque cosa stia davanti al server la taglia molto
    prima — Cloudflare a cento secondi — e chi ha parlato riceve un 524, che
    non ha niente a che vedere con cio' che ha detto e non suggerisce nemmeno
    di riprovare.

    Percio' si comincia all'avvio del servizio, quando nessuno sta aspettando.
    """
    if not disponibile() or caricato(nome):
        return False

    global _preparazione, _ultimo_errore, _iniziata
    with _lucchetto_preparazione:
        if _preparazione is not None and _preparazione.is_alive():
            return False
        _ultimo_errore = ""
        _iniziata = time.monotonic()
        _preparazione = threading.Thread(
            target=_prepara_adesso, args=(nome,), name="shinra-whisper", daemon=True
        )
        _preparazione.start()
    return True


def perche_non_e_pronto() -> str:
    """Perche' l'ultimo caricamento e' fallito, o stringa vuota se non lo e'.

    Serve a non confondere «sto lavorando» con «ci ho provato»: sono due
    stati che da fuori si assomigliano e portano a due comportamenti
    opposti — aspettare, oppure andare a guardare cosa non va.
    """
    return _ultimo_errore


def _prepara_adesso(nome: str) -> None:
    """Il corpo del filo di preparazione.

    Un guasto qui non deve spegnere niente, ma non deve nemmeno sparire: se
    il filo muore in silenzio, da fuori il servizio sembra star ancora
    caricando, e il microfono ripete «riprova fra un minuto» per sempre. Il
    motivo si tiene, e diventa il messaggio che legge chi ha premuto.
    """
    global _ultimo_errore
    try:
        carica(nome)
    except Exception as errore:  # pragma: no cover - dipende dall'ambiente
        _ultimo_errore = str(errore) or errore.__class__.__name__
        logger.error("Preparazione del modello non riuscita: %s", errore, exc_info=True)


def scarica() -> None:
    """Dimentica il modello. Serve ai test e a chi cambia modello a caldo."""
    global _modello, _modello_caricato, _ultimo_errore, _iniziata
    with _lucchetto:
        _modello = None
        _modello_caricato = ""
        _ultimo_errore = ""
        _iniziata = 0.0


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
