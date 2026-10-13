"""I ricordi come file Markdown leggibile, e il confronto di un file riletto (#251).

Un file che si apre con un editor e' una buona forma di trasparenza. Ma il **database resta la fonte**: il file e' una
vista, scritta quando la si chiede e riletta quando la si chiede, mai tenuta allineata di continuo. Per questo qui non c'e'
nessuna scrittura: `esporta` produce il testo, `confronta` dice cosa cambierebbe un file riletto e basta. Chi lo applica
(un servizio, dopo l'anteprima e la conferma) scrive.

Il file e' scritto in modo che chi lo modifica a mano non possa far danni fuori ambito:

- gli identificativi stanno in commenti `<!-- id:... -->` e **contano solo se il ricordo e' fra quelli che chi importa puo'
  gia' modificare**. Un identificativo sconosciuto (di un altro profilo, inventato) non sovrascrive niente: la riga e' un
  ricordo **nuovo**;
- una riga senza identificativo e' un ricordo nuovo; un ricordo che manca dal file e' proposto come **tolto**, mai tolto da qui;
- tutto cio' che arriva da un file e' solo un'**anteprima**: nuovi, modificati, tolti. Nessuno di questi e' ancora attivo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional

INTESTAZIONE = "# Memorie di Shinra"
AVVISO = (
    "> **Questo file contiene dati personali.** Tienilo al sicuro e non condividerlo. Puoi correggere il testo, spostare una "
    "riga sotto un'altra categoria o cancellarla; **non toccare i commenti `<!-- id:... -->`**. Il file non si sincronizza da "
    "solo: per applicare le modifiche si importa, si guarda l'anteprima e si conferma."
)

_ID = re.compile(r"\s*<!--\s*id:([A-Za-z0-9_\-]+)(\s+spento)?\s*-->\s*$")
_CATEGORIA = re.compile(r"^##\s+(.+?)\s*$")
_VOCE = re.compile(r"^[-*]\s+(.*\S)\s*$")


@dataclass(frozen=True)
class Voce:
    """Una riga del file riletta."""

    testo: str
    categoria: str
    identificativo: Optional[str] = None
    attivo: bool = True


@dataclass
class Differenze:
    """Cosa cambierebbe applicando il file. Solo un'anteprima."""

    nuovi: list[Voce] = field(default_factory=list)
    modificati: list[tuple[Mapping[str, Any], Voce]] = field(default_factory=list)
    tolti: list[Mapping[str, Any]] = field(default_factory=list)
    invariati: int = 0
    ignorate: int = 0

    @property
    def vuota(self) -> bool:
        return not (self.nuovi or self.modificati or self.tolti)


def _una_riga(testo: str) -> str:
    """Un ricordo sta su una riga sola: gli a capo e i commenti non devono poter rompere il file."""
    pulito = re.sub(r"<!--.*?-->", " ", str(testo or ""), flags=re.S)
    return " ".join(pulito.split())


def esporta(fatti: Iterable[Mapping[str, Any]], filtro: Optional[Callable[[str], str]] = None) -> str:
    """Il Markdown dei ricordi, raggruppati per categoria. `filtro` ripulisce ogni testo (es. segreti), se serve."""
    per_categoria: dict[str, list[Mapping[str, Any]]] = {}
    for fatto in fatti:
        categoria = _una_riga(fatto.get("category") or "generale") or "generale"
        per_categoria.setdefault(categoria, []).append(fatto)

    righe = [INTESTAZIONE, "", AVVISO]
    for categoria in sorted(per_categoria):
        righe += ["", f"## {categoria}", ""]
        for fatto in per_categoria[categoria]:
            testo = _una_riga(fatto.get("text") or "")
            if filtro:
                testo = _una_riga(filtro(testo))
            if not testo:
                continue
            spento = "" if fatto.get("enabled", True) else " spento"
            righe.append(f"- {testo} <!-- id:{fatto['id']}{spento} -->")
    return "\n".join(righe) + "\n"


def leggi(contenuto: str) -> tuple[list[Voce], int]:
    """Le voci di un file, e quante righe non si sono capite. Mai un'eccezione: un file ostile non deve rompere niente."""
    voci: list[Voce] = []
    ignorate = 0
    categoria = "generale"
    for riga in (contenuto or "").splitlines():
        if not riga.strip() or riga.startswith(">"):
            continue
        trovata = _CATEGORIA.match(riga)
        if trovata:
            categoria = trovata.group(1).strip() or "generale"
            continue
        if riga.startswith("#"):
            continue
        voce = _VOCE.match(riga)
        if not voce:
            ignorate += 1
            continue
        resto = voce.group(1)
        identificativo: Optional[str] = None
        attivo = True
        marcato = _ID.search(resto)
        if marcato:
            identificativo = marcato.group(1)
            attivo = marcato.group(2) is None
            resto = resto[: marcato.start()]
        testo = _una_riga(resto)
        if not testo:
            ignorate += 1
            continue
        voci.append(Voce(testo=testo, categoria=categoria, identificativo=identificativo, attivo=attivo))
    return voci, ignorate


def confronta(contenuto: str, modificabili: Iterable[Mapping[str, Any]]) -> Differenze:
    """Cosa cambierebbe rileggendo il file, rispetto ai ricordi che chi importa puo' gia' modificare.

    `modificabili` e' l'unico perimetro: un identificativo che non e' li' dentro non tocca nulla e la riga conta come nuova.
    """
    esistenti = {str(f["id"]): f for f in modificabili}
    voci, ignorate = leggi(contenuto)
    diff = Differenze(ignorate=ignorate)
    visti: set[str] = set()
    testi_nuovi: set[tuple[str, str]] = set()

    for voce in voci:
        attuale = esistenti.get(voce.identificativo or "")
        if attuale is None or voce.identificativo in visti:
            # Nuovo: senza id, con un id sconosciuto (fuori ambito) o ripetuto nel file. Mai due volte lo stesso testo.
            chiave = (voce.testo.casefold(), voce.categoria.casefold())
            if chiave in testi_nuovi:
                continue
            testi_nuovi.add(chiave)
            diff.nuovi.append(Voce(voce.testo, voce.categoria, None, voce.attivo))
            continue
        visti.add(str(voce.identificativo))
        categoria_attuale = _una_riga(attuale.get("category") or "generale") or "generale"
        uguale = (
            _una_riga(attuale.get("text") or "") == voce.testo
            and categoria_attuale == voce.categoria
            and bool(attuale.get("enabled", True)) == voce.attivo
        )
        if uguale:
            diff.invariati += 1
        else:
            diff.modificati.append((attuale, voce))

    diff.tolti = [f for i, f in esistenti.items() if i not in visti]
    return diff
