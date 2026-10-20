"""Ricordi doppi o in contraddizione: il codice li trova, una persona decide (#260).

Con il tempo la memoria si riempie di frasi quasi uguali («La caldaia e' in cantina», «la caldaia sta in cantina») e, peggio,
di frasi che si smentiscono («il wifi e' CasaMia5», «il wifi e' CasaMia6»). Di notte il codice le cerca e le **propone**:
non ne cancella, non ne fonde, non ne modifica nessuna. Quella che si tiene e quella che si archivia la sceglie la persona.

Come le trova, senza modello e senza parole di una lingua:

- **doppi**: lo stesso insieme di parole (almeno `PAROLA_MINIMA` lettere), oltre `SOGLIA_DOPPIO` di somiglianza;
- **in contraddizione sospetta**: molto in comune (oltre `SOGLIA_SIMILI`) ma **numeri diversi**. E' la forma piu' frequente
  («la sveglia e' alle 7» / «alle 8») e l'unica che si riconosce senza capire la frase. Una negazione («non») o un sinonimo
  non la vede: e' un limite dichiarato, non un difetto nascosto.

Si confrontano solo ricordi **dello stesso proprietario** e ancora attivi: un ricordo privato non viene mai accostato a quello
di un altro, e il confronto non porta fuori nessun testo (chi chiama riceve solo gli identificativi).

Puro: nessun database, nessuna rete.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

PAROLA_MINIMA = 3
PAROLE_MINIME_PER_CONFRONTARE = 3
SOGLIA_DOPPIO = 0.8
SOGLIA_SIMILI = 0.5
COPPIE_MASSIME = 5
RICORDI_MASSIMI_PER_PROFILO = 300

DOPPIO = "ricordo_doppio"
CONTRADDITTORIO = "ricordo_contraddittorio"

_PAROLE = re.compile(r"[^\W\d_]{%d,}" % PAROLA_MINIMA, re.UNICODE)
_NUMERI = re.compile(r"\d+")


@dataclass(frozen=True)
class Coppia:
    tipo: str
    proprietario: str
    a: str
    b: str
    somiglianza: float

    @property
    def chiave(self) -> str:
        """Identifica la coppia, non la notte: serve a non riproporla ogni volta (e a ricordare un «no»)."""
        primo, secondo = sorted((self.a, self.b))
        return f"{self.tipo}|{primo}|{secondo}"


def _parole(testo: str) -> frozenset[str]:
    return frozenset(p.casefold() for p in _PAROLE.findall(testo))


def _numeri(testo: str) -> frozenset[str]:
    return frozenset(_NUMERI.findall(testo))


def somiglianza(a: str, b: str) -> float:
    """Quanto due frasi condividono le stesse parole, da 0 a 1 (Jaccard sulle parole di almeno `PAROLA_MINIMA` lettere)."""
    pa, pb = _parole(a), _parole(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


def trova_coppie(ricordi: Iterable[Mapping[str, Any]]) -> list[Coppia]:
    """Le coppie di ricordi privati attivi che sembrano doppie o in contraddizione, per proprietario, le piu' evidenti prime.

    Anche i ricordi **della casa** (`proprietario` vuoto) si confrontano fra loro, mai con i privati di qualcuno: la proposta
    e' della casa e la vede chi puo' scriverla. Ogni proprietario ha al massimo `COPPIE_MASSIME` proposte per notte.
    """
    per_proprietario: dict[str, list[Mapping[str, Any]]] = {}
    for r in ricordi:
        chi = str(r.get("proprietario") or "")  # vuoto: della casa
        if str(r.get("stato") or "attivo") != "attivo" or r.get("enabled") is False:
            continue
        per_proprietario.setdefault(chi, []).append(r)

    trovate: list[Coppia] = []
    for chi, suoi in per_proprietario.items():
        suoi = suoi[:RICORDI_MASSIMI_PER_PROFILO]
        candidate: list[Coppia] = []
        for i, a in enumerate(suoi):
            testo_a = str(a.get("text") or "")
            if len(_parole(testo_a)) < PAROLE_MINIME_PER_CONFRONTARE:
                continue
            for b in suoi[i + 1 :]:
                testo_b = str(b.get("text") or "")
                if len(_parole(testo_b)) < PAROLE_MINIME_PER_CONFRONTARE:
                    continue
                s = somiglianza(testo_a, testo_b)
                if s >= SOGLIA_DOPPIO and _numeri(testo_a) == _numeri(testo_b):
                    tipo = DOPPIO
                elif s >= SOGLIA_SIMILI and _numeri(testo_a) != _numeri(testo_b):
                    tipo = CONTRADDITTORIO
                else:
                    continue
                candidate.append(Coppia(tipo, chi, str(a["id"]), str(b["id"]), s))
        candidate.sort(key=lambda c: (-c.somiglianza, c.chiave))
        trovate.extend(candidate[:COPPIE_MASSIME])
    return trovate
