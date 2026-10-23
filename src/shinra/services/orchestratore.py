"""L'orchestratore: una frase con piu' cose da fare, una cosa alla volta (#432, ADR 0013).

Il banco dei piani (#430) ha mostrato che un modello da tre miliardi di parametri sbaglia piu' spesso se gli si danno insieme quattro cose, e che scrivere un piano in
anticipo non basta. Qui il **codice** (non il modello) spezza la frase (`domain/scomposizione.py`), ogni pezzo fa il giro normale dell'agente — gli intenti veloci
prima, poi il router per dominio e il modello con due o tre strumenti — e un **revisore**, anche lui codice, dice cosa e' riuscito e cosa no.

Cosa garantisce, e i test lo difendono:

- **spenta di serie** (`agenti.orchestratore`): l'ADR 0013 dice che il multi-agente si usa solo dove il banco mostra un vantaggio, e il banco non lo ha ancora mostrato in modo
  solido. Spenta, tutto va come prima;
- **un pezzo che fallisce non ferma gli altri**, e non si nasconde: la risposta dice cosa non e' riuscito;
- **un tetto**: al massimo `MASSIMO_PEZZI` pezzi (il dominio) e `MASSIMO_AZIONI` azioni in tutto, e il tempo lo limita il lavoro che la contiene («ci penso», #431);
- **il revisore non indovina**: legge i risultati degli strumenti (`success`) e riporta i fallimenti; **non** rilegge lo stato dei dispositivi (gli eventi di Home Assistant arrivano dopo
  il comando, e leggerli subito darebbe falsi allarmi) — e' un limite dichiarato;
- **la storia resta una**: i pezzi usano una memoria a perdere; nella conversazione entrano la frase intera e la risposta unita.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Mapping, Sequence

from shinra.services import registro

logger = logging.getLogger("Shinra.Orchestratore")

MASSIMO_AZIONI = 12

# Un pezzo: la frase del pezzo -> la risposta dell'agente per quel pezzo (`{"response", "actions", "success"}`).
EseguiPezzo = Callable[[str], Awaitable[Mapping[str, Any]]]


def azione_fallita(azione: Mapping[str, Any]) -> bool:
    """Lo strumento ha detto di non essere riuscito (`success: false`). Cio' che non dice niente non si dichiara fallito."""
    risultato = azione.get("result")
    return isinstance(risultato, Mapping) and risultato.get("success") is False


def rivedi(risposta: Mapping[str, Any]) -> bool:
    """Un pezzo e' riuscito se l'agente non ha segnalato un errore e nessuno strumento ha detto `success: false`."""
    if risposta.get("success") is False:
        return False
    return not any(azione_fallita(a) for a in (risposta.get("actions") or []))


async def orchestra(
    pezzi: Sequence[str],
    esegui_pezzo: EseguiPezzo,
    non_riuscito: Callable[[str], str],
    fatto: str,
) -> dict[str, Any]:
    """Fa un giro per ogni pezzo, rivede, e unisce. Ritorna `{"response", "actions", "success", "pezzi", "falliti"}`.

    `non_riuscito(elenco)` compone la frase dei pezzi falliti nella lingua di chi parla; `fatto` e' la frase se tutti i pezzi sono riusciti ma nessuno ha detto niente.
    """
    risposte: list[str] = []
    azioni: list[dict[str, Any]] = []
    falliti: list[str] = []
    for pezzo in pezzi:
        if len(azioni) >= MASSIMO_AZIONI:
            falliti.append(pezzo)  # oltre il tetto non si esegue: e si dice
            continue
        try:
            esito = await esegui_pezzo(pezzo)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Pezzo non riuscito: %r", pezzo)
            falliti.append(pezzo)
            continue
        azioni.extend(esito.get("actions") or [])
        if rivedi(esito):
            testo = str(esito.get("response") or "").strip()
            if testo:
                risposte.append(testo)
        else:
            falliti.append(pezzo)
    corpo = " ".join(risposte) if risposte else ("" if falliti else fatto)
    if falliti:
        corpo = f"{corpo} {non_riuscito('; '.join(falliti))}".strip()
    registro.registra(
        "orchestratore.scomposta",
        esito=registro.ESITO_OK if not falliti else registro.ESITO_ERRORE,
        dettagli={"pezzi": len(pezzi), "falliti": len(falliti)},
    )
    return {
        "response": corpo,
        "actions": azioni,
        "success": not falliti,
        "pezzi": len(pezzi),
        "falliti": len(falliti),
    }


def attiva() -> bool:
    """L'orchestratore e' acceso? (`agenti.orchestratore`, spento di serie.)"""
    from shinra.config.settings import settings

    return bool(settings.agenti.orchestratore)
