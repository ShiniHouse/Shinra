# -*- coding: utf-8 -*-
"""Una conferma per gruppo di domande, invece di una per risposta.

Provando l'intervista in casa (2026-10-11): «poco fluida». Dopo ogni risposta Shinra mostrava «Ho capito questo, e'
giusto?» e aspettava un «si'»: tredici domande diventavano ventisei turni. Quella conferma esiste per una ragione seria
(#170): un'interpretazione sbagliata non deve diventare conoscenza permanente in silenzio. Qui la ragione resta e il
costo scende: le risposte di uno stesso argomento (la casa, la famiglia, le abitudini, i dati tecnici) si **raccolgono**
senza salvare niente, e **alla fine del gruppo** si mostra un riepilogo unico. Niente entra nel database senza il «si'».

Nel riepilogo si puo':
 - dire «si'»: si salva tutto;
 - dire «no»: si scarta tutto il gruppo;
 - dire «togli 2»: si toglie la voce 2 (e si rimostra il riepilogo);
 - riscrivere l'ultima risposta: si rilegge e sostituisce quella.

Si puo' tornare alla conferma dopo ogni risposta con `assistant.intervista_conferma: risposta`.
"""

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from shinra.config import settings as impostazioni
from shinra.services.intervista_comune import (
    FASE_CONFERMA,
    LIMITE_CORREZIONI,
    dice,
    e_affermativa,
    e_negativa,
    sezione,
)


def a_gruppi() -> bool:
    """Si confermano i gruppi (predefinito) o ogni singola risposta?"""
    return impostazioni.settings.assistant.intervista_conferma != "risposta"


def numero_da_togliere(testo: str, lingua: str = "") -> Optional[int]:
    """«togli 2», «no 3», «remove 1»: il numero della voce da togliere, o `None`."""
    parole = "|".join(re.escape(p) for p in sezione(lingua)["togli"])
    trovato = re.match(
        rf"^\s*(?:{parole})\s*(?:n\.?|numero|#)?\s*(\d+)\s*[.!]?\s*$", testo or "", re.IGNORECASE
    )
    return int(trovato.group(1)) if trovato else None


class TurniGruppo:
    """I turni del riepilogo di gruppo, per il motore dell'intervista (mixin)."""

    if TYPE_CHECKING:
        # Li definisce il motore: qui servono solo a mypy.
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

        def _salva(
            self, session: Dict[str, Any], step: Dict[str, Any], fatti: List[Dict[str, str]]
        ) -> List[Dict[str, Any]]: ...

        def _prossimo_da_chiedere(self, session: Dict[str, Any]) -> int: ...

        async def _extract_knowledge_and_routines(
            self, step: Dict[str, Any], user_answer: str, lingua: str = ""
        ) -> Dict[str, Any]: ...

    # ------------------------------------------------------------ raccogliere

    def _finisce_il_gruppo(self, session: Dict[str, Any], step: Dict[str, Any]) -> bool:
        """Dopo questo passo si cambia argomento, o si finisce?"""
        prossimo = self._prossimo_da_chiedere(session)
        passi = session["passi"]
        if prossimo >= len(passi):
            return True
        altro = passi[prossimo]
        return altro.get("kind") == "alias" or altro["category"] != step["category"]

    def _accumula(
        self,
        session: Dict[str, Any],
        step: Dict[str, Any],
        fatti: List[Dict[str, str]],
        routine: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Tiene la risposta in attesa. Se il gruppo e' finito mostra il riepilogo, altrimenti va avanti."""
        lingua = session.get("lingua", "")
        gruppo = session["gruppo"]
        gruppo[:] = [v for v in gruppo if v["step"]["id"] != step["id"]] + [{"step": step, "fatti": fatti}]
        if routine:
            session["routine_gruppo"] = routine
        if self._finisce_il_gruppo(session, step):
            return self._chiedi_conferma_gruppo(session, step)
        prefisso = dice(lingua, "raccolgo") if len(gruppo) == 1 else ""
        return self._avanza(session, prefisso, [], None, True)

    def _chiudi_o_prosegui(
        self,
        session: Dict[str, Any],
        step: Dict[str, Any],
        prefisso: str,
        salvati: List[Dict[str, Any]],
        routine: Optional[Dict[str, Any]],
        interpretato: bool,
    ) -> Dict[str, Any]:
        """Una risposta che non da' niente da confermare: se chiude un gruppo con cose in attesa, le si mostra."""
        if a_gruppi() and session["gruppo"] and self._finisce_il_gruppo(session, step):
            esito = self._chiedi_conferma_gruppo(session, step, prefisso)
            esito["new_facts"] = salvati
            return esito
        return self._avanza(session, prefisso, salvati, routine, interpretato)

    # ------------------------------------------------------------ riepilogo

    @staticmethod
    def _voci(session: Dict[str, Any]) -> List[Dict[str, str]]:
        return [f for v in session["gruppo"] for f in v["fatti"]]

    def _chiedi_conferma_gruppo(
        self, session: Dict[str, Any], step: Dict[str, Any], prefisso: str = ""
    ) -> Dict[str, Any]:
        lingua = session.get("lingua", "")
        voci = self._voci(session)
        elenco = "\n".join(f"{i}. {f['text']}" for i, f in enumerate(voci, start=1))
        session["fase"] = FASE_CONFERMA
        session["in_attesa"] = voci
        return self._stesso_passo(
            session,
            step,
            prefisso + dice(lingua, "riepilogo_gruppo", elenco=elenco),
            True,
            capiti=voci,
            suggerimento=dice(lingua, "suggerimento_gruppo"),
        )

    async def _turno_conferma_gruppo(
        self, session: Dict[str, Any], step: Dict[str, Any], answer_text: str
    ) -> Dict[str, Any]:
        """La risposta al riepilogo di gruppo: si', no, «togli N», o la riscrittura dell'ultima risposta."""
        lingua = session.get("lingua", "")

        if e_affermativa(answer_text, lingua):
            salvati: List[Dict[str, Any]] = []
            for voce in session["gruppo"]:
                salvati += self._salva(session, voce["step"], voce["fatti"])
            routine = session.get("routine_gruppo")
            self._azzera_gruppo(session)
            return self._avanza(
                session, dice(lingua, "riconoscimento_n", quanti=len(salvati)), salvati, routine, True
            )

        if e_negativa(answer_text, lingua):
            self._azzera_gruppo(session)
            return self._avanza(session, dice(lingua, "non_salvo_gruppo"), [], None, True)

        numero = numero_da_togliere(answer_text, lingua)
        if numero is not None:
            return self._togli(session, step, numero)

        # Tutto il resto riscrive l'ultima risposta: si rilegge e sostituisce quella.
        ancora = session["correzioni"] < LIMITE_CORREZIONI
        session["correzioni"] += 1
        ultima = session["gruppo"][-1]["step"]
        session["answers"][ultima["id"]] = answer_text
        estratto = await self._extract_knowledge_and_routines(ultima, answer_text, lingua)
        interpretato = bool(estratto.get("interpretato", True))
        fatti = estratto.get("facts") or []
        if interpretato and fatti:
            session["gruppo"][-1]["fatti"] = fatti
            if estratto.get("proposed_routine"):
                session["routine_gruppo"] = estratto["proposed_routine"]
            if ancora:
                return self._chiedi_conferma_gruppo(session, step)
        elif not interpretato:
            session["non_interpretate"] += 1
        # Un'altra correzione oltre il limite: si salva com'e', per non far riscrivere all'infinito.
        salvati = []
        for voce in session["gruppo"]:
            salvati += self._salva(session, voce["step"], voce["fatti"])
        routine = session.get("routine_gruppo")
        self._azzera_gruppo(session)
        return self._avanza(session, dice(lingua, "salvo_cosi"), salvati, routine, interpretato)

    def _togli(self, session: Dict[str, Any], step: Dict[str, Any], numero: int) -> Dict[str, Any]:
        lingua = session.get("lingua", "")
        indice = 0
        for voce in session["gruppo"]:
            for posizione, fatto in enumerate(voce["fatti"]):
                indice += 1
                if indice == numero:
                    del voce["fatti"][posizione]
                    if not self._voci(session):
                        self._azzera_gruppo(session)
                        return self._avanza(session, dice(lingua, "non_salvo_gruppo"), [], None, True)
                    return self._chiedi_conferma_gruppo(
                        session, step, dice(lingua, "tolto", testo=fatto["text"]) + "\n"
                    )
        # Un numero che non c'e': si rimostra il riepilogo, senza togliere niente.
        return self._chiedi_conferma_gruppo(session, step)

    @staticmethod
    def _azzera_gruppo(session: Dict[str, Any]) -> None:
        session["gruppo"].clear()
        session["routine_gruppo"] = None
