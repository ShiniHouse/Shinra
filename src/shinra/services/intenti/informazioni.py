"""Intenti che portano notizie dal mondo: meteo, notizie, enciclopedia."""

from __future__ import annotations

import logging
from typing import Optional

from shinra.config.settings import settings
from shinra.infra.lingue import schemi
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra
from shinra.skills.registry import execute_tool
from shinra.skills.weather import meteo_di_un_luogo

logger = logging.getLogger("Shinra.Intenti")


class Meteo(Intento):
    """Il tempo che fa, fuori.

    La temperatura di casa la legge un altro intento, con priorita' piu'
    alta: qui si finisce solo quando la domanda riguarda l'esterno.
    """

    nome = "meteo"
    priorita = 50

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in richiesta.schemi.parole_meteo)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        lingua = richiesta.schemi

        # Un luogo registrato vince sulla citta' scritta nel file di configurazione: il nome nella frase («al mare»), poi
        # la casa principale. Le coordinate restano qui dentro: nelle azioni va il nome, a Open-Meteo vanno arrotondate.
        luogo = self._luogo_registrato(richiesta)
        if luogo is not None:
            esito = await meteo_di_un_luogo(str(luogo["nome"]), luogo["latitudine"], luogo["longitudine"])
            richiesta.annota("get_weather", {"luogo": luogo["nome"], "days": 2}, esito)
            if esito.get("success"):
                return Risposta(self._frase(esito, richiesta.minuscolo, lingua))
            return None  # nessuna risposta: ci pensi il modello

        citta = self.citta(richiesta.testo, lingua)
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

        return Risposta(self._frase(esito, richiesta.minuscolo, lingua))

    @staticmethod
    def _luogo_registrato(richiesta: Richiesta) -> Optional[dict]:
        """Il luogo di cui si chiede il meteo: quello nominato nella frase, altrimenti la casa principale — ma solo se la
        frase non nomina una citta' (`citta` la riconosce da «a Milano»): chi chiede di Milano non vuole la sua casa.
        """
        from shinra.services import luoghi, posizione

        nominato = luoghi.nominato_nella_frase(richiesta.testo)
        if nominato is not None:
            return nominato
        if richiesta.schemi.citta.search(richiesta.testo):
            return None
        # Chi chiede «che tempo fa?» intende dove si trova: se la sua posizione e' collegata ed e' in un luogo registrato,
        # quello; altrimenti la casa principale.
        entita = getattr(richiesta.profilo, "entita_posizione", "") or ""
        if entita:
            attuale = posizione.luogo_attuale(entita, getattr(richiesta.profilo, "id", "") or "")
            if attuale is not None:
                return attuale
        return luoghi.principale()

    @staticmethod
    def citta(testo: str, lingua=None) -> str:
        trovata = (lingua or schemi()).citta.search(testo)
        if trovata:
            candidata = " ".join(trovata.group(1).split()).strip(" .,?!")
            if candidata:
                return candidata
        return settings.assistant.default_city or "Roma"

    @staticmethod
    def _frase(esito: dict, testo: str, lingua) -> str:
        localita = esito.get("localita", "")
        previsioni = esito.get("previsioni", [])
        if lingua.domani in testo and len(previsioni) > 1:
            domani = previsioni[1]
            return lingua.dice(
                "meteo_domani",
                localita=localita,
                condizione=(domani.get("condizione") or lingua.dice("condizione_variabile")).lower(),
                massima=domani.get("temp_max"),
                minima=domani.get("temp_min"),
            )

        adesso = esito.get("adesso", {})
        frase = lingua.dice(
            "meteo_adesso",
            localita=localita,
            temperatura=adesso.get("temperatura", ""),
            condizione=(adesso.get("condizione") or "").lower(),
        )
        if previsioni:
            frase += lingua.dice("meteo_massima", massima=previsioni[0].get("temp_max"))
        return frase


class Sole(Meteo):
    """A che ora sorge e tramonta il sole, **nel luogo giusto**: quello nominato, dove si trova chi parla, la casa principale."""

    nome = "sole"
    priorita = 49  # prima del meteo: «a che ora tramonta?» non e' «che tempo fa?»

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in richiesta.schemi.parole_sole)

    @staticmethod
    def _frase(esito: dict, testo: str, lingua) -> str:
        sole = esito.get("sole") or {}
        if not sole.get("alba") or not sole.get("tramonto"):
            return ""
        return lingua.dice(
            "sole_alba_tramonto",
            localita=esito.get("localita", ""),
            alba=sole["alba"],
            tramonto=sole["tramonto"],
        )

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        risposta = await super().esegui(richiesta)
        return risposta if risposta is not None and risposta.testo else None


class Notizie(Intento):
    nome = "notizie"
    priorita = 60

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in richiesta.schemi.inneschi_notizie)

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
        return Risposta(richiesta.schemi.dice("notizie_ultime", titoli=". ".join(titoli)))


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
        return any(p in richiesta.minuscolo for p in richiesta.schemi.inneschi_enciclopedia)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        termine = richiesta.schemi.pulizia_enciclopedia.sub("", richiesta.testo).strip(" ?.,\"'")
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


registra(Sole())
registra(Meteo())
registra(Notizie())
registra(Enciclopedia())
