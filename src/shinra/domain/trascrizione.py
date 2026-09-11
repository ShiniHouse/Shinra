"""Da voce a testo, e la domanda che viene prima: dove finisce l'audio.

Il riconoscimento vocale della dashboard usava la Web Speech API del browser,
che **manda l'audio ai server del produttore** — Google su Chrome, Apple su
Safari. Il modello girava in casa, la sintesi passava da Microsoft, e ogni
parola detta all'assistente usciva verso Google. Il README intanto scriveva
«Zero Cloud per i Dati Privati» e «100% privata».

Questo modulo contiene le decisioni che restano dopo aver scelto una libreria:
quale motore usare, cosa dire quando quello locale non c'e', e **cosa buttare
via di cio' che torna**.

Riferimento: issue #31.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# I due motori. Il primo tiene l'audio in casa, il secondo no — e questa e'
# l'unica differenza che conta fra loro.
LOCALE = "locale"
BROWSER = "browser"
MOTORI = (LOCALE, BROWSER)

# Per difetto si resta in casa. Se il motore locale non e' installato, il
# microfono **non funziona** e lo dice: ripiegare in silenzio sul browser
# sarebbe la stessa promessa non mantenuta di prima, con in piu' l'aggravante
# di essere stata scritta apposta.
MOTORE_PREDEFINITO = LOCALE

# Perche' il motore locale non e' pronto.
PRONTO = "pronto"
LIBRERIA_ASSENTE = "libreria_assente"
MODELLO_NON_CARICATO = "modello_non_caricato"
MODELLO_IN_PREPARAZIONE = "modello_in_preparazione"
SCELTO_IL_BROWSER = "scelto_il_browser"

# I modelli di Whisper, dal piu' svelto al piu' preciso. Su una CPU di un
# piccolo server `base` e' il compromesso che regge: `small` raddoppia
# l'attesa, `tiny` sbaglia i nomi propri — che in una casa sono quasi tutto
# («accendi la luce di Sonia»).
MODELLI = ("tiny", "base", "small", "medium", "large-v3")
MODELLO_PREDEFINITO = "base"

LINGUA_PREDEFINITA = "it"

# Quanto audio si accetta in una volta. Un endpoint che accetta caricamenti
# senza tetto e' un modo educato di riempire il disco di un server di casa, e
# venti secondi di comando parlato stanno in molto meno di questo.
MEGABYTE_MASSIMI = 8
DIMENSIONE_MASSIMA = MEGABYTE_MASSIMI * 1024 * 1024

# Cio' che il browser produce registrando. Non si accetta qualunque cosa:
# l'elenco e' quello che `MediaRecorder` sa fare, piu' il wav per chi manda
# audio da uno script.
FORMATI_ACCETTATI = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/flac",
    }
)

# Le frasi che Whisper inventa quando non sente niente.
#
# Non e' un difetto raro ne' un caso di scuola: il modello e' stato addestrato
# anche su sottotitoli, e sul silenzio produce i titoli di coda di quei
# sottotitoli. In italiano escono quasi sempre queste. Mandarle all'agente
# come se fossero un comando significa che un microfono aperto per sbaglio
# fa partire una richiesta che nessuno ha fatto.
ALLUCINAZIONI = (
    "sottotitoli e revisione a cura di",
    "sottotitoli creati dalla comunita",
    "sottotitoli creati dalla comunità",
    "sottotitoli a cura di",
    "amara.org",
    "qtss",
    "grazie per aver guardato il video",
    "grazie per l'attenzione",
    "iscriviti al canale",
    "www.mooji.org",
)

# Sotto questa lunghezza una trascrizione non e' un comando: e' un rumore che
# il modello ha interpretato. «si'» e «no» sono le eccezioni che contano —
# servono a confermare l'apertura di una serratura — e stanno sopra.
LUNGHEZZA_MINIMA = 2


@dataclass(frozen=True)
class Stato:
    """Se si puo' trascrivere in casa, e con che cosa."""

    motore: str
    motivo: str
    modello: str = ""

    @property
    def in_casa(self) -> bool:
        return self.motore == LOCALE

    @property
    def pronto(self) -> bool:
        return self.motivo in (PRONTO, SCELTO_IL_BROWSER)


def scegli_motore(configurato: str, libreria_presente: bool) -> Stato:
    """Quale motore vale adesso, e perche'.

    Un valore di configurazione che non si riconosce non fa ripiegare sul
    browser: fa ripiegare sul predefinito, che tiene l'audio in casa. Fra i
    due modi di sbagliare — «non funziona» e «funziona ma manda tutto a
    Google» — il secondo e' peggiore, perche' non si vede.
    """
    scelto = (configurato or "").strip().lower()
    if scelto not in MOTORI:
        scelto = MOTORE_PREDEFINITO

    if scelto == BROWSER:
        return Stato(BROWSER, SCELTO_IL_BROWSER)

    if not libreria_presente:
        return Stato(LOCALE, LIBRERIA_ASSENTE)

    return Stato(LOCALE, PRONTO)


def spiega(motivo: str) -> str:
    """Cosa dire a chi preme il microfono e non succede niente."""
    if motivo == LIBRERIA_ASSENTE:
        return (
            "Il riconoscimento vocale in casa non e' installato. Sul server: "
            "`pip install faster-whisper`. Fino ad allora il microfono non "
            "funziona — di proposito: l'alternativa sarebbe mandare la tua voce "
            "a Google senza dirtelo."
        )
    if motivo == MODELLO_NON_CARICATO:
        return (
            "Il modello di riconoscimento non si e' caricato. Il dettaglio e' nel "
            "log del server; il primo avvio scarica il modello e puo' volerci "
            "qualche minuto."
        )
    if motivo == MODELLO_IN_PREPARAZIONE:
        return (
            "Sto preparando il modello di riconoscimento: al primo avvio i pesi "
            "vanno scaricati, e possono volerci alcuni minuti. Riprova fra poco — "
            "succede una volta sola, poi il modello resta in memoria."
        )
    if motivo == SCELTO_IL_BROWSER:
        return (
            "Il riconoscimento vocale e' affidato al browser: l'audio esce di casa "
            "e va ai server del suo produttore. E' una scelta scritta in "
            "configurazione (`voce.motore`), non il comportamento predefinito."
        )
    return ""


def formato_accettabile(tipo: Optional[str]) -> bool:
    """Il tipo dichiarato dal browser, senza i parametri.

    `MediaRecorder` manda `audio/webm;codecs=opus`: confrontare la stringa
    intera con un elenco di tipi puliti rifiuterebbe ogni registrazione fatta
    da Chrome.
    """
    if not tipo:
        return False
    return tipo.split(";", 1)[0].strip().lower() in FORMATI_ACCETTATI


def e_allucinazione(testo: str) -> bool:
    """Vero per i titoli di coda che Whisper produce sul silenzio.

    Il confronto e' su una forma ridotta — minuscole, senza punteggiatura —
    perche' il modello varia la punteggiatura fra una volta e l'altra e un
    confronto letterale lascerebbe passare la meta' dei casi.
    """
    ridotto = re.sub(r"[^\w\s.]", " ", (testo or "").lower())
    ridotto = re.sub(r"\s+", " ", ridotto).strip()
    if not ridotto:
        return True
    return any(frase in ridotto for frase in ALLUCINAZIONI)


def pulisci(testo: str) -> str:
    """Il testo come lo riceverebbe una persona che ha scritto la frase.

    Whisper restituisce quasi sempre uno spazio in testa e a volte spezza la
    frase in segmenti che vanno riuniti. Restituisce stringa vuota per cio'
    che non e' un comando: chi trascrive deve poter distinguere «non ho
    sentito niente» da «ha detto qualcosa», e una stringa vuota lo dice senza
    bisogno di un secondo valore.
    """
    unito = re.sub(r"\s+", " ", (testo or "").strip())
    if len(unito) < LUNGHEZZA_MINIMA:
        return ""
    if e_allucinazione(unito):
        return ""
    return unito


def troppo_grande(byte: int) -> bool:
    return byte > DIMENSIONE_MASSIMA


def modello_valido(nome: str) -> str:
    """Un nome di modello sconosciuto non ferma il microfono.

    Ripiega sul predefinito e lascia che sia il log a dirlo: chi ha scritto
    `bas` invece di `base` si merita un avviso, non una casa che non ascolta.
    """
    pulito = (nome or "").strip().lower()
    return pulito if pulito in MODELLI else MODELLO_PREDEFINITO
