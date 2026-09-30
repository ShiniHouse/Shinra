"""Intenti che riguardano la casa: dispositivi, modalita', temperatura interna."""

from __future__ import annotations

import logging
from typing import Optional

from shinra.infra.data_store import data_store
from shinra.services.intenti.base import Intento, Richiesta, Risposta, registra
from shinra.skills.registry import execute_tool

logger = logging.getLogger("Shinra.Intenti")


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
        lingua = richiesta.schemi
        if not any(p in testo for p in lingua.parole_temperatura):
            return False
        if any(s in testo for s in lingua.segnali_interni):
            return True
        # Anche il nome di un dispositivo configurato vale come «qui dentro»:
        # chi ha un alias «clima camera» sta parlando di casa sua.
        return any((a.get("alias") or "").lower() in testo for a in data_store.get_aliases())

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        lingua = richiesta.schemi
        stanza = self._stanza(richiesta.minuscolo, lingua)
        esito = await execute_tool("get_indoor_temperature", {"room": stanza})
        richiesta.annota("get_indoor_temperature", {"room": stanza}, esito)

        if not esito.get("success"):
            # Nessun sensore, o Home Assistant irraggiungibile: meglio dirlo
            # che rispondere con la temperatura di fuori.
            return Risposta(esito.get("message") or lingua.dice("temperatura_sensori_illeggibili"))

        letture = esito.get("letture", [])
        if not letture:
            if stanza:
                return Risposta(lingua.dice("temperatura_nessun_sensore_in", stanza=stanza))
            return Risposta(lingua.dice("temperatura_nessun_sensore"))

        if len(letture) == 1:
            sola = letture[0]
            return Risposta(lingua.dice("temperatura_una_lettura", nome=sola["nome"], valore=sola["valore"]))

        elenco = ", ".join(f"{voce['nome']} {voce['valore']}" for voce in letture[:4])
        return Risposta(lingua.dice("temperatura_piu_letture", elenco=elenco))

    @staticmethod
    def _stanza(testo: str, lingua) -> str:
        trovata = lingua.stanza.search(testo)
        return trovata.group(1) if trovata else ""


class ControlloDispositivo(Intento):
    """«Accendi la luce della cucina»: il comando diretto, senza passare dal modello."""

    nome = "controllo-dispositivo"
    priorita = 40

    def applicabile(self, richiesta: Richiesta) -> bool:
        return richiesta.schemi.controllo_dispositivo.match(richiesta.testo.strip()) is not None

    async def esegui(self, richiesta: Richiesta) -> Optional[Risposta]:
        lingua = richiesta.schemi
        trovato = lingua.controllo_dispositivo.match(richiesta.testo.strip())
        if not trovato:
            return None

        verbo = trovato.group(1).lower()
        cercato = trovato.group(2).strip().lower()
        accende = verbo in lingua.verbi_che_accendono
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

        if esito.get("permesso_negato"):
            return Risposta(esito.get("spiegazione", lingua.dice("dispositivo_negato")))
        if esito.get("error") or esito.get("success") is False:
            # Prima si rispondeva «acceso» comunque, anche quando il comando
            # non era arrivato: peggio che tacere, perche' chi ascolta se ne
            # va convinto che la luce sia accesa.
            return Risposta(lingua.dice("dispositivo_non_comandato", nome=nome))

        return Risposta(
            lingua.dice("dispositivo_acceso" if accende else "dispositivo_spento", nome=nome.capitalize())
        )

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
        return Risposta(richiesta.schemi.dice("modalita_attivata", nome=modalita.get("name")))

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
