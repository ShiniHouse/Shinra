"""Liste della spesa e delle cose da fare: quale lista, e quali voci.

La decisione che conta in questo modulo non e' scritta in nessuna funzione,
ma le determina tutte: **una lista ha un padrone solo.**

Home Assistant ha le entita' `todo`, e chi ce le ha le vede sul telefono, nel
widget, sull'Echo. Tenerne una copia qui e sincronizzarla vorrebbe dire due
verita' che divergono al primo conflitto — la spesa aggiunta dal telefono
mentre la casa e' offline, la voce spuntata da tutti e due — e una lista della
spesa sbagliata e' peggio di nessuna lista, perche' ci si va al supermercato.

Quindi: se in Home Assistant c'e' una lista `todo` che corrisponde, si scrive
li' e si legge di li'. Le liste proprie, sul database di casa, esistono solo
per chi non ha `todo` configurato. Non si specchiano mai.

Qui non si chiama niente: entrano nomi e voci, escono decisioni.

Riferimento: issue #25.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

DOMINIO_HA = "todo"

# I nomi con cui una persona chiama le liste, e cio' che vogliono dire. Non
# e' una traduzione: e' il fatto che «la spesa», «lista della spesa» e «cosa
# manca» sono la stessa lista.
SINONIMI: dict[str, tuple[str, ...]] = {
    "spesa": ("spesa", "supermercato", "compere", "shopping", "cosa manca", "alimentari"),
    "cose da fare": ("cose da fare", "da fare", "todo", "to do", "faccende", "impegni casa"),
    "regali": ("regali", "regalo", "idee regalo"),
}

NOME_PREDEFINITO = "spesa"


@dataclass(frozen=True)
class Voce:
    testo: str
    fatta: bool = False


def normalizza(testo: str) -> str:
    piatto = unicodedata.normalize("NFD", (testo or "").lower())
    piatto = "".join(c for c in piatto if unicodedata.category(c) != "Mn")
    return " ".join(piatto.replace("_", " ").replace("'", " ").split())


def nome_canonico(detto: str) -> str:
    """Da «la spesa» a `spesa`. Chi non nomina nessuna lista intende la spesa."""
    piatto = normalizza(detto)
    if not piatto:
        return NOME_PREDEFINITO

    # Le parole di servizio non aiutano a riconoscere niente.
    piatto = re.sub(r"\b(?:la|le|il|lo|di|della|delle|dei|degli|lista|liste)\b", " ", piatto)
    piatto = " ".join(piatto.split())
    if not piatto:
        return NOME_PREDEFINITO

    for canonico, parole in SINONIMI.items():
        for parola in parole:
            if normalizza(parola) in piatto or piatto in normalizza(parola):
                return canonico

    # Un nome che non conosciamo e' comunque un nome: chi ha una lista
    # «cantina» ha diritto alla sua lista «cantina».
    return piatto


def scegli_entita(detto: str, entita: Sequence[dict[str, Any]]) -> Optional[str]:
    """La lista `todo` di Home Assistant che corrisponde a cio' che e' stato
    detto, se ce n'e' una.

    `None` non e' un errore: vuol dire che questa lista, in Home Assistant,
    non c'e', e quindi va tenuta in casa. E' il bivio su cui poggia tutto il
    modulo.
    """
    if not entita:
        return None

    cercato = nome_canonico(detto)
    parole_cercate = set(cercato.split())

    migliore: Optional[str] = None
    punteggio_migliore = 0

    for voce in entita:
        entity_id = str(voce.get("entity_id", ""))
        if not entity_id.startswith(f"{DOMINIO_HA}."):
            continue

        nome = str((voce.get("attributes") or {}).get("friendly_name") or entity_id.split(".", 1)[1])
        candidato = normalizza(nome)
        punteggio = len(parole_cercate & set(candidato.split()))

        # Il nome canonico dentro al nome dell'entita' vale piu' di una
        # parola in comune: «Lista della spesa» contiene «spesa».
        if cercato and cercato in candidato:
            punteggio += 2
        for parola in SINONIMI.get(cercato, ()):
            if normalizza(parola) in candidato:
                punteggio += 2
                break

        if punteggio > punteggio_migliore:
            migliore, punteggio_migliore = entity_id, punteggio

    if punteggio_migliore > 0:
        return migliore

    # Con una lista `todo` sola e nessuna corrispondenza, e' quella: chi ne
    # ha una la chiama come gli pare.
    solo_todo = [
        str(v.get("entity_id")) for v in entita if str(v.get("entity_id", "")).startswith(f"{DOMINIO_HA}.")
    ]
    return solo_todo[0] if len(solo_todo) == 1 else None


def voci_da_ha(grezze: Iterable[dict[str, Any]]) -> list[Voce]:
    """Dalle voci come le manda `todo.get_items` alle nostre."""
    fuori: list[Voce] = []
    for voce in grezze or []:
        testo = str(voce.get("summary") or voce.get("item") or "").strip()
        if not testo:
            continue
        fuori.append(Voce(testo, str(voce.get("status", "")).lower() == "completed"))
    return fuori


def gia_presente(testo: str, voci: Iterable[Voce]) -> Optional[Voce]:
    """La voce che dice gia' questa cosa, se c'e'.

    «Aggiungi il latte» a una lista che ha gia' il latte non deve fare due
    latti: al supermercato si legge una lista con due righe uguali e si
    compra due volte.
    """
    cercato = normalizza(testo)
    if not cercato:
        return None
    for voce in voci:
        altro = normalizza(voce.testo)
        if cercato == altro or cercato in altro.split() or altro in cercato.split():
            return voce
    return None


def separa_voci(detto: str) -> list[str]:
    """«Latte, pane e uova» sono tre voci, non una.

    Una persona che detta la spesa non si ferma dopo il primo articolo, e una
    riga «latte pane e uova» costringe a rileggerla al supermercato.
    """
    piatto = (detto or "").strip()
    if not piatto:
        return []

    pezzi = re.split(r"\s*(?:,|;|\se\s|\sed\s)\s*", piatto)
    return [p.strip(" .;,") for p in pezzi if p.strip(" .;,")]


def riassumi(nome: str, voci: Sequence[Voce]) -> str:
    """La lista come si dice a voce."""
    da_fare = [v for v in voci if not v.fatta]

    if not da_fare:
        return f"La lista {nome} e' vuota." if not voci else f"Nella lista {nome} e' tutto spuntato."

    if len(da_fare) == 1:
        return f"Nella lista {nome} c'e' solo {da_fare[0].testo}."

    elencate = ", ".join(v.testo for v in da_fare[:-1])
    return f"Nella lista {nome}: {elencate} e {da_fare[-1].testo}."
