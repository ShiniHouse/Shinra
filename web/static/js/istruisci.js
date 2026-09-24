// ==================== SHINRA ISTRUISCI / LEARNING INTERVIEW ENGINE ====================
let currentLearningSession = null;
let learningRecognition = null;
let isLearningListening = false;
let currentProposedRoutine = null;
let lastLearningQuestion = '';

async function startLearningModal() {
    const modal = document.getElementById('learning-interview-modal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Reset UI
    document.getElementById('learning-facts-container').classList.add('hidden');
    document.getElementById('learning-facts-list').innerHTML = '';
    document.getElementById('learning-routine-box').classList.add('hidden');
    document.getElementById('learning-answer-input').value = '';
    document.getElementById('learning-question-text').innerText = 'Inizializzazione intervista in corso...';
    document.getElementById('learning-topic-title').innerHTML =
        _html`<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i> Avvio...`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/start', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ user_id: Stato.utenteAttivo || 'alessio' }),
        });
        if (!res.ok) throw new Error('Errore avvio sessione');
        const data = await res.json();
        currentLearningSession = data;
        renderLearningStep(data);
    } catch (err) {
        console.error('startLearningModal:', err);
        document.getElementById('learning-question-text').innerText =
            'Impossibile avviare la sessione di apprendimento. Verifica la connessione.';
    }
}

function renderLearningStep(data) {
    currentLearningSession = data;
    const modal = document.getElementById('learning-interview-modal');
    if (!modal) return;

    const stepBadge = document.getElementById('learning-step-badge');
    const progBar = document.getElementById('learning-progress-bar');
    const topicTitle = document.getElementById('learning-topic-title');
    const qText = document.getElementById('learning-question-text');
    const hintText = document.getElementById('learning-hint-text');
    const answerInput = document.getElementById('learning-answer-input');
    const routineBox = document.getElementById('learning-routine-box');
    const factsContainer = document.getElementById('learning-facts-container');
    const factsList = document.getElementById('learning-facts-list');
    const submitBtn = document.getElementById('learning-submit-btn');

    if (data.is_complete) {
        stepBadge.innerText = 'Completata! 🎉';
        progBar.style.width = '100%';
        topicTitle.innerHTML = _html`<i data-lucide="check-circle" class="w-3.5 h-3.5 text-emerald-400"></i> Apprendimento Concluso`;
        qText.innerText = data.message;
        hintText.innerText = 'Tutti i fatti e le preferenze sono stati registrati nella tua Conoscenza Casa.';
        answerInput.parentElement.classList.add('hidden');
        submitBtn.parentElement.innerHTML = _html`
            <button type="button" onclick="closeLearningModal()" class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-indigo-600 hover:from-emerald-400 text-white rounded-xl text-xs font-bold transition shadow-lg">
                Chiudi e Visualizza Conoscenza
            </button>
        `;
        speakText(data.message);
        safeCreateIcons();
        loadKnowledge();
        return;
    }

    const step = data.step;
    const currentIdx = (data.step_index || 0) + 1;
    const total = data.total_steps || 6;
    const pct = Math.round((currentIdx / total) * 100);

    stepBadge.innerText = `Fase ${currentIdx} di ${total}`;
    progBar.style.width = `${pct}%`;
    const inConferma = data.fase === 'conferma';
    topicTitle.innerHTML = inConferma
        ? _html`<i data-lucide="list-checks" class="w-3.5 h-3.5 text-amber-400"></i> Ho capito bene?`
        : _html`<i data-lucide="help-circle" class="w-3.5 h-3.5"></i> ${step.title || 'Domanda'}`;

    // Il testo da mostrare e' quello che manda il server, non la domanda dello
    // step. Fino alla #170 qui c'era `step.question || data.message`, e la
    // domanda vinceva **sempre**: il riconoscimento — compreso «non sono
    // riuscita a ricavarne niente», aggiunto apposta dalla #171 — finiva nel
    // payload e non arrivava mai sullo schermo. Chi rispondeva vedeva solo la
    // domanda successiva, e continuava a credere che la casa stesse imparando.
    const daMostrare = data.message || step.question || '';
    qText.innerText = daMostrare;
    lastLearningQuestion = daMostrare;
    hintText.innerText = data.suggerimento || (step.hint ? `💡 ${step.hint}` : '');

    // Routine Proposal
    if (data.proposed_routine && data.proposed_routine.name) {
        currentProposedRoutine = data.proposed_routine;
        document.getElementById('learning-routine-desc').innerText =
            `Ho notato una possibile routine "${data.proposed_routine.name}": ${data.proposed_routine.description || 'Automazione personalizzata'}.`;
        routineBox.classList.remove('hidden');
    } else {
        routineBox.classList.add('hidden');
        currentProposedRoutine = null;
    }

    // Facts list
    if (data.new_facts && data.new_facts.length > 0) {
        factsContainer.classList.remove('hidden');
        data.new_facts.forEach((f) => {
            const badge = document.createElement('span');
            badge.className =
                'px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-700/60 text-emerald-300 text-[11px]';
            badge.innerText = `✓ ${f.text}`;
            factsList.appendChild(badge);
        });
    }

    answerInput.value = '';
    answerInput.parentElement.classList.remove('hidden');
    answerInput.placeholder = inConferma
        ? 'Rispondi «sì», «no», oppure riscrivi la frase come la diresti tu...'
        : 'Parla al microfono o scrivi qui la tua risposta...';
    answerInput.focus();

    // Speak question
    speakText(daMostrare);
    safeCreateIcons();
}

function playAudioOrSpeak(text) {
    if (text && typeof speakText === 'function') {
        speakText(text);
    }
}

function replayLearningQuestionAudio() {
    if (lastLearningQuestion) {
        speakText(lastLearningQuestion);
    }
}

async function submitLearningAnswer() {
    const input = document.getElementById('learning-answer-input');
    const text = input ? input.value.trim() : '';
    if (!text) {
        alert('Inserisci o detta una risposta prima di proseguire.');
        return;
    }

    const submitBtn = document.getElementById('learning-submit-btn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = _html`<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> <span>Salvataggio...</span>`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/answer', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                user_id: Stato.utenteAttivo || 'alessio',
                answer: text,
            }),
        });
        if (!res.ok) throw new Error('Errore durante il salvataggio');
        const data = await res.json();
        renderLearningStep(data);
        loadKnowledge();
    } catch (err) {
        console.error('submitLearningAnswer:', err);
        alert("Errore durante l'elaborazione della risposta: " + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        safeCreateIcons();
    }
}

async function acceptProposedRoutine() {
    if (!currentProposedRoutine) return;
    const btn = document.getElementById('learning-routine-confirm-btn');
    btn.disabled = true;
    btn.innerHTML = _html`<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i> Creazione in corso...`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/confirm-routine', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ routine: currentProposedRoutine }),
        });
        const data = await res.json();
        if (data.success) {
            btn.className =
                'px-3 py-1.5 bg-slate-800 text-emerald-400 rounded-xl text-xs font-bold transition flex items-center gap-1.5 border border-emerald-500/40';
            btn.innerHTML = _html`<i data-lucide="check-check" class="w-3.5 h-3.5"></i> Routine Creata con Successo!`;
            safeCreateIcons();
            if (typeof loadModes === 'function') loadModes();
        } else {
            alert('Errore creazione routine: ' + (data.error || 'Errore sconosciuto'));
            btn.disabled = false;
        }
    } catch (err) {
        console.error('acceptProposedRoutine:', err);
        btn.disabled = false;
    }
}

async function toggleLearningMic() {
    const micBtn = document.getElementById('learning-mic-btn');
    const statusLabel = document.getElementById('learning-mic-status');
    const input = document.getElementById('learning-answer-input');

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert(
            'Riconoscimento vocale non supportato dal browser. Puoi digitare la risposta nella casella di testo.',
        );
        return;
    }

    if (isLearningListening && learningRecognition) {
        try {
            learningRecognition.stop();
        } catch {}
        isLearningListening = false;
        if (statusLabel) statusLabel.classList.add('hidden');
        if (micBtn) {
            micBtn.classList.remove('bg-rose-600', 'text-white');
            micBtn.classList.add('bg-slate-800', 'text-slate-300');
        }
        return;
    }

    // Su iOS Safari: sblocca la sessione microfono se necessario
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach((t) => t.stop());
        } catch (micErr) {
            console.warn('Permesso microfono non concesso da iOS:', micErr);
            alert(
                "Accesso al microfono non consentito da iOS. Vai in Impostazioni iPhone ➔ Safari ➔ Microfono e seleziona 'Consenti'.",
            );
            return;
        }
    }

    try {
        learningRecognition = new SpeechRec();
        learningRecognition.lang = 'it-IT';
        learningRecognition.continuous = false;
        learningRecognition.interimResults = true;

        let finalTranscript = '';
        const initialText = input ? input.value.trim() : '';

        learningRecognition.onstart = () => {
            isLearningListening = true;
            if (statusLabel) {
                statusLabel.innerText = '🎙️ In ascolto... parla pure!';
                statusLabel.classList.remove('hidden');
            }
            if (micBtn) {
                micBtn.classList.add('bg-rose-600', 'text-white');
                micBtn.classList.remove('bg-slate-800', 'text-slate-300');
            }
        };

        learningRecognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += piece;
                } else {
                    interim += piece;
                }
            }
            const spoken = (finalTranscript || interim).trim();
            if (input && spoken) {
                input.value = initialText ? `${initialText} ${spoken}` : spoken;
            }
        };

        learningRecognition.onerror = (event) => {
            console.warn('Learning speech error:', event.error);
            isLearningListening = false;
            if (statusLabel) statusLabel.classList.add('hidden');
            if (micBtn) {
                micBtn.classList.remove('bg-rose-600', 'text-white');
                micBtn.classList.add('bg-slate-800', 'text-slate-300');
            }
            if (event.error === 'not-allowed') {
                alert('Permesso microfono non autorizzato su iOS. Controlla le impostazioni di Safari.');
            }
        };

        learningRecognition.onend = () => {
            isLearningListening = false;
            if (statusLabel) statusLabel.classList.add('hidden');
            if (micBtn) {
                micBtn.classList.remove('bg-rose-600', 'text-white');
                micBtn.classList.add('bg-slate-800', 'text-slate-300');
            }
        };

        learningRecognition.start();
    } catch (err) {
        console.error('Errore avvio learningRecognition:', err);
        isLearningListening = false;
        if (statusLabel) statusLabel.classList.add('hidden');
        if (micBtn) {
            micBtn.classList.remove('bg-rose-600', 'text-white');
            micBtn.classList.add('bg-slate-800', 'text-slate-300');
        }
    }
}

async function closeLearningModal() {
    if (isLearningListening && learningRecognition) {
        learningRecognition.stop();
    }
    const modal = document.getElementById('learning-interview-modal');
    if (modal) modal.style.display = 'none';

    try {
        await fetch('/api/learning/stop', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ user_id: Stato.utenteAttivo || 'alessio' }),
        });
    } catch {}

    await loadKnowledge();
}

async function saveNewKnowledge() {
    const text = document.getElementById('new-k-text').value.trim();
    const category = document.getElementById('new-k-cat').value || 'generale';
    if (!text) return;
    await fetch('/api/knowledge', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ text, category, enabled: true }),
    });
    closeModal();
    loadKnowledge();
}

async function deleteKnowledge(id) {
    if (!confirm('Rimuovere questo fatto?')) return;
    await fetch(`/api/knowledge/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
    loadKnowledge();
}
