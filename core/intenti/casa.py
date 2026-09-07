"""Intenti che riguardano la casa: dispositivi, modalita', temperatura interna."""

from __future__ import annotations

import logging
import re
from typing import Optional

from core.data_store import data_store
from core.intenti.base import Intento, Richiesta, Risposta, registra
from core.tools.registry import execute_tool

logger = logging.getLogger("Shinra.Intenti")

# Parole che dicono «qui dentro», non «fuori». Servono a distinguere «che
# temperatura c'e' in salotto» — un sensore di casa — da «che temperatura c'e'
# a Bologna», che e' il meteo.
SEGNALI_INTERNI = (
    "in casa",
    "dentro",
    "qui",
    "in salotto",
    "in cucina",
    "in camera",
    "in bagno",
    "in sala",
    "in soggiorno",
    "in taverna",
    "in garage",
    "in mansarda",
    "in studio",
    "in corridoio",
    "in ingresso",
    "in cantina",
)


class TemperaturaInterna(Intento):
    """«Che temperatura c'e' in salotto» legge il sensore, non le previsioni.

    Prima il percorso rapido del meteo scattava sulla sola parola
    «temperatura» e interrogava Open-Meteo: alla domanda sulla stanza si
    rispondeva con la temperatura esterna della citta'. Sbagliata, e detta
    con sicurezza.
    """

    nome = "temperatura-interna"
    priorita = 30  # prima del meteo

    def applicabile(self, richiesta: Richiesta) -> bool:
        testo = richiesta.minuscolo
        if not any(p in testo for p in ("temperatura", "che caldo", "che freddo", "gradi")):
            return False
        if any(s in testo for s in SEGNALI_INTERNI):
            return True
        # Anche il nome di un dispositivo configurato vale come «qui dentro»:
        # chi ha un alias «clima camera» sta parlando di casa sua.
        return any((a.get("alias") or "").lower() in testo for a in data_store.get_aliases())

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        stanza = self._stanza(richiesta.minuscolo)
        esito = await execute_tool("get_indoor_temperature", {"room": stanza})
        richiesta.annota("get_indoor_temperature", {"room": stanza}, esito)

        if not esito.get("success"):
            # Nessun sensore, o Home Assistant irraggiungibile: meglio dirlo
            # che rispondere con la temperatura di fuori.
            return Risposta(esito.get("message") or "Non riesco a leggere i sensori di casa.")

        letture = esito.get("letture", [])
        if not letture:
            dove = f" in {stanza}" if stanza else " in casa"
            return Risposta(f"Non trovo un sensore di temperatura{dove}.")

        if len(letture) == 1:
            sola = letture[0]
            return Risposta(f"{sola['nome']}: {sola['valore']} gradi.")

        elenco = ", ".join(f"{voce['nome']} {voce['valore']}" for voce in letture[:4])
        return Risposta(f"Temperature in casa: {elenco} gradi.")

    @staticmethod
    def _stanza(testo: str) -> str:
        trovata = re.search(r"\b(?:in|nel|nella|del|della|al|alla)\s+([a-zàèéìòù]+)", testo)
        return trovata.group(1) if trovata else ""


class ControlloDispositivo(Intento):
    """«Accendi la luce della cucina»: il comando diretto, senza passare dal modello."""

    nome = "controllo-dispositivo"
    priorita = 40

    ESPRESSIONE = re.compile(
        r"^(accendi|attiva|spegni|disattiva)\s+(?:la\s+|il\s+|le\s+|l'|i\s+|gli\s+)?(.+)$",
        re.IGNORECASE,
    )

    def applicabile(self, richiesta: Richiesta) -> bool:
        return self.ESPRESSIONE.match(richiesta.testo.strip()) is not None

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        trovato = self.ESPRESSIONE.match(richiesta.testo.strip())
        if not trovato:
            return None

        verbo = trovato.group(1).lower()
        cercato = trovato.group(2).strip().lower()
        accende = verbo in ("accendi", "attiva")
        azione = "turn_on" if accende else "turn_off"

        entita, nome = self._risolvi(cercato)
        if not entita:
            return None  # non e' un dispositivo noto: ci pensi il modello

        argomenti = {"entity_id": entita, "action": azione}
        esito = await execute_tool("control_device", argomenti)
        richiesta.annota("control_device", argomenti, esito)
        if richiesta.memoria is not None:
            # Senza questa riga «spegnila» non puo' funzionare: nella
            # cronologia non resterebbe scritto quale luce e' stata accesa.
            richiesta.memoria.add_tool_interaction("control_device", argomenti, esito)

        return Risposta(f"{nome.capitalize()} {'acceso' if accende else 'spento'}.")

    @staticmethod
    def _risolvi(cercato: str) -> tuple[Optional[str], str]:
        for alias in data_store.get_aliases():
            nome = (alias.get("alias") or "").lower()
            if nome and (nome == cercato or nome in cercato or cercato in nome):
                return alias.get("entity_id"), alias.get("alias") or cercato
        return None, cercato


class AttivaModalita(Intento):
    """«Modalita' cinema»: le routine configurate dall'utente."""

    nome = "modalita"
    priorita = 20

    def applicabile(self, richiesta: Richiesta) -> bool:
        return self._trova(richiesta.minuscolo) is not None

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        modalita = self._trova(richiesta.minuscolo)
        if not modalita:
            return None

        argomenti = {"mode_name": modalita.get("name")}
        esito = await execute_tool("activate_mode", argomenti)
        richiesta.annota("activate_mode", argomenti, esito)
        return Risposta(f"Modalità {modalita.get('name')} attivata.")

    @staticmethod
    def _trova(testo: str) -> Optional[dict]:
        for modalita in data_store.get_modes():
            if not modalita.get("enabled", True):
                continue
            for frase in modalita.get("trigger_phrases") or []:
                if frase and frase.lower() in testo:
                    return modalita
        return None


registra(AttivaModalita())
registra(TemperaturaInterna())
registra(ControlloDispositivo())
