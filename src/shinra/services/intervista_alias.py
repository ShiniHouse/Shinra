# -*- coding: utf-8 -*-
"""L'intervista dai dispositivi veri: un nome per ciascuno (#210).

Finche' l'intervista raccoglie frasi in prosa, la casa non impara a *fare*
niente di nuovo. Qui ogni risposta diventa una capacita': il nome con cui si
chiama un dispositivo, che da quel momento Shinra capisce a voce.

Il modello non entra: l'elenco dei dispositivi viene da Home Assistant e il
nome lo scrive chi risponde. **Nessuna entita' inventata puo' entrare negli
alias**, perche' l'`entity_id` non lo scrive nessuno che non sia Home
Assistant: sta nel passo, e il passo lo costruisce il codice.

Le frasi stanno nel file della lingua di chi risponde (#207).
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from shinra.services.intervista_comune import (
    FASE_CONFERMA,
    LIMITE_CORREZIONI,
    dice,
    e_affermativa,
    e_negativa,
    normalizza,
    sezione,
    vuole_saltare,
)

logger = logging.getLogger("Shinra.Interview")

# I domini che una persona chiama per nome. Un sensore di temperatura non
# serve a «accendi la luce del corridoio».
DOMINI_DA_NOMINARE = ("light", "switch", "cover", "climate", "fan", "media_player")

# Quanti dispositivi si chiedono in una sola intervista: l'elenco vero di una
# casa ne ha centinaia, e un'intervista di cento domande non la finisce nessuno.
LIMITE_DISPOSITIVI = 6

MAX_PAROLE = 6
MAX_LUNGHEZZA = 60


def alias_proposto(risposta: str) -> Optional[str]:
    """Il nome scritto da chi risponde, ripulito, o `None` se non e' un nome.

    Un nome e' breve: una frase intera («accendo quella lampada quando mi
    siedo») non e' un modo di chiamare un dispositivo.
    """
    pulito = re.sub(r"\s+", " ", (risposta or "").strip().strip("\"'«»“”.,;:!?")).strip()
    if len(pulito) < 2 or len(pulito) > MAX_LUNGHEZZA:
        return None
    if len(pulito.split()) > MAX_PAROLE:
        return None
    return pulito


def passo_alias(dispositivo: Dict[str, Any], lingua: str = "") -> Dict[str, Any]:
    """Il passo dell'intervista per un dispositivo vero."""
    dominio = dispositivo["entity_id"].split(".")[0]
    nome = dispositivo.get("friendly_name") or dispositivo["entity_id"]
    etichetta = sezione(lingua)["etichette"].get(dominio, dominio)
    return {
        "id": f"alias:{dispositivo['entity_id']}",
        "kind": "alias",
        "category": "alias",
        "title": dice(lingua, "alias_titolo"),
        "question": dice(lingua, "alias_domanda", nome=nome, etichetta=etichetta),
        "hint": dice(lingua, "alias_hint"),
        "entity_id": dispositivo["entity_id"],
        "dominio": dominio,
    }


async def dispositivi_senza_nome(limite: int = LIMITE_DISPOSITIVI) -> List[Dict[str, Any]]:
    """I dispositivi veri di Home Assistant che non hanno ancora un alias.

    Se Home Assistant non risponde l'elenco e' vuoto: l'intervista fa le sue
    domande e basta, senza questa parte.
    """
    from shinra.infra.data_store import data_store
    from shinra.skills.entita import stati_noti

    try:
        stati = await stati_noti()
    except Exception as e:
        logger.warning("Dispositivi da nominare non letti (%s): salto questa parte.", e)
        return []

    con_alias = {a.get("entity_id") for a in data_store.get_aliases()}
    candidati = [
        {
            "entity_id": s.get("entity_id", ""),
            "friendly_name": (s.get("attributes") or {}).get("friendly_name") or s.get("entity_id", ""),
        }
        for s in stati
        if s.get("entity_id", "").split(".")[0] in DOMINI_DA_NOMINARE
        and s.get("entity_id") not in con_alias
        and s.get("state") != "unavailable"
    ]
    candidati.sort(
        key=lambda d: (DOMINI_DA_NOMINARE.index(d["entity_id"].split(".")[0]), d["friendly_name"].lower())
    )
    return candidati[:limite]


def alias_gia_usato(nome: str, alias_esistenti: List[Dict[str, Any]], entity_id: str) -> Optional[str]:
    """Se lo stesso nome indica gia' un altro dispositivo, dice quale."""
    voluto = normalizza(nome)
    for a in alias_esistenti:
        if normalizza(str(a.get("alias") or "")) == voluto and a.get("entity_id") != entity_id:
            return str(a.get("entity_id") or "")
    return None


class TurniAlias:
    """I due turni di un passo-alias, per il motore dell'intervista.

    Servono `_avanza` e `_stesso_passo` del motore: la classe e' un mixin e si
    usa solo li'. Il nome si salva **dopo** il «si'»: un alias rifiutato non
    entra nel database. Le frasi sono nella lingua della sessione.
    """

    if TYPE_CHECKING:
        # Li definisce il motore: qui servono solo a mypy, che da un mixin non li vede.
        def _avanza(
            self,
            session: Dict[str, Any],
            prefisso: str,
            salvati: List[Dict[str, Any]],
            routine: Optional[Dict[str, Any]],
            interpretato: bool,
        ) -> Dict[str, Any]: ...

        @staticmethod
        def _stesso_passo(
            session: Dict[str, Any],
            step: Dict[str, Any],
            messaggio: str,
            interpretato: bool,
            capiti: Optional[List[Dict[str, str]]] = None,
            suggerimento: Optional[str] = None,
        ) -> Dict[str, Any]: ...

    def _turno_alias(self, session, step, risposta: str, archivio) -> Dict[str, Any]:
        if session.get("fase") == FASE_CONFERMA:
            return self._conferma_alias(session, step, risposta, archivio)
        return self._chiedi_alias(session, step, risposta, archivio)

    def _chiedi_alias(self, session, step, risposta: str, archivio) -> Dict[str, Any]:
        lingua = session.get("lingua", "")
        if vuole_saltare(risposta, lingua):
            return self._avanza(session, dice(lingua, "alias_lascio"), [], None, True)
        nome = alias_proposto(risposta)
        if nome is None:
            if session["insistito"]:
                return self._avanza(session, dice(lingua, "alias_non_capito"), [], None, True)
            session["insistito"] = True
            return self._stesso_passo(session, step, dice(lingua, "alias_breve"), True)
        altro = alias_gia_usato(nome, archivio.get_aliases(), step["entity_id"])
        if altro:
            return self._stesso_passo(
                session, step, dice(lingua, "alias_gia_preso", nome=nome, altro=altro), True
            )
        session["fase"] = FASE_CONFERMA
        session["in_attesa"] = [{"text": nome, "category": "alias"}]
        return self._stesso_passo(
            session,
            step,
            dice(lingua, "alias_conferma", nome=nome),
            True,
            capiti=session["in_attesa"],
            suggerimento=dice(lingua, "alias_suggerimento"),
        )

    def _conferma_alias(self, session, step, risposta: str, archivio) -> Dict[str, Any]:
        lingua = session.get("lingua", "")
        if e_affermativa(risposta, lingua):
            nome = session["in_attesa"][0]["text"]
            archivio.salva_alias(
                {"alias": nome, "entity_id": step["entity_id"], "room": "", "domain": step["dominio"]}
            )
            session["alias_creati"] = session.get("alias_creati", 0) + 1
            return self._avanza(session, dice(lingua, "alias_fatto", nome=nome), [], None, True)
        if e_negativa(risposta, lingua):
            return self._avanza(session, dice(lingua, "alias_lascio"), [], None, True)
        # Un altro nome: si riparte da li', una volta sola, poi si rinuncia.
        if session["correzioni"] >= LIMITE_CORREZIONI:
            return self._avanza(session, dice(lingua, "alias_rinuncia"), [], None, True)
        session["correzioni"] += 1
        session["fase"] = "domanda"
        return self._chiedi_alias(session, step, risposta, archivio)
