"""Intenti che portano notizie dal mondo: meteo, notizie, enciclopedia."""

from __future__ import annotations

import logging
import re
from typing import Optional

from shinra.config.settings import settings
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra
from shinra.skills.registry import execute_tool

logger = logging.getLogger("Shinra.Intenti")

PAROLE_METEO = (
    "meteo",
    "tempo a",
    "tempo fa",
    "tempo farà",
    "previsioni",
    "pioverà",
    "piove",
    "temperatura",
    "gradi fuori",
)

# «a Reggio Emilia», «ad Alfonsine», «a San Giovanni in Persiceto». Il nome
# puo' essere composto e contenere preposizioni interne: si prendono le
# parole che cominciano per maiuscola piu' i collegamenti fra loro. La
# vecchia espressione ne catturava una sola, e spezzava a meta' meta' Italia.
CITTA = re.compile(
    r"\b(?:a|ad|in|per|di)\s+"
    r"((?:[A-ZÀ-Ù][\wàèéìòùç']*)(?:\s+(?:d[ei]|del|della|delle|dei|in|al|sul|sulla|a)\s+[A-ZÀ-Ù]?[\wàèéìòùç']*|\s+[A-ZÀ-Ù][\wàèéìòùç']*)*)"
)


class Meteo(Intento):
    """Il tempo che fa, fuori.

    La temperatura di casa la legge un altro intento, con priorita' piu'
    alta: qui si finisce solo quando la domanda riguarda l'esterno.
    """

    nome = "meteo"
    priorita = 50

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in PAROLE_METEO)

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
        trovata = CITTA.search(testo)
        if trovata:
            candidata = " ".join(trovata.group(1).split()).strip(" .,?!")
            if candidata:
                return candidata
        return settings.assistant.default_city or "Roma"

    @staticmethod
    def _frase(esito: dict, testo: str) -> str:
        localita = esito.get("localita", "")
        previsioni = esito.get("previsioni", [])
        if "domani" in testo and len(previsioni) > 1:
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
        argomenti = {"category": "generale"}
        esito = await execute_tool("get_latest_news", argomenti)
        richiesta.annota("get_latest_news", argomenti, esito)

        if not esito.get("success"):
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

    INNESCHI = (
        "cosa significa",
        "chi era",
        "chi è",
        "chi fu",
        "definizione di",
        "cos'è",
        "che cos'è",
        "spiegami",
        "quando è",
        "quando e",
        "patrono",
        "storia di",
        "dove si trova",
        "chi sono",
        "biografia di",
    )

    PULIZIA = re.compile(
        r"^(cosa significa|chi era|chi è|chi fu|definizione di|cos'è|che cos'è|spiegami|"
        r"il termine|la parola|quando è|quando e|dove si trova|storia di|patrono di|"
        r"la festa di|il santo)\s+",
        re.IGNORECASE,
    )

    def applicabile(self, richiesta: Richiesta) -> bool:
        return any(p in richiesta.minuscolo for p in self.INNESCHI)

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        termine = self.PULIZIA.sub("", richiesta.testo).strip(" ?.,\"'")
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
