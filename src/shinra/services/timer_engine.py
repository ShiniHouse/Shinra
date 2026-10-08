import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from shinra.domain import quando as quando_dominio
from shinra.infra.db import depositi
from shinra.infra.lingue import Schemi, schemi

logger = logging.getLogger("Shinra.TimerEngine")


class TimerItem(BaseModel):
    id: str
    label: str
    duration_seconds: int
    started_at: float
    expires_at: float
    user_id: str = "alessio"
    completed: bool = False


class ReminderItem(BaseModel):
    id: str
    text: str
    remind_at: str  # ISO format YYYY-MM-DDTHH:MM:SS
    user_id: str = "alessio"
    completed: bool = False
    created_at: str


class TimerEngine:
    """Timer e promemoria.

    Dalla v0.2.0 stanno nel database. Le firme restano quelle di prima: le
    usano le rotte, l'agente, lo scheduler e la skill Alexa.
    """

    # ---------------------------------------------------------------- timer

    def get_timers(self) -> List[Dict[str, Any]]:
        adesso = time.time()
        timers = depositi.timer.elenco()
        for t in timers:
            # Calcolato al momento della lettura, non salvato: un valore
            # scritto su disco sarebbe sbagliato un secondo dopo.
            t["remaining_seconds"] = max(0, int(t.get("expires_at", adesso) - adesso))
        return timers

    def add_timer(self, label: str, duration_seconds: int, user_id: str = "alessio") -> Dict[str, Any]:
        adesso = time.time()
        t_id = f"timer_{uuid.uuid4().hex[:6]}"
        item = depositi.timer.aggiungi(
            {
                "id": t_id,
                "label": label or "Timer",
                "duration_seconds": duration_seconds,
                "started_at": adesso,
                "expires_at": adesso + duration_seconds,
                "user_id": user_id,
                "completed": False,
            }
        )
        item["remaining_seconds"] = duration_seconds

        # Il conto alla rovescia non vive piu' solo nel browser: alla scadenza
        # e' lo scheduler a suonare, anche a scheda chiusa.
        from shinra.infra.scheduler.motore import scheduler

        scheduler.programma_timer(t_id, item["label"], item["expires_at"], user_id)
        return item

    def delete_timer(self, timer_id: str) -> bool:
        from shinra.infra.scheduler.motore import scheduler

        scheduler.annulla_timer(timer_id)
        return depositi.timer.cancella(timer_id)

    def segna_completato(self, timer_id: str) -> bool:
        """Marca un timer come scaduto.

        Prima nessuno lo faceva: `completed` restava sempre falso, l'elenco
        cresceva all'infinito e ogni voce vecchia riappariva scaduta al
        caricamento successivo della dashboard.
        """
        return depositi.timer.segna_completato(timer_id)

    def pulisci_scaduti(self, conserva_ore: int = 24) -> int:
        """Rimuove i timer completati piu' vecchi del periodo di conservazione."""
        return depositi.timer.pulisci_completati(conserva_ore)

    # ----------------------------------------------------------- promemoria

    def get_reminders(self) -> List[Dict[str, Any]]:
        return depositi.promemoria.elenco()

    def add_reminder(self, text: str, remind_at_iso: str, user_id: str = "alessio") -> Dict[str, Any]:
        """Crea un promemoria. La primitiva sta in `skills/reminders.py`.

        Ce n'erano due copie — una qui, una nel tool che il modello chiama —
        e solo questa funzionava (issue #92). Adesso ce n'e' una sola, e sta
        fra le capacita': scrivere una riga e programmare una sveglia sono
        archivio e scheduler, che stanno sotto. Qui resta l'orchestrazione:
        il ripristino dei job dopo un riavvio, che una capacita' non puo'
        conoscere.
        """
        from shinra.skills import reminders

        return reminders.crea(text, remind_at_iso, user_id)

    def delete_reminder(self, reminder_id: str) -> bool:
        from shinra.skills import reminders

        return reminders.cancella(reminder_id)

    def segna_promemoria_completato(self, reminder_id: str) -> bool:
        return depositi.promemoria.segna_completato(reminder_id)

    # -------------------------------------------------------------- ripresa

    def ripristina_job(self) -> dict[str, int]:
        """Riprogramma i job per timer e promemoria ancora in attesa.

        Serve dopo un riavvio: l'archivio dei job di APScheduler li conserva,
        ma un'installazione che aggiorna da una versione senza scheduler ha
        timer e promemoria in attesa e nessun job corrispondente.
        """
        from shinra.infra.scheduler.motore import scheduler

        contati = {"timer": 0, "promemoria": 0}
        for t in depositi.timer.attivi():
            if scheduler.programma_timer(
                t["id"], t.get("label", "Timer"), t.get("expires_at", 0), t.get("user_id", "")
            ):
                contati["timer"] += 1
        for r in depositi.promemoria.attivi():
            if scheduler.programma_promemoria(
                r["id"], r.get("text", ""), r.get("remind_at", ""), r.get("user_id", "")
            ):
                contati["promemoria"] += 1
        return contati

    # --- Natural Language Parser per Timer & Promemoria ---

    # I numeri che si dicono a voce. «Metti un timer di un minuto» e'
    # italiano normale: prima non veniva riconosciuto perche' la regex
    # pretendeva una cifra, e la frase finiva al modello.

    def parse_timer_or_reminder(
        self, user_text: str, lingua: Optional[Schemi] = None
    ) -> Optional[Dict[str, Any]]:
        """Estrae durata, etichetta o orario da frasi in linguaggio naturale.

        Le parole le dice la lingua (`lingua`, o quella dell'installazione): i numeri, le unita', i verbi che
        chiedono un timer e quelli che chiedono un promemoria stanno nel suo file, sezioni `timer` e `tempo` (#205).
        """
        lingua = lingua or schemi()
        lessico, frasi = lingua.tempo, lingua.timer
        t_lower = user_text.lower().strip()
        parola = frasi["parola"]
        etichetta_dopo = frasi["prima_dell_etichetta"]
        voce = {"secondi": 1, "minuti": 60, "ore": 3600}

        # "mezz'ora" non ha un numero da estrarre: si tratta a parte.
        mezzora = re.search(
            rf"\b{parola}\s+(?:{frasi['prima_della_durata']})?(?:{frasi['mezz_ora']})\b(?:\s+{etichetta_dopo}\s+(.+))?",
            t_lower,
        )
        if mezzora:
            etichetta = (mezzora.group(1) or frasi["etichetta_predefinita"]).strip(" .?!,")
            return {
                "type": "timer",
                "label": etichetta.capitalize(),
                "duration_seconds": 1800,
                "amount": 30,
                "unit": frasi["unita_a_voce"]["minuti"],
            }

        # 1. Timer: "timer 10 minuti", "timer di 5 minuti per la pasta", "metti un timer di 30 secondi".
        # Tollera «d» al posto di «di» (un refuso, o una trascrizione vocale): senza, la frase non era un timer, passava
        # al modello, e il modello inventava un promemoria (trovato provando in casa, #195).
        unita = "|".join(f"(?P<{nome}>{espressione})" for nome, espressione in frasi["unita"].items())
        timer_match = re.search(
            rf"\b{frasi['verbi']}?\s*{frasi['articolo']}{parola}\s+{frasi['prima_della_durata']}"
            rf"(?P<n>{lessico.numero[1:-1]})\s*(?:{unita})\b(?:\s+{etichetta_dopo}\s+(?P<etichetta>.+))?",
            t_lower,
        )
        if timer_match:
            amount = lessico.quantita(timer_match.group("n"))
            if amount is None:
                return None
            nome_unita = next(n for n in voce if timer_match.group(n))
            label = (timer_match.group("etichetta") or frasi["etichetta_predefinita"]).strip(" .?!,")
            return {
                "type": "timer",
                "label": label.capitalize(),
                "duration_seconds": amount * voce[nome_unita],
                "amount": amount,
                "unit": timer_match.group(nome_unita),
            }

        # 2. Promemoria. Il «quando» lo legge `domain/quando.py` con il lessico della lingua: capisce anche «domani
        #    mattina», «sabato», «fra due giorni» e l'ordine delle parole rovesciato («ricordami domani di
        #    chiamare»).
        #
        #    Prima qui c'erano due espressioni regolari, «alle HH» e «tra N minuti», e basta. Tutto il resto cadeva al
        #    modello, che chiamava un tool che scriveva in una lista in memoria e rispondeva «salvato» — issue #92. Le
        #    formule che questo ramo non cattura finiscono ancora al modello, ma adesso il tool le tratta bene, e se
        #    non capisce l'ora chiede invece di fingere.
        chiesto = re.search(rf"\b{frasi['promemoria']}(.+)", t_lower)
        if chiesto:
            resto = chiesto.group(1).strip()
            azione, momento = quando_dominio.separa(resto, lessico=lessico)
            if momento is not None and azione:
                return {
                    "type": "reminder",
                    "text": azione.capitalize(),
                    "remind_at": momento.strftime("%Y-%m-%dT%H:%M:%S"),
                    "formatted_time": quando_dominio.descrivi(momento, lessico=lessico),
                }

        return None


timer_engine = TimerEngine()
