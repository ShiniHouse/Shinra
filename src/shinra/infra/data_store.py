"""I dati della casa: conoscenza, alias, modalita', fonti.

Dalla v0.2.0 stanno nel database (`core/archivio/`), non piu' in file JSON
riscritti per intero a ogni modifica. I nomi dei metodi e la forma di cio'
che restituiscono non sono cambiati: sopra ci sono le rotte HTTP,
l'interfaccia e l'agente, e la migrazione doveva spostare i dati, non
riscrivere meta' applicazione.

Cio' che e' cambiato davvero sono i metodi `salva_*`/`cancella_*`: toccano
una riga sola. I vecchi `save_*(elenco)`, che riscrivevano l'intera tabella
(con due richieste sovrapposte, una delle due modifiche spariva), sono stati
tolti: non li usava piu' nessuno.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from shinra.domain import stanze
from shinra.infra.db import depositi

logger = logging.getLogger(__name__)


class KnowledgeItem(BaseModel):
    id: str
    text: str
    category: str = "generale"
    enabled: bool = True


class NewsSource(BaseModel):
    id: str
    name: str
    category: str
    url: str
    enabled: bool = True


class DeviceAlias(BaseModel):
    id: str
    alias: str
    entity_id: str
    room: Optional[str] = ""
    domain: Optional[str] = "light"


class ModeAction(BaseModel):
    type: str  # 'ha_service' o 'tts'
    domain: Optional[str] = None
    service: Optional[str] = None
    entity_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class ModeItem(BaseModel):
    id: str
    name: str
    icon: Optional[str] = "zap"
    trigger_phrases: List[str] = []
    description: Optional[str] = ""
    enabled: bool = True
    actions: List[Dict[str, Any]] = []


def _identificativo(dati: Dict[str, Any], prefisso: str) -> str:
    """Un identificativo che non collide mai.

    Prima era `f"k_{len(items) + 1}"`: dopo una cancellazione quel conteggio
    torna su un numero gia' usato, e la modifica successiva sovrascrive un
    altro record invece di crearne uno. Silenziosamente.
    """
    esistente = (dati.get("id") or "").strip()
    return esistente or f"{prefisso}_{uuid.uuid4().hex[:8]}"


class DataStore:
    # ------------------------------------------------------------ conoscenza

    def get_knowledge(self) -> List[Dict[str, Any]]:
        return depositi.fatti.elenco()

    def salva_fatto(self, item: Dict[str, Any]) -> Dict[str, Any]:
        dati = dict(item)
        dati["id"] = _identificativo(dati, "k")
        return depositi.fatti.salva(dati)

    def cancella_fatto(self, identificativo: str) -> bool:
        return depositi.fatti.cancella(identificativo)

    def add_knowledge_item(
        self, text: str, category: str = "generale", enabled: bool = True
    ) -> Dict[str, Any]:
        """Aggiunge un fatto imparato durante un'intervista.

        Se un fatto identico c'e' gia' restituisce quello: durante
        un'intervista capita di ripetersi, e ogni fatto finisce nel prompt di
        ogni risposta.
        """
        return depositi.fatti.aggiungi_fatto(text, category, enabled)

    def get_enabled_knowledge_summary(self) -> str:
        attivi = [f"- {f['text']}" for f in depositi.fatti.elenco() if f.get("enabled", True)]
        return "\n".join(attivi) if attivi else "Nessuna informazione personalizzata registrata."

    # ---------------------------------------------------------------- fonti

    def get_sources(self) -> List[Dict[str, Any]]:
        return depositi.fonti.elenco()

    def salva_fonte(self, fonte: Dict[str, Any]) -> Dict[str, Any]:
        dati = dict(fonte)
        dati["id"] = _identificativo(dati, "src")
        return depositi.fonti.salva(dati)

    def cancella_fonte(self, identificativo: str) -> bool:
        return depositi.fonti.cancella(identificativo)

    def imposta_tutte_le_fonti(self, attive: bool) -> int:
        fonti = depositi.fonti.elenco()
        for f in fonti:
            depositi.fonti.aggiorna(f["id"], {"enabled": attive})
        return len(fonti)

    # ---------------------------------------------------------------- alias

    def get_aliases(self) -> List[Dict[str, Any]]:
        return depositi.alias.elenco()

    def salva_alias(self, alias: Dict[str, Any]) -> Dict[str, Any]:
        dati = dict(alias)
        dati["id"] = _identificativo(dati, "alias")
        return depositi.alias.salva(dati)

    def cancella_alias(self, identificativo: str) -> bool:
        return depositi.alias.cancella(identificativo)

    def cerca_dispositivo(self, query_name: str, stanza: str = "") -> stanze.Esito:
        """Quale dispositivo, oppure perche' non si puo' dire.

        La scelta la fa `domain/stanze.py`; qui si legge soltanto l'archivio.
        Chi ha bisogno di sapere che il riferimento era ambiguo chiama questa;
        chi vuole solo tirare avanti chiama `resolve_alias_or_entity`.
        """
        return stanze.risolvi(query_name, stanze.da_alias(depositi.alias.elenco()), stanza)

    def resolve_alias_or_entity(self, query_name: str, stanza: str = "") -> str:
        """Risolve un nome detto a voce nell'entity_id esatto di Home Assistant.

        Restituisce il riferimento cosi' com'e' quando non lo riconosce **o
        quando e' ambiguo**: chi chiama questa funzione non ha modo di gestire
        un'ambiguita', e a valle c'e' `skills/entita.verifica` che sa dirlo.
        Prima l'ambiguita' non esisteva proprio: la ricerca era un
        `riferimento in nome`, quindi «luce» corrispondeva a «luce cucina»,
        «luce salotto» e «luce bagno», e vinceva quella che l'archivio
        restituiva per prima. Silenziosamente.
        """
        esito = self.cerca_dispositivo(query_name, stanza)
        return esito.entity_id if esito.certo else query_name.strip().lower()

    def get_aliases_summary(self) -> str:
        righe = [
            f"- '{a.get('alias')}' → `{a.get('entity_id')}` ({a.get('room') or 'Generale'})"
            for a in depositi.alias.elenco()
        ]
        return "\n".join(righe) if righe else "Nessun alias configurato."

    # ----------------------------------------------------------- modalita'

    def get_modes(self) -> List[Dict[str, Any]]:
        return depositi.modalita.elenco()

    def salva_modalita(self, modalita: Dict[str, Any]) -> Dict[str, Any]:
        dati = dict(modalita)
        dati["id"] = _identificativo(dati, "mode")
        return depositi.modalita.salva(dati)

    def cancella_modalita(self, identificativo: str) -> bool:
        return depositi.modalita.cancella(identificativo)

    def get_modes_summary(self) -> str:
        righe = []
        for m in depositi.modalita.elenco():
            if m.get("enabled", True):
                frasi = ", ".join(f"'{t}'" for t in (m.get("trigger_phrases") or []))
                righe.append(
                    f"- Modalità '{m.get('name')}' (frasi di attivazione: {frasi}): "
                    f"{m.get('description') or ''}"
                )
        return "\n".join(righe) if righe else "Nessuna modalità configurata."


data_store = DataStore()
