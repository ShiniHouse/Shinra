# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from shinra.config import settings as impostazioni
from shinra.infra.data_store import data_store
from shinra.infra.llm.ollama import OllamaClient

logger = logging.getLogger("Shinra.Interview")


def _riconoscimento(interpretato: bool, quanti: int) -> str:
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
        return (
            "Ho conservato la tua risposta, ma non sono riuscita a ricavarne niente "
            "di preciso: il modello non ha risposto come mi serve. Controlla quale "
            "modello e' configurato — per capire una frase e riassumerla ne serve "
            "uno da qualche miliardo di parametri. Intanto proseguo. "
        )
    if quanti:
        return f"Ricevuto! Ho aggiunto {quanti} nuovi dettagli alla mia conoscenza. "
    return (
        "Ho letto, ma da questa risposta non ho ricavato niente da ricordare: "
        "se ti va, piu' avanti riprendiamo con qualche dettaglio in piu'. "
    )


def _chiusura(imparati: int, non_interpretate: int) -> str:
    """Il saluto finale, che non dice «ottimo lavoro» dopo sei fallimenti."""
    if non_interpretate:
        return (
            f"Intervista finita. Ho memorizzato {imparati} fatti, ma {non_interpretate} "
            "delle tue risposte non sono riuscita a interpretarle: le ho conservate "
            "cosi' come le hai scritte. Con un modello piu' capace vale la pena "
            "rifarla — imparerei molto di piu' dalle stesse risposte."
        )
    return (
        f"Ottimo lavoro! Intervista completata. Ho memorizzato {imparati} fatti sulla "
        "tua casa e calibrato le mie risposte per te e la tua famiglia."
    )


# Le due fasi di un passo. Fino alla #170 ce n'era una sola: si rispondeva e
# l'intervista salvava. Adesso in mezzo c'e' la conferma.
FASE_DOMANDA = "domanda"
FASE_CONFERMA = "conferma"

# Quante volte si accetta una correzione prima di salvare e proseguire. Senza
# un limite, chi risponde con una frase che il modello continua a masticare
# male resta fermo sullo stesso passo per sempre: ogni testo libero e' una
# correzione, e ogni correzione riapre la conferma.
LIMITE_CORREZIONI = 1

AFFERMAZIONI = frozenset(
    {
        "si",
        "sì",
        "s",
        "ok",
        "okay",
        "va bene",
        "vabene",
        "giusto",
        "esatto",
        "esattamente",
        "corretto",
        "perfetto",
        "certo",
        "confermo",
        "conferma",
        "yes",
        "y",
        "tutto giusto",
        "e giusto",
        "è giusto",
        "sì esatto",
        "si esatto",
    }
)

NEGAZIONI = frozenset(
    {
        "no",
        "n",
        "nope",
        "sbagliato",
        "niente",
        "annulla",
        "salta",
        "lascia perdere",
        "no grazie",
        "non e giusto",
        "non è giusto",
    }
)

SUGGERIMENTO_CONFERMA = (
    "Rispondi «sì» per salvare, «no» per saltare, oppure riscrivi la frase come la diresti tu."
)


def _normalizza(testo: str) -> str:
    """Toglie punteggiatura e maiuscole, per leggere «Sì!» come «si».

    Si conservano le lettere accentate: in italiano «e» e «è» non sono la
    stessa parola, e «no» non deve diventare un «n» che vale come «n» secco.
    """
    solo_lettere = re.sub(r"[^a-zà-ÿ]+", " ", (testo or "").lower())
    return re.sub(r"\s+", " ", solo_lettere).strip()


def _e_affermativa(testo: str) -> bool:
    return _normalizza(testo) in AFFERMAZIONI


def _e_negativa(testo: str) -> bool:
    return _normalizza(testo) in NEGAZIONI


def _riepilogo(fatti: List[Dict[str, str]]) -> str:
    """Cosa si e' capito, **prima** di salvarlo.

    Fino alla #170 l'intervista salvava e proseguiva: un'interpretazione
    sbagliata diventava conoscenza permanente in silenzio, e si scopriva mesi
    dopo da una risposta strana in cucina. Adesso passa da qui, mentre chi ha
    risposto ha ancora in mente cosa intendeva dire.
    """
    elenco = "\n".join(f"• {f['text']}" for f in fatti)
    return (
        "Ho capito questo:\n"
        f"{elenco}\n"
        "È giusto? Rispondi «sì» e lo salvo. Se ho capito male, riscrivimelo come lo "
        "diresti tu; se preferisci lasciar perdere, rispondi «no»."
    )


def _insistenza(step: Dict[str, Any], interpretato: bool) -> str:
    """Si chiede di approfondire **una volta sola**, con un esempio concreto.

    Prima una risposta di due parole veniva accettata e si passava oltre: la
    domanda non tornava piu', e quel pezzo di casa restava ignoto per sempre.
    Si insiste una volta e basta, perche' un'intervista che non accetta un
    «boh» la si abbandona a meta' — e a quel punto non impara niente di
    niente.
    """
    apertura = (
        "Non sono riuscita a ricavarne niente di preciso."
        if not interpretato
        else "Da questa risposta non ho ricavato niente da ricordare."
    )
    esempio = re.sub(r"^es\.\s*", "", str(step.get("hint") or "")).strip()
    coda = f"\nPer esempio: «{esempio}»" if esempio else ""
    return f"{apertura} Ci riprovo una volta sola, poi passo oltre.\n{step['question']}{coda}"


INTERVIEW_STEPS = [
    {
        "id": "casa_base",
        "category": "casa",
        "title": "Casa e Indirizzo",
        "question": "Perfetto! Iniziamo con la tua casa: in quale città o zona si trova, a che piano sei e quante stanze principali ci sono?",
        "hint": "es. Vivo ad Arezzo in un appartamento al secondo piano con salotto, cucina, due camere e studio.",
    },
    {
        "id": "famiglia",
        "category": "famiglia",
        "title": "Membri della Famiglia",
        "question": "Chi vive con te in casa? Dimmi i loro nomi, le stanze in cui passano più tempo o eventuali ruoli.",
        "hint": "es. Vivo con mia moglie Sonia e i miei figli Thomas e Christian. Thomas sta spesso nella cameretta.",
    },
    {
        "id": "mattina",
        "category": "abitudini",
        "title": "Risveglio e Mattina",
        "question": "Come inizia la tua tipica mattinata? A che ora ti svegli e quali dispositivi o luci vorresti accendere o controllare al risveglio?",
        "hint": "es. Mi sveglio alle 7:00, accendo la luce in cucina, vorrei sentire le notizie e accendere la macchina del caffè.",
    },
    {
        "id": "notte",
        "category": "abitudini",
        "title": "Sera e Buonanotte",
        "question": "E la sera quando vai a dormire? C'è un orario tipico e cosa deve succedere in casa (spegnere tutto, abbassare le tapparelle, controllare il clima)?",
        "hint": "es. Vado a letto verso le 23:30, vorrei spegnere tutte le luci della casa e abbassare il termostato a 18 gradi.",
    },
    {
        "id": "relax",
        "category": "abitudini",
        "title": "Relax e Svago",
        "question": "Quando ti rilassi a guardare un film o ad ascoltare musica, come ti piace impostare la stanza e le luci?",
        "hint": "es. Quando guardo un film mi piace abbassare le luci del salotto al 15% e accendere la presa della TV.",
    },
    {
        "id": "tecnico",
        "category": "casa_tecnica",
        "title": "Dati Tecnici ed Emergenze",
        "question": "Infine, ci sono dettagli tecnici utili da ricordare? Come il nome della rete Wi-Fi per gli ospiti, dove si trova il contatore elettrico o un contatto importante?",
        "hint": "es. La rete ospiti è CasaMia_Guest, il contatore è nel sottoscala all'ingresso.",
    },
]


class LearningInterviewEngine:
    def __init__(self):
        self.ollama = OllamaClient()
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def is_session_active(self, user_id: str) -> bool:
        session = self._active_sessions.get(user_id)
        return bool(session and session.get("is_active", False))

    def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._active_sessions.get(user_id)

    def start_session(self, user_id: str = "alessio") -> Dict[str, Any]:
        session = {
            "user_id": user_id,
            "is_active": True,
            "current_step_index": 0,
            "total_steps": len(INTERVIEW_STEPS),
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
        first_step = INTERVIEW_STEPS[0]

        greeting = (
            "Modalità Apprendimento attivata. Ti farò qualche breve domanda per imparare a gestire la tua casa al meglio. "
            + first_step["question"]
        )
        return {
            "is_active": True,
            "step_index": 0,
            "step": first_step,
            "total_steps": len(INTERVIEW_STEPS),
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

        current_step = INTERVIEW_STEPS[session["current_step_index"]]
        if session.get("fase") == FASE_CONFERMA:
            return await self._turno_conferma(session, current_step, answer_text)
        return await self._turno_domanda(session, current_step, answer_text)

    async def _turno_domanda(
        self, session: Dict[str, Any], step: Dict[str, Any], answer_text: str
    ) -> Dict[str, Any]:
        """La risposta alla domanda del passo. Non salva ancora niente."""
        session["answers"][step["id"]] = answer_text
        estratto = await self._extract_knowledge_and_routines(step, answer_text)
        interpretato = bool(estratto.get("interpretato", True))
        fatti = estratto.get("facts") or []
        routine = estratto.get("proposed_routine")

        # Una risposta da cui non e' uscito niente — perche' era povera o
        # perche' il modello non l'ha interpretata. Si chiede una volta sola.
        if (not interpretato or not fatti) and not session["insistito"]:
            session["insistito"] = True
            return self._stesso_passo(session, step, _insistenza(step, interpretato), interpretato)

        if not interpretato:
            # La frase e' rimasta grezza: e' gia' sua parola per parola, e
            # chiedergli «ho capito questo, e' giusto?» ripetendogli cio' che
            # ha appena scritto sarebbe una presa in giro. Si salva e si dice
            # che non si e' capito.
            session["non_interpretate"] += 1
            salvati = self._salva(session, step, fatti)
            return self._avanza(session, _riconoscimento(False, len(salvati)), salvati, routine, False)

        if not fatti:
            return self._avanza(session, _riconoscimento(True, 0), [], routine, True)

        return self._chiedi_conferma(session, step, fatti, routine)

    async def _turno_conferma(
        self, session: Dict[str, Any], step: Dict[str, Any], answer_text: str
    ) -> Dict[str, Any]:
        """La risposta al riepilogo: un «sì», un «no», o una correzione."""
        if _e_affermativa(answer_text):
            salvati = self._salva(session, step, session.get("in_attesa") or [])
            return self._avanza(
                session,
                _riconoscimento(True, len(salvati)),
                salvati,
                session.get("routine_in_attesa"),
                True,
            )

        if _e_negativa(answer_text):
            return self._avanza(session, "Va bene, non salvo niente di questo passo. ", [], None, True)

        # Tutto il resto e' una correzione: si riparte da cio' che ha scritto
        # lui adesso, non da cio' che si era capito prima.
        ancora = session["correzioni"] < LIMITE_CORREZIONI
        session["correzioni"] += 1
        session["answers"][step["id"]] = answer_text

        estratto = await self._extract_knowledge_and_routines(step, answer_text)
        interpretato = bool(estratto.get("interpretato", True))
        fatti = estratto.get("facts") or []
        routine = estratto.get("proposed_routine")

        if interpretato and fatti and ancora:
            return self._chiedi_conferma(session, step, fatti, routine)

        if not interpretato:
            session["non_interpretate"] += 1
        salvati = self._salva(session, step, fatti)
        prefisso = (
            "Salvo così e proseguo, per non farti riscrivere all'infinito. "
            if salvati and not ancora
            else _riconoscimento(interpretato, len(salvati))
        )
        return self._avanza(session, prefisso, salvati, routine, interpretato)

    def _chiedi_conferma(
        self,
        session: Dict[str, Any],
        step: Dict[str, Any],
        fatti: List[Dict[str, str]],
        routine: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        session["fase"] = FASE_CONFERMA
        session["in_attesa"] = fatti
        session["routine_in_attesa"] = routine
        return self._stesso_passo(
            session,
            step,
            _riepilogo(fatti),
            True,
            capiti=fatti,
            suggerimento=SUGGERIMENTO_CONFERMA,
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
            "total_steps": len(INTERVIEW_STEPS),
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
        session["fase"] = FASE_DOMANDA
        session["in_attesa"] = []
        session["routine_in_attesa"] = None
        session["insistito"] = False
        session["correzioni"] = 0

        proposta = ""
        if routine and routine.get("name"):
            session["proposed_routines"].append(routine)
            proposta = (
                f"\n\n💡 Ho notato una possibile routine: vuoi che crei l'automazione '{routine['name']}'?"
            )

        prossimo = session["current_step_index"] + 1
        if prossimo < len(INTERVIEW_STEPS):
            session["current_step_index"] = prossimo
            passo = INTERVIEW_STEPS[prossimo]
            return {
                "is_active": True,
                "step_index": prossimo,
                "step": passo,
                "total_steps": len(INTERVIEW_STEPS),
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
            "total_steps": len(INTERVIEW_STEPS),
            "fase": FASE_DOMANDA,
            "message": _chiusura(imparati, session["non_interpretate"]),
            "new_facts": salvati,
            "capiti": [],
            "suggerimento": None,
            "proposed_routine": routine,
            "interpretato": interpretato,
            "is_complete": True,
            "summary": {"total_facts": imparati, "proposed_routines": session["proposed_routines"]},
        }

    async def _extract_knowledge_and_routines(self, step: Dict[str, Any], user_answer: str) -> Dict[str, Any]:
        if not user_answer or len(user_answer.strip()) < 3:
            return {"facts": [], "proposed_routine": None}

        prompt = f"""Sei l'assistente IA Shinra. Analizza la risposta dell'utente durante un'intervista ed estrai le informazioni da memorizzare.

Argomento: {step['title']} (Categoria: {step['category']})
Domanda: "{step['question']}"
Risposta: "{user_answer}"

Estrai:
1. Una lista di 'facts' atomici e chiari in forma di frasi descrittive in terza persona (es. "La sveglia nei feriali è alle ore 7:00").
2. Se l'utente ha descritto una sequenza di azioni o abitudini, crea un oggetto 'proposed_routine' con 'name', 'description', 'trigger_phrases' e una lista 'actions' (con type 'ha_device', 'tts' o 'delay'). Altrimenti metti null.

Rispondi ESCLUSIVAMENTE con un JSON:
{{
  "facts": [
    {{"text": "Frase descrittiva 1", "category": "{step['category']}"}}
  ],
  "proposed_routine": null
}}"""

        dati = await self.ollama.genera_json(
            prompt=prompt,
            system="Rispondi solo con JSON valido. Non aggiungere markdown o spiegazioni.",
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
            "proposed_routine": self._routine_valida(dati.get("proposed_routine")),
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
