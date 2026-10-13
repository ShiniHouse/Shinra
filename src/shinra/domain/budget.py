"""Quanto pesa ogni parte del prompt, e cosa si taglia quando non ci sta (#244).

Ollama, quando il prompt supera `num_ctx`, **taglia l'inizio in silenzio**: sparisce per primo proprio il prompt di sistema e
nessuno lo sa. Questo modulo conta i token per componente (sistema, strumenti, ricordi, storia, domanda), dice se il
totale ci sta nel contesto lasciando posto alla risposta, e, quando non ci sta, dichiara l'**ordine** in cui si taglia:

1. la **storia grezza**, dal messaggio piu' vecchio;
2. i **ricordi** meno pertinenti (arrivano gia' ordinati dal recupero: si tolgono dall'ultimo);
3. **mai** il sistema, gli strumenti scelti e la domanda.

Non chiama niente e non conosce il modello: la stima dei token e' grossolana (vedi `stima_token`) e serve a decidere, non
a fatturare. Il numero vero lo dice Ollama (`prompt_eval_count`), ed e' quello che il banco confronta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

# Caratteri per token. In italiano e in JSON il tokenizer dei modelli piccoli sta fra 2,5 e 3,5: si prende il valore prudente
# (piu' token stimati, quindi si taglia un po' prima invece di un po' dopo).
CARATTERI_PER_TOKEN = 3.0

# L'ordine in cui si taglia, dal primo all'ultimo. Cio' che non c'e' non si taglia mai.
ORDINE_DI_TAGLIO = ("storia", "ricordi")
INTOCCABILI = ("sistema", "strumenti", "domanda")


def stima_token(testo: str) -> int:
    """Una stima dei token di un testo, sempre per eccesso (arrotonda in su)."""
    return math.ceil(len(testo) / CARATTERI_PER_TOKEN) if testo else 0


@dataclass(frozen=True)
class Misura:
    """Il peso di una richiesta, per componente."""

    componenti: Mapping[str, int]
    num_ctx: int
    risposta: int

    @property
    def totale(self) -> int:
        return sum(self.componenti.values())

    @property
    def disponibile(self) -> int:
        """I token che il prompt puo' occupare, lasciando posto alla risposta."""
        return max(0, self.num_ctx - self.risposta)

    @property
    def sfora(self) -> int:
        return max(0, self.totale - self.disponibile)

    def come_riga(self) -> str:
        parti = ", ".join(f"{nome}={n}" for nome, n in self.componenti.items())
        stato = f"SFORA di {self.sfora}" if self.sfora else "ci sta"
        return f"{parti} | totale={self.totale} su {self.disponibile} ({self.num_ctx} - {self.risposta} per la risposta): {stato}"


def misura(
    num_ctx: int,
    risposta: int,
    *,
    sistema: str = "",
    strumenti: str = "",
    ricordi: str = "",
    storia: Sequence[Mapping[str, Any]] = (),
    domanda: str = "",
) -> Misura:
    """Conta i token di ogni parte. `strumenti` e' il testo serializzato degli schemi passati al modello."""
    return Misura(
        componenti={
            "sistema": stima_token(sistema),
            "strumenti": stima_token(strumenti),
            "ricordi": stima_token(ricordi),
            "storia": sum(stima_token(str(m.get("content", ""))) + 4 for m in storia),
            "domanda": stima_token(domanda),
        },
        num_ctx=num_ctx,
        risposta=risposta,
    )


@dataclass
class Taglio:
    """Cosa si e' tolto, e perche': niente si taglia senza una traccia."""

    storia_tolta: int = 0
    ricordi_tolti: int = 0
    insufficiente: bool = False
    motivi: list[str] = field(default_factory=list)

    @property
    def tagliato(self) -> bool:
        return bool(self.storia_tolta or self.ricordi_tolti)


def riduci(
    misurato: Misura,
    storia: Sequence[Mapping[str, Any]],
    ricordi: Sequence[str],
) -> tuple[list[Mapping[str, Any]], list[str], Taglio]:
    """Toglie storia e ricordi, nell'ordine dichiarato, finche' il prompt ci sta.

    Restituisce la storia e i ricordi che restano (la storia sempre dal messaggio piu' vecchio, i ricordi dall'ultimo) e il
    `Taglio` che racconta cosa e' successo. Se tolti storia e ricordi non basta, `insufficiente` e' vero: sistema,
    strumenti e domanda da soli non ci stanno, e il chiamante deve dirlo invece di tagliare di nascosto.
    """
    taglio = Taglio()
    storia_rimasta = list(storia)
    ricordi_rimasti = list(ricordi)
    eccesso = misurato.sfora

    def peso_messaggio(m: Mapping[str, Any]) -> int:
        return stima_token(str(m.get("content", ""))) + 4

    while eccesso > 0 and storia_rimasta:
        tolto = storia_rimasta.pop(0)
        eccesso -= peso_messaggio(tolto)
        taglio.storia_tolta += 1
    if taglio.storia_tolta:
        taglio.motivi.append(f"storia: tolti {taglio.storia_tolta} messaggi, dal piu' vecchio")

    while eccesso > 0 and ricordi_rimasti:
        tolto_ricordo = ricordi_rimasti.pop()
        eccesso -= stima_token(tolto_ricordo)
        taglio.ricordi_tolti += 1
    if taglio.ricordi_tolti:
        taglio.motivi.append(f"ricordi: tolti {taglio.ricordi_tolti}, i meno pertinenti")

    if eccesso > 0:
        taglio.insufficiente = True
        taglio.motivi.append(
            "sistema, strumenti e domanda da soli non ci stanno: nulla di piu' si puo' tagliare"
        )
    return storia_rimasta, ricordi_rimasti, taglio
