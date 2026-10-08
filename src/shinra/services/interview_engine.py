# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from shinra.config import settings as impostazioni
from shinra.infra.data_store import data_store
from shinra.infra.llm.ollama import OllamaClient
from shinra.services.intervista_alias import TurniAlias, passo_alias
from shinra.services.intervista_comune import (
    FASE_CONFERMA,
    FASE_DOMANDA,
    LIMITE_CORREZIONI,
    dice,
    sezione,
)
from shinra.services.intervista_comune import (
    e_affermativa as _e_affermativa,
)
from shinra.services.intervista_comune import (
    e_negativa as _e_negativa,
)
from shinra.services.intervista_noto import cosa_si_sa, dati_della_casa
from shinra.services.intervista_passi import INTERVIEW_STEPS, passi_per
from shinra.services.intervista_routine import controlla_proposta, routine_da_salvare

logger = logging.getLogger("Shinra.Interview")

# Le frasi non sono qui: stanno nella sezione `intervista` del file della lingua di chi risponde (#207), e la
# lingua e' quella della sessione. Qui restano le regole: cosa si chiede, quando si insiste, quando si salva.
__all__ = ["INTERVIEW_STEPS", "LIMITE_CORREZIONI", "LearningInterviewEngine", "interview_engine"]
_USATI_DAI_TEST = (_e_affermativa, _e_negativa)


def _riconoscimento(interpretato: bool, quanti: int, lingua: str = "") -> str:
    """Cosa si risponde dopo una risposta dell'utente.

    Fino alla #170 qui c'era una frase sola — «Ricevuto! Ho aggiunto N nuovi
    dettagli» — e la diceva **anche quando il modello non aveva capito
    niente**, perche' il ripiego che conserva la frase grezza produce un fatto
    come tutti gli altri. Un guasto travestito da normalita'.

    Adesso i tre casi si dicono diversi, e quello che e' andato storto lo
    dice per primo: chi sta rispondendo deve poter smettere, invece di
    consegnare altre cinque risposte a qualcosa che non le sta leggendo.
    """
    if not interpretato:
        return dice(lingua, "riconoscimento_non_interpretato")
    if quanti:
        return dice(lingua, "riconoscimento_n", quanti=quanti)
    return dice(lingua, "riconoscimento_niente")


def _chiusura(imparati: int, non_interpretate: int, alias_creati: int = 0, lingua: str = "") -> str:
    """Il saluto finale, che non dice «ottimo lavoro» dopo sei fallimenti."""
    nomi = ""
    if alias_creati:
        nomi = dice(
            lingua, "chiusura_alias_uno" if alias_creati == 1 else "chiusura_alias_piu", n=alias_creati
        )
    if non_interpretate:
        return dice(lingua, "chiusura_errori", imparati=imparati, non_interpretate=non_interpretate) + nomi
    return dice(lingua, "chiusura_ok", imparati=imparati) + nomi


def _riepilogo(fatti: List[Dict[str, str]], lingua: str = "") -> str:
    """Cosa si e' capito, **prima** di salvarlo.

    Fino alla #170 l'intervista salvava e proseguiva: un'interpretazione
    sbagliata diventava conoscenza permanente in silenzio, e si scopriva mesi
    dopo da una risposta strana in cucina. Adesso passa da qui, mentre chi ha
    risposto ha ancora in mente cosa intendeva dire.
    """
    elenco = "\n".join(f"• {f['text']}" for f in fatti)
    return dice(lingua, "riepilogo", elenco=elenco)


def _insistenza(step: Dict[str, Any], interpretato: bool, lingua: str = "") -> str:
    """Si chiede di approfondire **una volta sola**, con un esempio concreto.

    Prima una risposta di due parole veniva accettata e si passava oltre: la
    domanda non tornava piu', e quel pezzo di casa restava ignoto per sempre.
    Si insiste una volta e basta, perche' un'intervista che non accetta un
    «boh» la si abbandona a meta' — e a quel punto non impara niente di
    niente.
    """
    apertura = dice(lingua, "insistenza_vuota" if interpretato else "insistenza_non_interpretato")
    esempio = re.sub(r"^(?:es\.|e\.g\.)\s*", "", str(step.get("hint") or ""), flags=re.IGNORECASE).strip()
    coda = dice(lingua, "per_esempio", esempio=esempio) if esempio else ""
    return dice(lingua, "insistenza", apertura=apertura, domanda=step["question"], esempio=coda)


def _primo_da_chiedere(partenza: int, passi: List[Dict[str, Any]], lingua: str = "") -> tuple:
    """Dal passo `partenza` in poi, il primo che la casa non sa gia'.

    Ritorna `(indice, saltati)`: `saltati` sono le frasi che dicono cosa si e'
    saltato e perche'. Se resta niente da chiedere, `indice` e' la lunghezza.
    """
    dati = dati_della_casa(data_store)
    saltati: List[str] = []
    indice = partenza
    while indice < len(passi):
        noto = cosa_si_sa(passi[indice], dati, lingua)
        if not noto:
            break
        saltati.append(noto)
        indice += 1
    return indice, saltati


def _frase_dei_saltati(saltati: List[str], lingua: str = "") -> str:
    if not saltati:
        return ""
    return " ".join(dice(lingua, "salto", noto=s) for s in saltati) + " "


class LearningInterviewEngine(TurniAlias):
    def __init__(self):
        self.ollama = OllamaClient()
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def is_session_active(self, user_id: str) -> bool:
        session = self._active_sessions.get(user_id)
        return bool(session and session.get("is_active", False))

    def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._active_sessions.get(user_id)

    def start_session(
        self,
        user_id: str = "alessio",
        dispositivi: Optional[List[Dict[str, Any]]] = None,
        lingua: str = "",
    ) -> Dict[str, Any]:
        """Apre l'intervista, nella lingua di chi risponde (vuota: quella dell'installazione)."""
        passi = passi_per(lingua) + [passo_alias(d, lingua) for d in dispositivi or []]
        session: Dict[str, Any] = {
            "passi": passi,
            "lingua": lingua,
            "user_id": user_id,
            "is_active": True,
            "current_step_index": 0,
            "total_steps": len(passi),
            "answers": {},
            "learned_facts": [],
            "proposed_routines": [],
            # Quante risposte il modello non e' riuscito a interpretare. Serve
            # a non chiudere l'intervista dicendo «ottimo lavoro» dopo sei
            # fallimenti di fila (#170).
            "non_interpretate": 0,
            # Dalla #170 un passo ha due fasi: si risponde, si guarda cosa ha
            # capito, si conferma. Qui sta a che punto e' il passo corrente.
            "fase": FASE_DOMANDA,
            "in_attesa": [],
            "routine_in_attesa": None,
            "insistito": False,
            "correzioni": 0,
            "started_at": datetime.now().isoformat(),
        }
        self._active_sessions[user_id] = session
        indice, saltati = _primo_da_chiedere(0, passi, lingua)
        if indice >= len(passi):
            session["is_active"] = False
            return {
                "is_active": False,
                "step_index": indice,
                "total_steps": len(session["passi"]),
                "fase": FASE_DOMANDA,
                "message": _frase_dei_saltati(saltati, lingua) + dice(lingua, "niente_da_chiedere"),
                "capiti": [],
                "suggerimento": None,
                "is_complete": True,
                "summary": {"total_facts": 0, "proposed_routines": []},
            }
        session["current_step_index"] = indice
        first_step = passi[indice]

        greeting = dice(lingua, "saluto") + _frase_dei_saltati(saltati, lingua) + first_step["question"]
        return {
            "is_active": True,
            "step_index": indice,
            "step": first_step,
            "total_steps": len(session["passi"]),
            "fase": FASE_DOMANDA,
            "message": greeting,
            "capiti": [],
            "suggerimento": None,
            "is_complete": False,
        }

    async def process_answer(self, user_id: str, answer_text: str) -> Dict[str, Any]:
        session = self._active_sessions.get(user_id)
        if not session or not session.get("is_active", False):
            return self.start_session(user_id)

        current_step = session["passi"][session["current_step_index"]]
        if current_step.get("kind") == "alias":
            return self._turno_alias(session, current_step, answer_text, data_store)
        if session.get("fase") == FASE_CONFERMA:
            return await self._turno_conferma(session, current_step, answer_text)
        return await self._turno_domanda(session, current_step, answer_text)

    async def _turno_domanda(
        self, session: Dict[str, Any], step: Dict[str, Any], answer_text: str
    ) -> Dict[str, Any]:
        """La risposta alla domanda del passo. Non salva ancora niente."""
        lingua = session.get("lingua", "")
        session["answers"][step["id"]] = answer_text
        estratto = await self._extract_knowledge_and_routines(step, answer_text, lingua)
        interpretato = bool(estratto.get("interpretato", True))
        fatti = estratto.get("facts") or []
        routine = estratto.get("proposed_routine")

        # Una risposta da cui non e' uscito niente — perche' era povera o
        # perche' il modello non l'ha interpretata. Si chiede una volta sola.
        if (not interpretato or not fatti) and not session["insistito"]:
            session["insistito"] = True
            return self._stesso_passo(session, step, _insistenza(step, interpretato, lingua), interpretato)

        if not interpretato:
            # La frase e' rimasta grezza: e' gia' sua parola per parola, e
            # chiedergli «ho capito questo, e' giusto?» ripetendogli cio' che
            # ha appena scritto sarebbe una presa in giro. Si salva e si dice
            # che non si e' capito.
            session["non_interpretate"] += 1
            salvati = self._salva(session, step, fatti)
            return self._avanza(
                session, _riconoscimento(False, len(salvati), lingua), salvati, routine, False
            )

        if not fatti:
            return self._avanza(session, _riconoscimento(True, 0, lingua), [], routine, True)

        return self._chiedi_conferma(session, step, fatti, routine)

    async def _turno_conferma(
        self, session: Dict[str, Any], step: Dict[str, Any], answer_text: str
    ) -> Dict[str, Any]:
        """La risposta al riepilogo: un «sì», un «no», o una correzione."""
        lingua = session.get("lingua", "")
        if _e_affermativa(answer_text, lingua):
            salvati = self._salva(session, step, session.get("in_attesa") or [])
            return self._avanza(
                session,
                _riconoscimento(True, len(salvati), lingua),
                salvati,
                session.get("routine_in_attesa"),
                True,
            )

        if _e_negativa(answer_text, lingua):
            return self._avanza(session, dice(lingua, "non_salvo"), [], None, True)

        # Tutto il resto e' una correzione: si riparte da cio' che ha scritto
        # lui adesso, non da cio' che si era capito prima.
        ancora = session["correzioni"] < LIMITE_CORREZIONI
        session["correzioni"] += 1
        session["answers"][step["id"]] = answer_text

        estratto = await self._extract_knowledge_and_routines(step, answer_text, lingua)
        interpretato = bool(estratto.get("interpretato", True))
        fatti = estratto.get("facts") or []
        routine = estratto.get("proposed_routine")

        if interpretato and fatti and ancora:
            return self._chiedi_conferma(session, step, fatti, routine)

        if not interpretato:
            session["non_interpretate"] += 1
        salvati = self._salva(session, step, fatti)
        prefisso = (
            dice(lingua, "salvo_cosi")
            if salvati and not ancora
            else _riconoscimento(interpretato, len(salvati), lingua)
        )
        return self._avanza(session, prefisso, salvati, routine, interpretato)

    def _chiedi_conferma(
        self,
        session: Dict[str, Any],
        step: Dict[str, Any],
        fatti: List[Dict[str, str]],
        routine: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        lingua = session.get("lingua", "")
        session["fase"] = FASE_CONFERMA
        session["in_attesa"] = fatti
        session["routine_in_attesa"] = routine
        return self._stesso_passo(
            session,
            step,
            _riepilogo(fatti, lingua),
            True,
            capiti=fatti,
            suggerimento=dice(lingua, "suggerimento_conferma"),
        )

    def _salva(
        self, session: Dict[str, Any], step: Dict[str, Any], fatti: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        salvati: List[Dict[str, Any]] = []
        for fatto in fatti:
            if not fatto.get("text"):
                continue
            try:
                riga = data_store.add_knowledge_item(
                    text=fatto["text"], category=fatto.get("category") or step["category"]
                )
            except (OSError, ValueError) as e:
                # Un fatto che non si riesce a salvare non deve interrompere
                # l'intervista: era proprio questo il difetto BLK-01, dove
                # l'errore arrivava fino all'utente come un 500.
                logger.error("Fatto non salvato (%s): %s", fatto.get("text", "")[:60], e)
                continue
            salvati.append(riga)
            session["learned_facts"].append(riga)
        return salvati

    @staticmethod
    def _stesso_passo(
        session: Dict[str, Any],
        step: Dict[str, Any],
        messaggio: str,
        interpretato: bool,
        capiti: Optional[List[Dict[str, str]]] = None,
        suggerimento: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Si resta sulla stessa domanda: non si e' ancora salvato niente."""
        return {
            "is_active": True,
            "step_index": session["current_step_index"],
            "step": step,
            "total_steps": len(session["passi"]),
            "fase": session["fase"],
            "message": messaggio,
            "new_facts": [],
            "capiti": capiti or [],
            "suggerimento": suggerimento,
            "proposed_routine": None,
            "interpretato": interpretato,
            "is_complete": False,
        }

    def _avanza(
        self,
        session: Dict[str, Any],
        prefisso: str,
        salvati: List[Dict[str, Any]],
        routine: Optional[Dict[str, Any]],
        interpretato: bool,
    ) -> Dict[str, Any]:
        """Il passo e' chiuso: si azzera il suo stato e si va al successivo."""
        lingua = session.get("lingua", "")
        session["fase"] = FASE_DOMANDA
        session["in_attesa"] = []
        session["routine_in_attesa"] = None
        session["insistito"] = False
        session["correzioni"] = 0

        proposta = ""
        if routine and routine.get("name"):
            session["proposed_routines"].append(routine)
            scartate = (
                dice(lingua, "routine_scartate", elenco="; ".join(routine["scartate"]))
                if routine.get("scartate")
                else ""
            )
            proposta = dice(
                lingua,
                "routine_proposta",
                nome=routine["name"],
                anteprima=routine.get("anteprima", ""),
                prova=routine.get("prova", dice(lingua, "routine_prova_non_fatta")),
                scartate=scartate,
            )

        prossimo, saltati = _primo_da_chiedere(session["current_step_index"] + 1, session["passi"], lingua)
        prefisso += _frase_dei_saltati(saltati, lingua)
        if prossimo < len(session["passi"]):
            session["current_step_index"] = prossimo
            passo = session["passi"][prossimo]
            return {
                "is_active": True,
                "step_index": prossimo,
                "step": passo,
                "total_steps": len(session["passi"]),
                "fase": FASE_DOMANDA,
                "message": prefisso + passo["question"] + proposta,
                "new_facts": salvati,
                "capiti": [],
                "suggerimento": None,
                "proposed_routine": routine,
                "interpretato": interpretato,
                "is_complete": False,
            }

        session["is_active"] = False
        imparati = len(session["learned_facts"])
        return {
            "is_active": False,
            "step_index": prossimo,
            "total_steps": len(session["passi"]),
            "fase": FASE_DOMANDA,
            "message": prefisso
            + _chiusura(imparati, session["non_interpretate"], session.get("alias_creati", 0), lingua),
            "new_facts": salvati,
            "capiti": [],
            "suggerimento": None,
            "proposed_routine": routine,
            "interpretato": interpretato,
            "is_complete": True,
            "summary": {"total_facts": imparati, "proposed_routines": session["proposed_routines"]},
        }

    async def _extract_knowledge_and_routines(
        self, step: Dict[str, Any], user_answer: str, lingua: str = ""
    ) -> Dict[str, Any]:
        if not user_answer or len(user_answer.strip()) < 3:
            return {"facts": [], "proposed_routine": None}

        # Il prompt e' nella lingua di chi risponde: un modello a cui si parla in inglese risponde meglio
        # se anche le istruzioni lo sono, e i fatti che estrae restano nella lingua della persona.
        intervista = sezione(lingua)
        prompt = intervista["prompt_estrazione"].format(
            titolo=step["title"], categoria=step["category"], domanda=step["question"], risposta=user_answer
        )

        dati = await self.ollama.genera_json(
            prompt=prompt,
            system=intervista["sistema_estrazione"],
            temperature=0.1,
        )

        if dati is None:
            # Ollama spento, o risposta inutilizzabile. Si conserva comunque
            # cio' che l'utente ha detto: perdere la sua risposta sarebbe
            # peggio che conservarla non elaborata.
            #
            # Ma **si dichiara**. Fino alla #170 questo ripiego restituiva un
            # fatto come tutti gli altri, e l'intervista rispondeva «Ricevuto!
            # Ho aggiunto 1 nuovi dettagli alla mia conoscenza»: falliva e
            # rassicurava. In casa, con un modello da un miliardo di
            # parametri, e' successo per sei domande di fila senza che niente
            # lo dicesse — e chi stava rispondendo ha creduto per tutto il
            # tempo che la casa stesse imparando.
            logger.warning(
                "Estrazione non riuscita per '%s' con il modello «%s»: conservo la "
                "risposta cosi' com'e'. Un modello che non produce JSON strutturato "
                "non puo' imparare niente da un'intervista.",
                step["id"],
                impostazioni.settings.llm.model,
            )
            return {
                "facts": [{"text": user_answer.strip(), "category": step["category"]}],
                "proposed_routine": None,
                "interpretato": False,
            }

        return {
            "facts": self._fatti_validi(dati.get("facts"), step),
            "proposed_routine": await controlla_proposta(
                self._routine_valida(dati.get("proposed_routine")), data_store, lingua
            ),
            "interpretato": True,
        }

    @staticmethod
    def _fatti_validi(grezzi: Any, step: Dict[str, Any]) -> List[Dict[str, str]]:
        """Tiene solo i fatti utilizzabili.

        Un modello piccolo restituisce spesso stringhe al posto di oggetti, o
        campi vuoti: senza questo filtro finirebbero nella conoscenza della
        casa, e da li' nel prompt di ogni risposta.
        """
        if not isinstance(grezzi, list):
            return []
        puliti: List[Dict[str, str]] = []
        for voce in grezzi:
            if isinstance(voce, str):
                testo, categoria = voce.strip(), step["category"]
            elif isinstance(voce, dict):
                testo = str(voce.get("text") or "").strip()
                categoria = str(voce.get("category") or step["category"]).strip()
            else:
                continue
            if len(testo) < 3:
                continue
            puliti.append({"text": testo, "category": categoria or step["category"]})
        return puliti

    @staticmethod
    def _routine_valida(grezza: Any) -> Optional[Dict[str, Any]]:
        """Una routine senza nome o senza azioni non e' proponibile."""
        if not isinstance(grezza, dict):
            return None
        nome = str(grezza.get("name") or "").strip()
        if not nome:
            return None
        azioni = grezza.get("actions")
        grezza["name"] = nome
        grezza["actions"] = azioni if isinstance(azioni, list) else []
        frasi = grezza.get("trigger_phrases")
        grezza["trigger_phrases"] = (
            [str(f).strip() for f in frasi if str(f).strip()] if isinstance(frasi, list) else []
        )
        return grezza

    async def conferma_routine_proposta(self, proposta: Dict[str, Any], lingua: str = "") -> Dict[str, Any]:
        """Salva la routine proposta, dopo averla ricontrollata (vedi `intervista_routine`)."""
        pulita = await routine_da_salvare(proposta, data_store, lingua)
        if pulita is None:
            return {"success": False, "error": dice(lingua, "routine_non_supera")}
        return self.confirm_routine(pulita)

    def confirm_routine(self, routine_data: Dict[str, Any]) -> Dict[str, Any]:
        if not routine_data or not routine_data.get("name"):
            return {"success": False, "error": "Nome routine mancante."}

        routine_id = routine_data.get("id") or "mode_" + re.sub(
            r"[^a-zA-Z0-9_]", "", routine_data["name"].lower().replace(" ", "_")
        )
        routine_data["id"] = routine_id
        routine_data["enabled"] = True
        if "icon" not in routine_data:
            routine_data["icon"] = "workflow"

        salvata = data_store.salva_modalita(routine_data)
        return {"success": True, "routine": salvata}

    def stop_session(self, user_id: str) -> None:
        if user_id in self._active_sessions:
            self._active_sessions[user_id]["is_active"] = False


interview_engine = LearningInterviewEngine()
