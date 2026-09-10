"""«Accendi la luce» — ma quale, e dove.

Finora la risposta era: la prima che capita. `resolve_alias_or_entity`
cercava l'alias con un `riferimento in nome`, quindi «luce» corrispondeva a
«luce cucina», «luce salotto» e «luce bagno» insieme, e vinceva quella che
l'archivio restituiva per prima. Nessun avviso, nessun modo di accorgersene
se non guardando quale lampadina si accende.

Questo modulo tiene ferme tre cose.

**Un riferimento ambiguo si dichiara ambiguo.** Scegliere a caso fra tre luci
e' peggio che chiedere: chi ascolta crede di essere stato capito, e la
prossima volta ripetera' la stessa frase aspettandosi lo stesso risultato. La
casa che chiede «quale?» perde due secondi; la casa che indovina perde la
fiducia.

**La stanza di chi parla scioglie l'ambiguita' prima di ogni altra cosa.** E'
tutto il senso di un punto di ascolto per stanza (issue #33): «accendi la
luce» detto in cucina vuol dire quella della cucina, e non c'e' bisogno di
dirlo.

**Le parole si cercano tutte, non come sottostringa.** «luce» dentro «luce
cucina» e' una corrispondenza; «ce» dentro «luce» non lo e', e con la
sottostringa lo era.

Qui non si comanda niente e non si legge nessun archivio: entrano un
riferimento, l'elenco di cio' che la casa conosce e la stanza di chi ha
parlato; esce quale dispositivo, o perche' non si puo' dire.

Riferimento: issue #33.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

# Perche' non si e' potuto scegliere.
TROVATO = "trovato"
NESSUNO = "nessuno"
AMBIGUO = "ambiguo"


def normalizza(testo: Any) -> str:
    """Minuscolo, senza accenti, senza punteggiatura di contorno.

    «Salotto», «salotto» e «Salottò» sono la stessa stanza. Gli accenti si
    tolgono perche' chi scrive un alias dalla tastiera del telefono a volte li
    mette e a volte no, e due stanze che differiscono per un accento sono due
    stanze che non si incontreranno mai.
    """
    grezzo = unicodedata.normalize("NFD", str(testo or "").strip().lower())
    senza_accenti = "".join(c for c in grezzo if unicodedata.category(c) != "Mn")
    # Tutto cio' che non e' lettera o cifra diventa uno spazio: cosi' «luce,
    # cucina», «luce_cucina» e «luce cucina» sono la stessa cosa, e la
    # punteggiatura di una frase trascritta non fa sembrare diverse due frasi
    # uguali.
    solo_utili = "".join(c if c.isalnum() else " " for c in senza_accenti)
    return " ".join(solo_utili.split())


# Parole che non restringono niente: «la luce del salotto» e «luce salotto»
# devono valere uguale. Sono poche apposta — un elenco lungo comincia a
# buttare via parole che qualcuno ha usato per distinguere due dispositivi.
VUOTE = frozenset(
    {
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "l",
        "un",
        "uno",
        "una",
        "del",
        "della",
        "dello",
        "dei",
        "delle",
        "degli",
        "di",
        "da",
        "in",
        "nel",
        "nella",
    }
)


def parole(testo: Any) -> list[str]:
    return [p for p in normalizza(testo).split() if p not in VUOTE]


@dataclass(frozen=True)
class Dispositivo:
    """Cio' che la casa sa di un dispositivo, per poterlo riconoscere."""

    entity_id: str
    alias: str = ""
    stanza: str = ""


@dataclass(frozen=True)
class Esito:
    """Quale dispositivo, oppure perche' non si puo' dire.

    `alternative` c'e' perche' «non ho capito quale» non aiuta nessuno: chi
    riceve questo esito deve poter chiedere «la cucina o il salotto?», e per
    farlo gli servono i nomi.
    """

    tipo: str
    entity_id: str = ""
    alternative: tuple[Dispositivo, ...] = field(default_factory=tuple)

    @property
    def certo(self) -> bool:
        return self.tipo == TROVATO


def _corrisponde(cercate: Sequence[str], dispositivo: Dispositivo) -> bool:
    """Tutte le parole cercate compaiono nel nome del dispositivo.

    In questa direzione e non nell'altra: «luce» trova «luce cucina», mentre
    «luce cucina» non deve trovare «luce» — chiedere di piu' restringe, non
    allarga.
    """
    disponibili = set(parole(dispositivo.alias)) | set(parole(dispositivo.entity_id))
    return bool(cercate) and all(p in disponibili for p in cercate)


def _nella_stanza(dispositivi: Sequence[Dispositivo], stanza: str) -> list[Dispositivo]:
    cercata = normalizza(stanza)
    if not cercata:
        return []
    return [d for d in dispositivi if normalizza(d.stanza) == cercata]


def risolvi(
    riferimento: str,
    dispositivi: Iterable[Dispositivo],
    stanza: str = "",
) -> Esito:
    """Quale dispositivo intende chi ha detto questo, da questa stanza.

    L'ordine dei tentativi non e' casuale:

    1. un `entity_id` scritto per esteso e' gia' la risposta;
    2. un alias che coincide **esattamente** vince su tutto: chi ha chiamato
       un dispositivo «luce» voleva dire quello;
    3. fra i candidati, quelli della stanza di chi parla;
    4. se ne resta uno solo, e' quello;
    5. se ne restano molti, si dichiara l'ambiguita' invece di sceglierne uno.

    Il punto 5 e' il motivo per cui questo modulo esiste.
    """
    grezzo = (riferimento or "").strip()
    if "." in grezzo and " " not in grezzo:
        return Esito(TROVATO, grezzo.lower())

    elenco = list(dispositivi)
    cercate = parole(grezzo)
    if not cercate:
        return Esito(NESSUNO)

    esatti = [d for d in elenco if normalizza(d.alias) == normalizza(grezzo)]
    candidati = esatti or [d for d in elenco if _corrisponde(cercate, d)]

    if not candidati:
        return Esito(NESSUNO)

    # La stanza restringe **solo se** ci lascia qualcosa: un satellite in
    # corridoio che chiede la luce del salotto deve poterla accendere.
    in_stanza = _nella_stanza(candidati, stanza)
    if in_stanza:
        candidati = in_stanza

    if len(candidati) == 1:
        return Esito(TROVATO, candidati[0].entity_id)

    return Esito(AMBIGUO, alternative=tuple(sorted(candidati, key=lambda d: d.entity_id)))


def da_alias(righe: Iterable[Mapping[str, Any]]) -> list[Dispositivo]:
    """Gli alias dell'archivio, nella forma che questo dominio capisce."""
    return [
        Dispositivo(
            entity_id=str(r.get("entity_id") or ""),
            alias=str(r.get("alias") or ""),
            stanza=str(r.get("room") or ""),
        )
        for r in righe
        if r.get("entity_id")
    ]


def descrivi_alternative(alternative: Sequence[Dispositivo]) -> str:
    """Le alternative dette a voce, con la stanza quando la distingue.

    La stanza si nomina solo se serve davvero a distinguere: ripeterla quando
    e' la stessa per tutte allunga la frase e non aiuta.
    """
    stanze = {normalizza(d.stanza) for d in alternative}
    distingue = len(stanze) > 1 and all(s for s in stanze)

    nomi = []
    for d in alternative:
        nome = d.alias or d.entity_id
        nomi.append(f"{nome} ({d.stanza})" if distingue else nome)

    if len(nomi) <= 1:
        return "".join(nomi)
    return ", ".join(nomi[:-1]) + " o " + nomi[-1]
