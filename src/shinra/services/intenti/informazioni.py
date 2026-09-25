"""Intenti che portano notizie dal mondo: meteo, notizie, enciclopedia."""

from __future__ import annotations

import logging
from typing import Optional

from shinra.config.settings import settings
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra
from shinra.services.intenti.lingue import schemi
from shinra.skills.registry import execute_tool

logger = logging.getLogger("Shinra.Intenti")


class Meteo(Intento):
    """Il tempo che fa, fuori.

    La temperatura di casa la legge un altro intento, con priorita' piu'
    alta: qui si finisce solo quando la domanda riguarda l'esterno.
    """

    nome = "meteo"
    priorita = 50

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in schemi().parole_meteo)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        citta = self.citta(richiesta.testo)
        argomenti = {"location": citta, "days": 2}
        esito = await execute_tool("get_weather", argomenti)
        richiesta.annota("get_weather", argomenti, esito)

        if not esito.get("success"):
            # La citta' estratta potrebbe non esistere — «il tempo a casa
            # mia». Invece di una lista di parole da escludere scritta a
            # mano, si chiede alla geocodifica: se non la conosce, si
            # ripiega sulla citta' predefinita.
            predefinita = settings.assistant.default_city or "Roma"
            if citta.lower() == predefinita.lower():
                return None  # nessuna risposta: ci pensi il modello
            logger.info("Citta' '%s' non riconosciuta: ripiego su %s", citta, predefinita)
            argomenti = {"location": predefinita, "days": 2}
            esito = await execute_tool("get_weather", argomenti)
            richiesta.annota("get_weather", argomenti, esito)
            if not esito.get("success"):
                return None

        return Risposta(self._frase(esito, richiesta.minuscolo))

    @staticmethod
    def citta(testo: str) -> str:
        trovata = schemi().citta.search(testo)
        if trovata:
            candidata = " ".join(trovata.group(1).split()).strip(" .,?!")
            if candidata:
                return candidata
        return settings.assistant.default_city or "Roma"

    @staticmethod
    def _frase(esito: dict, testo: str) -> str:
        localita = esito.get("localita", "")
        previsioni = esito.get("previsioni", [])
        if schemi().domani in testo and len(previsioni) > 1:
            domani = previsioni[1]
            return (
                f"Domani a {localita} {domani.get('condizione', 'variabile').lower()}, "
                f"max {domani.get('temp_max')} gradi e min {domani.get('temp_min')}."
            )

        adesso = esito.get("adesso", {})
        frase = f"A {localita} attualmente {adesso.get('temperatura', '')}, {(adesso.get('condizione') or '').lower()}."
        if previsioni:
            frase += f" Massima prevista di {previsioni[0].get('temp_max')} gradi."
        return frase


class Notizie(Intento):
    nome = "notizie"
    priorita = 60

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(
            p in richiesta.minuscolo for p in ("notizie", "ultime notizie", "rassegna stampa", "cosa succede")
        )

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        # Le categorie preferite del profilo che ha parlato. Erano salvate
        # nell'anagrafica fin dalla prima versione e non le leggeva nessuno:
        # la rassegna era identica per tutti, e sceglierle nell'interfaccia
        # non cambiava niente (issue #26).
        preferite = list(getattr(richiesta.profilo, "preferred_news_categories", None) or [])
        argomenti: dict = {"categorie": preferite} if preferite else {"category": "generale"}

        esito = await execute_tool("get_latest_news", argomenti)
        richiesta.annota("get_latest_news", argomenti, esito)

        if not esito.get("success"):
            # «Nessuna fonte attiva» e' una risposta, non un guasto: chi ha
            # spento tutte le fonti deve sentirselo dire, non ricevere il
            # silenzio del modello che prova a cavarsela.
            if esito.get("message"):
                return Risposta(esito["message"])
            return None

        titoli = [n.get("titolo", "") for n in esito.get("notizie", [])[:2] if n.get("titolo")]
        if not titoli:
            return None
        return Risposta("Ultime notizie: " + ". ".join(titoli))


class Enciclopedia(Intento):
    """Non risponde: informa il modello.

    E' l'unico intento che restituisce sempre `None` pur avendo lavorato.
    Aggiunge il testo di Wikipedia al contesto e lascia che sia il modello a
    formulare la risposta, perche' un estratto di enciclopedia letto a voce
    non e' una risposta a una domanda.
    """

    nome = "enciclopedia"
    priorita = 70

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in schemi().inneschi_enciclopedia)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        termine = schemi().pulizia_enciclopedia.sub("", richiesta.testo).strip(" ?.,\"'")
        if not termine:
            return None

        argomenti = {"query": termine}
        esito = await execute_tool("search_wikipedia", argomenti)
        richiesta.annota("search_wikipedia", argomenti, esito)

        if esito.get("success") and esito.get("estratto"):
            richiesta.contesto.append(
                f"ENCICLOPEDIA/DATI PER '{termine.upper()}': {esito.get('estratto', '')}"
            )
        return None


registra(Meteo())
registra(Notizie())
registra(Enciclopedia())
