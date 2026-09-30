import inspect
import logging
from typing import Any, Callable, Dict, List

from shinra.services import registro
from shinra.services.permessi import PermessoNegato
from shinra.skills.catalogo import (
    agenda,
    casa,
    clima_e_tapparelle,
    dispositivi,
    energia,
    informazioni,
    promemoria,
    sicurezza,
)

logger = logging.getLogger(__name__)

# Gli strumenti stanno nei moduli di `skills/catalogo/`, uno per dominio: qui si
# mettono insieme e si esegue quello che il modello sceglie.
TOOL_HANDLERS: Dict[str, Callable] = {
    **informazioni.GESTORI,
    **casa.GESTORI,
    **promemoria.GESTORI,
    **dispositivi.GESTORI,
    **sicurezza.GESTORI,
    **clima_e_tapparelle.GESTORI,
    **energia.GESTORI,
    **agenda.GESTORI,
}

# Schemi compatibili con Ollama / OpenAI Tools
TOOLS_SCHEMA: List[Dict[str, Any]] = [
    *informazioni.SCHEMI,
    *casa.SCHEMI,
    *promemoria.SCHEMI,
    *dispositivi.SCHEMI,
    *sicurezza.SCHEMI,
    *clima_e_tapparelle.SCHEMI,
    *energia.SCHEMI,
    *agenda.SCHEMI,
]


async def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Esegue un tool registrato passando gli argomenti forniti dal modello LLM.

    E' il passaggio obbligato di ogni azione: comandi ai dispositivi,
    attivazione di modalita', meteo, notizie, promemoria. Per questo il
    registro delle azioni (issue #15) si attacca qui e non in dieci posti
    diversi — un tool nuovo risulta tracciato senza che nessuno se ne debba
    ricordare.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        registro.registra(
            f"tool.{tool_name}", esito=registro.ESITO_ERRORE, dettagli={"errore": "tool sconosciuto"}
        )
        return {"success": False, "error": f"Tool '{tool_name}' non trovato nel registro."}

    with registro.traccia(f"tool.{tool_name}", {"parametri": arguments}) as voce:
        try:
            if inspect.iscoroutinefunction(handler):
                esito = await handler(**arguments)
            else:
                esito = handler(**arguments)
        except PermessoNegato as negato:
            # Un rifiuto non e' un guasto, e non va raccontato come tale: chi
            # ha chiesto deve sapere cosa gli manca, non che «qualcosa e'
            # andato storto». Il registro lo ha gia' scritto in `esigi`.
            logger.info("Permesso negato su %s: %s", tool_name, negato.permesso)
            voce["esito"] = registro.ESITO_NEGATO
            voce["dettagli"]["permesso"] = negato.permesso
            return {
                "success": False,
                "error": negato.spiegazione,
                "permesso_negato": True,
                "spiegazione": negato.spiegazione,
            }
        except Exception as e:
            logger.error(f"Errore durante l'esecuzione del tool {tool_name} con args {arguments}: {e}")
            voce["esito"] = registro.ESITO_ERRORE
            voce["dettagli"]["errore"] = str(e)
            return {"success": False, "error": str(e)}

        # I tool segnalano i guasti restituendoli, non sollevandoli: senza
        # questo controllo un comando fallito comparirebbe nel registro come
        # riuscito, che e' il modo peggiore di avere un registro.
        if isinstance(esito, dict) and (esito.get("error") or esito.get("success") is False):
            voce["esito"] = registro.ESITO_ERRORE
            voce["dettagli"]["errore"] = str(esito.get("error") or "operazione non riuscita")
        return esito
