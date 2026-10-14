"""Il materiale del sogno: cosa e' successo oggi, per profilo, con un tetto (#258).

Il sogno notturno riflette su cio' che **c'e' davvero**: le azioni eseguite (il registro), i riassunti delle conversazioni
(scritti dal codice dai fatti verificati) e i ricordi scritti o cambiati. Non si inventa materiale che non c'e'.

Le regole che questo modulo tiene ferme, e che i test difendono:

- **il materiale di un profilo non contiene niente di un altro**: righe di registro di un altro attore, riassunti e ricordi
  privati altrui restano fuori. Fa eccezione la **casa condivisa**: le azioni senza attore (le routine, le regole) e i ricordi
  della casa;
- **niente testo libero oltre a cio' che il codice ha gia' verificato**: del registro si prende il solo *nome* dell'azione e
  quante volte (mai i dettagli, che possono avere nomi, luoghi, codici); dei riassunti il testo scritto dal codice;
  dei ricordi solo quanti e di che categoria, mai il testo;
- **un tetto di dimensione**: anche con mesi di registro il materiale non supera i limiti, e dice quando ha tagliato.

Puro: nessun database, nessuna rete.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

AZIONI_MASSIME = 12
RIASSUNTI_MASSIMI = 4
CATEGORIE_MASSIME = 8
CARATTERI_MASSIMI = 2000


@dataclass
class Materiale:
    """Cio' che il sogno sa di un profilo in un periodo."""

    profilo: str
    da: Optional[datetime] = None
    a: Optional[datetime] = None
    # Dal nome dell'azione a quante volte ({riuscite, fallite}); solo le piu' frequenti.
    azioni: dict[str, dict[str, int]] = field(default_factory=dict)
    # Le azioni senza un attore (routine, regole): la casa condivisa.
    azioni_della_casa: dict[str, int] = field(default_factory=dict)
    riassunti: list[str] = field(default_factory=list)
    # Ricordi scritti o cambiati nel periodo: solo il numero e le categorie, mai il testo.
    ricordi_toccati: int = 0
    categorie: list[str] = field(default_factory=list)
    troncato: bool = False

    @property
    def vuoto(self) -> bool:
        return not (self.azioni or self.azioni_della_casa or self.riassunti or self.ricordi_toccati)

    def caratteri(self) -> int:
        return len(self.come_testo())

    def come_testo(self) -> str:
        """Il materiale in una forma compatta, per misurarlo (e, dopo, per darlo al modello)."""
        righe = [f"{n}: {c['riuscite']}+{c['fallite']}" for n, c in self.azioni.items()]
        righe += [f"casa {n}: {q}" for n, q in self.azioni_della_casa.items()]
        righe += self.riassunti
        righe += [f"ricordi toccati: {self.ricordi_toccati}"] if self.ricordi_toccati else []
        righe += self.categorie
        return "\n".join(righe)


def _di(voce: Mapping[str, Any]) -> str:
    return str(voce.get("attore") or "")


def raccogli(
    profilo: str,
    voci: Iterable[Mapping[str, Any]],
    riassunti: Iterable[Mapping[str, Any]],
    ricordi: Iterable[Mapping[str, Any]],
    da: Optional[datetime] = None,
    a: Optional[datetime] = None,
) -> Materiale:
    """Il materiale di `profilo`: solo suo (piu' la casa condivisa), dentro i tetti.

    `voci` sono righe di registro (`attore`, `azione`, `esito`), `riassunti` righe di `riassunti_conversazione` (`profilo`,
    `testo`), `ricordi` righe di `knowledge` (`proprietario`, `category`). Chi chiama passa anche cio' che non e' del profilo:
    il filtro e' **qui**, in un punto solo, e si prova con righe di piu' profili mescolate.
    """
    m = Materiale(profilo=profilo, da=da, a=a)

    proprie: dict[str, dict[str, int]] = {}
    casa: Counter[str] = Counter()
    for v in voci:
        nome = str(v.get("azione") or "")
        if not nome:
            continue
        attore = _di(v)
        if attore == profilo and profilo:
            conta = proprie.setdefault(nome, {"riuscite": 0, "fallite": 0})
            conta["riuscite" if str(v.get("esito") or "ok") == "ok" else "fallite"] += 1
        elif not attore:
            casa[nome] += 1
        # l'azione di un altro attore non entra: nemmeno come numero

    piu_frequenti = sorted(proprie.items(), key=lambda c: (-(c[1]["riuscite"] + c[1]["fallite"]), c[0]))
    if len(piu_frequenti) > AZIONI_MASSIME:
        m.troncato = True
    m.azioni = dict(piu_frequenti[:AZIONI_MASSIME])
    della_casa = casa.most_common(AZIONI_MASSIME)
    if len(casa) > AZIONI_MASSIME:
        m.troncato = True
    m.azioni_della_casa = dict(della_casa)

    miei = [r for r in riassunti if str(r.get("profilo") or "") == profilo and profilo]
    if len(miei) > RIASSUNTI_MASSIMI:
        m.troncato = True
    m.riassunti = [str(r.get("testo") or "") for r in miei[-RIASSUNTI_MASSIMI:]]

    toccati = [r for r in ricordi if str(r.get("proprietario") or "") in ("", profilo)]
    m.ricordi_toccati = len(toccati)
    categorie = Counter(str(r.get("category") or "generale") for r in toccati)
    if len(categorie) > CATEGORIE_MASSIME:
        m.troncato = True
    m.categorie = [c for c, _ in categorie.most_common(CATEGORIE_MASSIME)]

    # Il tetto finale: se ancora troppo, si accorciano per prime le cose meno informative.
    while m.caratteri() > CARATTERI_MASSIMI and (m.azioni_della_casa or m.riassunti or m.azioni):
        m.troncato = True
        if m.azioni_della_casa:
            m.azioni_della_casa.popitem()
        elif m.riassunti:
            m.riassunti.pop(0)
        else:
            m.azioni.popitem()
    return m
