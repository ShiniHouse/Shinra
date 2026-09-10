"""Chi ha parlato: dall'identificativo di Amazon a un profilo di casa.

`domain/voce.py` decide *come* si passa da un identificativo vocale a un
profilo, e cosa fare quando non ci si arriva. Qui c'e' il resto: leggere
l'archivio delle voci sentite, annotare il passaggio, e — l'unica parte che
cambia qualcosa fuori da se' — dire al contesto della richiesta chi sta
agendo.

Sta fra i servizi e non fra le capacita' perche' non e' una cosa che la casa
sa fare: e' una decisione su chi puo' chiedergliela.

Riferimento: issue #48, ADR 0004.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from shinra.domain import voce as dominio
from shinra.domain.contesto import dichiara_identita, dichiara_identita_ignota

logger = logging.getLogger("Shinra.Voci")


class ServizioVoci:
    """L'identita' del canale vocale, e la sua gestione dalle impostazioni."""

    # ------------------------------------------------------- riconoscere

    def identifica(self, dati: Mapping[str, Any]) -> dominio.Identita:
        """Chi ha parlato, secondo la richiesta appena arrivata.

        Annota il passaggio prima di risolvere: una voce che parla per la
        prima volta deve comparire nelle impostazioni **anche** se nessuno
        l'ha ancora associata, altrimenti associarla vorrebbe dire copiare a
        mano un identificativo opaco letto in un log.
        """
        from shinra.infra.db import depositi

        person_id = dominio.persona_dalla_richiesta(dati)
        if not person_id:
            return dominio.Identita(motivo=dominio.SENZA_PROFILI_VOCALI)

        depositi.voci_sentite.segna_passaggio(person_id)
        profili = {u["id"]: u for u in depositi.utenti.elenco()}
        return dominio.risolvi(person_id, depositi.voci_sentite.associazioni(), profili)

    def applica(self, identita: dominio.Identita) -> None:
        """Scrive l'identita' nel contesto della richiesta.

        E' la riga che rende reali i permessi sul canale vocale: da qui in
        poi `permessi.profilo_corrente()` sa rispondere, e i controlli che
        fino alla issue #48 non scattavano mai cominciano a scattare.
        """
        if identita.riconosciuta and identita.user_id:
            dichiara_identita(identita.user_id)
            return
        dichiara_identita_ignota()
        logger.info("Voce non attribuita (%s): valgono i permessi minimi.", identita.motivo)

    # -------------------------------------------------- dalle impostazioni

    def elenco(self) -> list[dict[str, Any]]:
        """Le voci sentite, con il nome del profilo quando c'e' n'e' uno."""
        from shinra.infra.db import depositi

        nomi = {u["id"]: u.get("name", u["id"]) for u in depositi.utenti.elenco()}
        righe = []
        for riga in depositi.voci_sentite.elenco():
            utente = riga.get("user_id")
            righe.append({**riga, "nome_profilo": nomi.get(utente) if utente else None})
        return righe

    def associa(self, person_id: str, user_id: Optional[str], nota: str = "") -> Optional[dict[str, Any]]:
        """Dice di chi e' una voce. `user_id` vuoto la riporta a sconosciuta.

        Un profilo inesistente viene rifiutato qui e non piu' avanti: e'
        l'unico punto in cui qualcuno decide a mano chi puo' comandare la
        casa parlando, e un errore di battitura non deve produrre
        un'associazione che sembra valida.
        """
        from shinra.infra.db import depositi

        if user_id and depositi.utenti.per_id(user_id) is None:
            raise ValueError(f"Il profilo «{user_id}» non esiste.")
        return depositi.voci_sentite.associa(person_id, user_id or None, nota)

    def dimentica(self, person_id: str) -> bool:
        from shinra.infra.db import depositi

        return depositi.voci_sentite.dimentica(person_id)


servizio_voci = ServizioVoci()
