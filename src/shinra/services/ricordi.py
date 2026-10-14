"""I ricordi, per chi li vede: leggerli, scriverli, correggerli, cancellarli, dimenticare tutto di se' (#249, ADR 0009).

La regola di chi vede cosa sta in `domain/ricordi.py` ed e' applicata **qui**, nel codice, non nell'interfaccia: un profilo che
indovina l'identificativo di un ricordo altrui riceve «non trovato», come se non esistesse. Ognuno vede solo i propri ricordi
privati (nemmeno un amministratore legge quelli di un altro); la casa la legge chi puo' leggere la conoscenza e la scrive chi
puo' scriverla.

Il registro delle azioni dice **che** e' successo e **quale campo**, mai il testo di un ricordo.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping, Optional

from shinra.domain import ricordi as regole
from shinra.domain.recupero import IMPORTANZA_FISSATA
from shinra.infra.data_store import data_store
from shinra.infra.db import depositi
from shinra.services import permessi, registro

TESTO_MASSIMO = 500
CATEGORIA_MASSIMA = 64
STATI = (regole.STATO_ATTIVO, regole.STATO_PROPOSTO, regole.STATO_ARCHIVIATO)
AMBITI = ("tutti", "casa", "mio")
CAMPI_MODIFICABILI = ("text", "category", "importanza", "stato", "enabled")


class RicordoNonTrovato(LookupError):
    """Non esiste, oppure e' il privato di un altro: per chi chiede e' la stessa cosa."""


class NonConsentito(PermissionError):
    pass


class DatoNonValido(ValueError):
    pass


def _id(profilo: Any) -> str:
    return str(getattr(profilo, "id", "") or "")


def come_si_mostra(ricordo: Mapping[str, Any]) -> dict[str, Any]:
    """Un ricordo per l'interfaccia, con l'ambito detto a parole."""
    importanza = int(ricordo.get("importanza") or 3)
    return {
        "id": ricordo["id"],
        "testo": ricordo.get("text", ""),
        "categoria": ricordo.get("category", "generale"),
        "ambito": "casa" if regole.e_della_casa(ricordo) else "mio",
        "origine": ricordo.get("origine", "manuale"),
        "importanza": importanza,
        "fissato": importanza >= IMPORTANZA_FISSATA,
        "usi": int(ricordo.get("usi") or 0),
        "ultimo_uso": ricordo.get("ultimo_uso"),
        "stato": ricordo.get("stato", regole.STATO_ATTIVO),
        "attivo": bool(ricordo.get("enabled", True)),
    }


def _visibile(profilo: Any, identificativo: str) -> dict[str, Any]:
    ricordo = depositi.fatti.per_id(identificativo)
    if ricordo is None or not regole.e_visibile_a(ricordo, _id(profilo)):
        raise RicordoNonTrovato(identificativo)
    return ricordo


def elenco(
    profilo: Any,
    ambito: str = "tutti",
    origine: Optional[str] = None,
    stato: Optional[str] = None,
    importanza_min: Optional[int] = None,
) -> list[dict[str, Any]]:
    """I ricordi che questo profilo vede, con i filtri chiesti."""
    if ambito not in AMBITI:
        raise DatoNonValido(f"ambito: uno fra {', '.join(AMBITI)}")
    visti = []
    for r in depositi.fatti.elenco():
        if not regole.e_visibile_a(r, _id(profilo)):
            continue
        if ambito == "casa" and not regole.e_della_casa(r):
            continue
        if ambito == "mio" and regole.e_della_casa(r):
            continue
        if origine and r.get("origine") != origine:
            continue
        if stato and r.get("stato") != stato:
            continue
        if importanza_min is not None and int(r.get("importanza") or 3) < importanza_min:
            continue
        visti.append(come_si_mostra(r))
    return visti


def _pulisci(campi: Mapping[str, Any]) -> dict[str, Any]:
    pulito: dict[str, Any] = {}
    if "text" in campi:
        testo = " ".join(str(campi["text"] or "").split())
        if not testo:
            raise DatoNonValido("testo: non puo' essere vuoto")
        if len(testo) > TESTO_MASSIMO:
            raise DatoNonValido(f"testo: al massimo {TESTO_MASSIMO} caratteri")
        pulito["text"] = testo
    if "category" in campi:
        pulito["category"] = " ".join(str(campi["category"] or "").split())[:CATEGORIA_MASSIMA] or "generale"
    if "importanza" in campi:
        try:
            valore = int(campi["importanza"])
        except (TypeError, ValueError) as errore:
            raise DatoNonValido("importanza: un numero da 1 a 5") from errore
        if not 1 <= valore <= 5:
            raise DatoNonValido("importanza: da 1 a 5")
        pulito["importanza"] = valore
    if "stato" in campi:
        if campi["stato"] not in STATI:
            raise DatoNonValido(f"stato: uno fra {', '.join(STATI)}")
        pulito["stato"] = campi["stato"]
    if "enabled" in campi:
        pulito["enabled"] = bool(campi["enabled"])
    return pulito


def crea(
    profilo: Any, testo: str, categoria: str = "generale", ambito: str = "mio", importanza: int = 3
) -> dict[str, Any]:
    """Scrive un ricordo, della casa o proprio. Serve il permesso di scrivere la conoscenza, per l'uno e per l'altro."""
    if ambito not in ("casa", "mio"):
        raise DatoNonValido("ambito: casa oppure mio")
    if not permessi.ha_permesso(profilo, permessi.SCRIVI_CONOSCENZA):
        raise NonConsentito("Non hai il permesso di insegnare cose nuove all'assistente.")
    if ambito == "mio" and not _id(profilo):
        raise NonConsentito("Serve un profilo per scrivere un ricordo proprio.")
    dati = _pulisci({"text": testo, "category": categoria, "importanza": importanza})
    proprietario = regole.CASA if ambito == "casa" else _id(profilo)
    # Un doppione si cerca **fra i ricordi dello stesso ambito**: confrontarsi col privato di un altro direbbe che esiste.
    for r in depositi.fatti.elenco():
        stesso = str(r.get("text", "")).strip().casefold() == dati["text"].casefold()
        if regole.proprietario_di(r) == proprietario and stesso:
            return come_si_mostra(r)
    ricordo = depositi.fatti.aggiungi(
        {
            "id": f"k_{uuid.uuid4().hex[:8]}",
            "text": dati["text"],
            "category": dati["category"],
            "enabled": True,
            "proprietario": proprietario,
            "origine": "manuale",
            "importanza": dati["importanza"],
            "stato": regole.STATO_ATTIVO,
        }
    )
    registro.registra("ricordo.scritto", dettagli={"id": ricordo["id"], "ambito": ambito})
    return come_si_mostra(ricordo)


def _puo_toccare(profilo: Any, ricordo: Mapping[str, Any]) -> bool:
    return regole.puo_modificare(
        ricordo, _id(profilo), permessi.ha_permesso(profilo, permessi.SCRIVI_CONOSCENZA)
    )


def modifica(profilo: Any, identificativo: str, campi: Mapping[str, Any]) -> dict[str, Any]:
    """Corregge un ricordo: testo, categoria, importanza («fissa» = 5), stato, acceso/spento. Il proprietario non si cambia."""
    esistente = _visibile(profilo, identificativo)
    if not _puo_toccare(profilo, esistente):
        raise NonConsentito("Non hai il permesso di cambiare i ricordi della casa.")
    if any(k not in CAMPI_MODIFICABILI for k in campi):
        raise DatoNonValido(f"campi modificabili: {', '.join(CAMPI_MODIFICABILI)}")
    dati = _pulisci(campi)
    if not dati:
        raise DatoNonValido("nessun campo da cambiare")
    aggiornato = depositi.fatti.aggiorna(identificativo, dati)
    if aggiornato is None:
        raise RicordoNonTrovato(identificativo)
    registro.registra("ricordo.modificato", dettagli={"id": identificativo, "campi": sorted(dati)})
    return come_si_mostra(aggiornato)


def cancella(profilo: Any, identificativo: str) -> bool:
    """Cancella un ricordo, e con lui il suo vettore. Il proprio privato si cancella sempre; quello della casa chi la scrive."""
    esistente = _visibile(profilo, identificativo)
    # Il proprio privato si cancella anche senza il permesso di scrivere (`puo_modificare` lo prevede): dimenticare e' un
    # diritto di chi viene ricordato. Quello della casa lo cancella solo chi puo' scriverla.
    if not _puo_toccare(profilo, esistente):
        raise NonConsentito("Non hai il permesso di cancellare i ricordi della casa.")
    cancellato = data_store.cancella_fatto(identificativo)
    if cancellato:
        registro.registra("ricordo.cancellato", dettagli={"id": identificativo})
    return cancellato


def dimentica_tutto_di_me(profilo: Any) -> int:
    """Cancella **tutti i ricordi privati** di questo profilo, e i loro vettori. Quelli della casa non si toccano."""
    if not _id(profilo):
        raise NonConsentito("Serve un profilo.")
    mio = _id(profilo)
    quanti = 0
    for r in depositi.fatti.elenco():
        if regole.proprietario_di(r) == mio and data_store.cancella_fatto(str(r["id"])):
            quanti += 1
    registro.registra("ricordi.dimenticati", dettagli={"profilo": mio, "quanti": quanti})
    return quanti
