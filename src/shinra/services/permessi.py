"""Cosa ciascuno puo' fare in casa.

Fino alla v0.2.0 il profilo distingueva adulto, ragazzo e bambino, ma quella
distinzione cambiava **solo il tono delle risposte**: `restricted_topics`
esisteva nel modello senza che una riga lo applicasse, e un bambino poteva
comandare qualunque cosa.

Due idee, entrambe dall'ADR 0004.

**I permessi appartengono a un ruolo, non alla persona.** I ruoli si creano:
oltre ai predefiniti possono nascere «Collaboratrice domestica», «Nonno»,
«Ospite fine settimana», ognuno con la sua combinazione.

**`sicurezza.comanda` sta da solo.** Serrature e allarme non sono lampadine:
sbagliare li' ha conseguenze di un altro ordine, e chi puo' accendere una
luce non deve per questo poter aprire la porta di casa.

Riferimento: issue #19, ADR 0004.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("Shinra.Permessi")

# --------------------------------------------------------------------------
# I permessi
# --------------------------------------------------------------------------

COMANDA_DISPOSITIVI = "dispositivi.comanda"
COMANDA_SICUREZZA = "sicurezza.comanda"
ATTIVA_MODALITA = "modalita.attiva"
MODIFICA_MODALITA = "modalita.modifica"
LEGGI_CONOSCENZA = "conoscenza.leggi"
SCRIVI_CONOSCENZA = "conoscenza.scrivi"
GESTISCI_UTENTI = "utenti.gestisci"
GESTISCI_IMPOSTAZIONI = "impostazioni.gestisci"

PERMESSI: dict[str, str] = {
    COMANDA_DISPOSITIVI: "Luci, prese, clima, tapparelle",
    COMANDA_SICUREZZA: "Serrature e allarme",
    ATTIVA_MODALITA: "Avviare routine e scenari",
    MODIFICA_MODALITA: "Creare o modificare una routine",
    LEGGI_CONOSCENZA: "Leggere cio' che l'assistente sa della casa",
    SCRIVI_CONOSCENZA: "Insegnare cose nuove all'assistente",
    GESTISCI_UTENTI: "Creare, modificare e cancellare i profili",
    GESTISCI_IMPOSTAZIONI: "Token, modello, configurazione",
}

TUTTI = tuple(PERMESSI)

# I domini di Home Assistant che contano come sicurezza. Tutto il resto e'
# «dispositivi»: una lampadina sbagliata si rispegne, una serratura no.
DOMINI_SICUREZZA = frozenset({"lock", "alarm_control_panel"})

# --------------------------------------------------------------------------
# I ruoli predefiniti
# --------------------------------------------------------------------------
#
# Gli identificativi coincidono con i valori che il campo `role` ha gia' nei
# profili esistenti: cosi' la migrazione e' una corrispondenza, non una
# riscrittura, e nessuno si ritrova senza ruolo dopo l'aggiornamento.

RUOLI_PREDEFINITI: list[dict[str, Any]] = [
    {
        "id": "admin",
        "nome": "Amministratore",
        "descrizione": "Puo' fare tutto, compreso gestire profili e impostazioni.",
        "permessi": list(TUTTI),
        "predefinito": True,
    },
    {
        "id": "adult",
        "nome": "Adulto",
        "descrizione": "Comanda la casa, comprese serrature e allarme. Non tocca profili ne' impostazioni.",
        "permessi": [
            COMANDA_DISPOSITIVI,
            COMANDA_SICUREZZA,
            ATTIVA_MODALITA,
            MODIFICA_MODALITA,
            LEGGI_CONOSCENZA,
            SCRIVI_CONOSCENZA,
        ],
        "predefinito": True,
    },
    {
        "id": "teen",
        "nome": "Ragazzo",
        "descrizione": "Comanda luci e clima e avvia le routine. Niente serrature.",
        "permessi": [COMANDA_DISPOSITIVI, ATTIVA_MODALITA, LEGGI_CONOSCENZA],
        "predefinito": True,
    },
    {
        "id": "child",
        "nome": "Bambino",
        "descrizione": "Luci e routine. Niente serrature, niente impostazioni.",
        "permessi": [COMANDA_DISPOSITIVI, ATTIVA_MODALITA, LEGGI_CONOSCENZA],
        "predefinito": True,
    },
    {
        "id": "guest",
        "nome": "Ospite",
        "descrizione": "Puo' chiedere, non comandare.",
        "permessi": [LEGGI_CONOSCENZA],
        "predefinito": True,
    },
]


class PermessoNegato(Exception):
    """Sollevata quando manca un permesso. Porta con se' come spiegarlo.

    Un rifiuto muto e' inutile a chi lo riceve: «non hai il permesso di
    aprire la serratura» dice cosa e' successo e cosa chiedere. Un 403
    secco lascia solo l'impressione che qualcosa sia rotto.
    """

    def __init__(self, permesso: str, spiegazione: str = ""):
        self.permesso = permesso
        self.spiegazione = spiegazione or f"Non hai il permesso «{PERMESSI.get(permesso, permesso)}»."
        super().__init__(self.spiegazione)


def permesso_per_dominio(dominio: str) -> str:
    return COMANDA_SICUREZZA if dominio in DOMINI_SICUREZZA else COMANDA_DISPOSITIVI


def permessi_del_ruolo(id_ruolo: Optional[str]) -> set[str]:
    """I permessi di un ruolo, letti dal database.

    Un ruolo che non esiste non da' permessi. E' voluto: se qualcuno
    cancella un ruolo ancora assegnato, quei profili restano senza poteri
    invece di ereditarli tutti.
    """
    from shinra.infra.db import depositi

    if not id_ruolo:
        return set()
    riga = depositi.ruoli.per_id(id_ruolo)
    if riga is None:
        logger.warning("Ruolo '%s' non trovato: nessun permesso.", id_ruolo)
        return set()
    return set(riga.get("permessi") or [])


def ha_permesso(profilo: Any, permesso: str) -> bool:
    """Se questo profilo ha questo permesso.

    Un profilo assente significa «nessuna identita' in gioco»: succede con
    l'autenticazione disattivata, ed e' la stessa scelta che si e' fatta li'
    — casa aperta. Non e' un buco nascosto: `verifica_configurazione()`
    avverte a voce alta quando l'autenticazione e' spenta.
    """
    if profilo is None:
        return True
    return permesso in permessi_del_ruolo(getattr(profilo, "role", None))


def esigi(profilo: Any, permesso: str) -> None:
    """Come `ha_permesso`, ma solleva. Ogni rifiuto finisce nel registro."""
    if ha_permesso(profilo, permesso):
        return

    from shinra.services import registro

    registro.registra(
        "permesso.negato",
        esito=registro.ESITO_NEGATO,
        dettagli={"permesso": permesso, "ruolo": getattr(profilo, "role", None)},
        attore=getattr(profilo, "id", None),
    )
    raise PermessoNegato(permesso)


def profilo_corrente() -> Any:
    """Chi sta agendo adesso, secondo il contesto della richiesta.

    Restituisce `None` quando non c'e' nessuna identita' in gioco: una
    richiesta senza sessione con l'autenticazione spenta, oppure un'azione
    che parte dal sistema — lo scheduler che annuncia un promemoria
    sull'Echo. Il sistema non ha un ruolo, e non ha senso negargli i
    permessi che gli ha dato l'utente quando ha creato il promemoria.
    """
    from shinra.services import registro
    from shinra.services.user_manager import user_manager

    attore = registro.contesto().attore
    return user_manager.get_user_by_id(attore) if attore else None


def esigi_per_dominio(dominio: str) -> None:
    """Il controllo sui comandi ai dispositivi, dal dominio dell'entita'.

    Sta qui e non nei singoli tool perche' tutto passa da
    `HomeAssistantClient.call_service`: comandi diretti, scenari e le azioni
    dentro una routine. E' cosi' che si ottiene il requisito piu' scomodo
    della issue — **una routine si esegue con i permessi di chi la invoca**,
    non di chi l'ha scritta. Altrimenti il controllo si aggira scrivendo una
    routine.
    """
    esigi(profilo_corrente(), permesso_per_dominio(dominio))


def assicura_ruoli_predefiniti() -> list[str]:
    """Crea i ruoli predefiniti mancanti. Non tocca quelli gia' presenti.

    Non sovrascrive: se hai tolto le serrature agli adulti, resta com'e' hai
    deciso tu. Aggiunge soltanto cio' che manca, cosi' una versione futura
    puo' introdurre un permesso nuovo senza disfare le tue scelte.
    """
    from shinra.infra.db import depositi

    creati = []
    for ruolo in RUOLI_PREDEFINITI:
        if depositi.ruoli.per_id(ruolo["id"]) is None:
            depositi.ruoli.aggiungi(ruolo)
            creati.append(ruolo["id"])
    if creati:
        logger.info("Ruoli predefiniti creati: %s", ", ".join(creati))
    return creati
