# -*- coding: utf-8 -*-
import json
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.ollama_client import OllamaClient
from core.data_store import data_store
from core.user_manager import user_manager

logger = logging.getLogger("Shinra.Interview")

INTERVIEW_STEPS = [
    {
        "id": "casa_base",
        "category": "casa",
        "title": "Casa e Indirizzo",
        "question": "Perfetto! Iniziamo con la tua casa: in quale città o zona si trova, a che piano sei e quante stanze principali ci sono?",
        "hint": "es. Vivo ad Arezzo in un appartamento al secondo piano con salotto, cucina, due camere e studio."
    },
    {
        "id": "famiglia",
        "category": "famiglia",
        "title": "Membri della Famiglia",
        "question": "Chi vive con te in casa? Dimmi i loro nomi, le stanze in cui passano più tempo o eventuali ruoli.",
        "hint": "es. Vivo con mia moglie Sonia e i miei figli Thomas e Christian. Thomas sta spesso nella cameretta."
    },
    {
        "id": "mattina",
        "category": "abitudini",
        "title": "Risveglio e Mattina",
        "question": "Come inizia la tua tipica mattinata? A che ora ti svegli e quali dispositivi o luci vorresti accendere o controllare al risveglio?",
        "hint": "es. Mi sveglio alle 7:00, accendo la luce in cucina, vorrei sentire le notizie e accendere la macchina del caffè."
    },
    {
        "id": "notte",
        "category": "abitudini",
        "title": "Sera e Buonanotte",
        "question": "E la sera quando vai a dormire? C'è un orario tipico e cosa deve succedere in casa (spegnere tutto, abbassare le tapparelle, controllare il clima)?",
        "hint": "es. Vado a letto verso le 23:30, vorrei spegnere tutte le luci della casa e abbassare il termostato a 18 gradi."
    },
    {
        "id": "relax",
        "category": "abitudini",
        "title": "Relax e Svago",
        "question": "Quando ti rilassi a guardare un film o ad ascoltare musica, come ti piace impostare la stanza e le luci?",
        "hint": "es. Quando guardo un film mi piace abbassare le luci del salotto al 15% e accendere la presa della TV."
    },
    {
        "id": "tecnico",
        "category": "casa_tecnica",
        "title": "Dati Tecnici ed Emergenze",
        "question": "Infine, ci sono dettagli tecnici utili da ricordare? Come il nome della rete Wi-Fi per gli ospiti, dove si trova il contatore elettrico o un contatto importante?",
        "hint": "es. La rete ospiti è CasaMia_Guest, il contatore è nel sottoscala all'ingresso."
    }
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
            "started_at": datetime.now().isoformat()
        }
        self._active_sessions[user_id] = session
        first_step = INTERVIEW_STEPS[0]
        
        greeting = "Modalità Apprendimento attivata. Ti farò qualche breve domanda per imparare a gestire la tua casa al meglio. " + first_step["question"]
        return {
            "is_active": True,
            "step_index": 0,
            "step": first_step,
            "total_steps": len(INTERVIEW_STEPS),
            "message": greeting,
            "is_complete": False
        }

    async def process_answer(self, user_id: str, answer_text: str) -> Dict[str, Any]:
        session = self._active_sessions.get(user_id)
        if not session or not session.get("is_active", False):
            return self.start_session(user_id)

        step_idx = session["current_step_index"]
        current_step = INTERVIEW_STEPS[step_idx]

        # 1. Analisi ed estrazione automatica tramite LLM
        extracted_info = await self._extract_knowledge_and_routines(current_step, answer_text)
        
        # 2. Salvataggio immediato dei fatti nel data store
        new_facts = []
        for fact in extracted_info.get("facts", []):
            if fact.get("text"):
                saved = data_store.add_knowledge_item(
                    text=fact["text"],
                    category=fact.get("category") or current_step["category"]
                )
                new_facts.append(saved)
                session["learned_facts"].append(saved)

        # 3. Rilevamento di routine potenziali
        proposed_routine = extracted_info.get("proposed_routine")
        routine_proposal_text = ""
        if proposed_routine and proposed_routine.get("name"):
            session["proposed_routines"].append(proposed_routine)
            routine_proposal_text = f"\n\n💡 Ho notato una possibile routine: vuoi che crei l'automazione '{proposed_routine['name']}'?"

        session["answers"][current_step["id"]] = answer_text

        # 4. Avanzamento al prossimo step
        next_step_idx = step_idx + 1
        if next_step_idx < len(INTERVIEW_STEPS):
            session["current_step_index"] = next_step_idx
            next_step = INTERVIEW_STEPS[next_step_idx]
            
            ack = "Perfetto, ho memorizzato queste informazioni. "
            if new_facts:
                ack = f"Ricevuto! Ho aggiunto {len(new_facts)} nuovi dettagli alla mia conoscenza. "
            
            bot_msg = ack + next_step["question"] + routine_proposal_text
            return {
                "is_active": True,
                "step_index": next_step_idx,
                "step": next_step,
                "total_steps": len(INTERVIEW_STEPS),
                "message": bot_msg,
                "new_facts": new_facts,
                "proposed_routine": proposed_routine,
                "is_complete": False
            }
        else:
            session["is_active"] = False
            total_learned = len(session["learned_facts"])
            completion_msg = f"Ottimo lavoro! Intervista completata. Ho memorizzato {total_learned} fatti sulla tua casa e calibrato le mie risposte per te e la tua famiglia."
            return {
                "is_active": False,
                "step_index": next_step_idx,
                "total_steps": len(INTERVIEW_STEPS),
                "message": completion_msg,
                "new_facts": new_facts,
                "proposed_routine": proposed_routine,
                "is_complete": True,
                "summary": {
                    "total_facts": total_learned,
                    "proposed_routines": session["proposed_routines"]
                }
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

        try:
            raw = await self.ollama.generate(
                prompt=prompt,
                system="Rispondi solo con JSON valido. Non aggiungere markdown o spiegazioni.",
                temperature=0.1
            )
            clean_json = re.sub(r'```json\s*|\s*```', '', raw.strip())
            data = json.loads(clean_json)
            return data
        except Exception as e:
            logger.warning(f"Fallback estrazione per '{step['id']}': {e}")
            return {
                "facts": [{"text": user_answer.strip(), "category": step["category"]}],
                "proposed_routine": None
            }

    def confirm_routine(self, routine_data: Dict[str, Any]) -> Dict[str, Any]:
        if not routine_data or not routine_data.get("name"):
            return {"success": False, "error": "Nome routine mancante."}

        routine_id = routine_data.get("id") or "mode_" + re.sub(r'[^a-zA-Z0-9_]', '', routine_data["name"].lower().replace(' ', '_'))
        routine_data["id"] = routine_id
        routine_data["enabled"] = True
        if "icon" not in routine_data:
            routine_data["icon"] = "workflow"

        modes = data_store.get_modes()
        updated = False
        for i, m in enumerate(modes):
            if m.get("id") == routine_id:
                modes[i] = routine_data
                updated = True
                break
        if not updated:
            modes.append(routine_data)

        data_store.save_modes(modes)
        return {"success": True, "routine": routine_data}

    def stop_session(self, user_id: str) -> None:
        if user_id in self._active_sessions:
            self._active_sessions[user_id]["is_active"] = False

interview_engine = LearningInterviewEngine()
