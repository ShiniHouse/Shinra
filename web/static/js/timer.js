// ==================== CHIME AUDIO & TIMER ENGINE ====================
function playChimeAlert() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;

        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now); // D5
        gain1.gain.setValueAtTime(0.3, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.4);

        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, now + 0.12); // A5
        gain2.gain.setValueAtTime(0.35, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.7);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.7);
    } catch (e) {
        console.warn('Audio Context non supportato:', e);
    }
}

let _timerInterval = null;

async function loadTimers() {
    try {
        const res = await fetch('/api/timers', { headers: getAuthHeaders() });
        Stato.timerAttivi = await res.json();
        renderTimers();
    } catch (e) {
        console.error('Errore loadTimers:', e);
    }
}

function renderTimers() {
    const container = document.getElementById('active-timers-list');
    if (!container) return;
    if (!Stato.timerAttivi || Stato.timerAttivi.length === 0) {
        container.innerHTML =
            '<div class="text-[11px] text-slate-500 text-center py-2">Nessun timer attivo. Prova a dire "Timer pasta 9 minuti".</div>';
        return;
    }

    container.innerHTML = _html`${Stato.timerAttivi.map((t) => {
        const rem = t.remaining_seconds || 0;
        const m = Math.floor(rem / 60);
        const s = rem % 60;
        const timeStr = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        const pct =
            t.duration_seconds > 0
                ? Math.min(100, Math.max(0, ((t.duration_seconds - rem) / t.duration_seconds) * 100))
                : 0;
        const isFinished = rem <= 0;

        return _html`
            <div class="p-2.5 rounded-xl bg-slate-950/80 border ${isFinished ? 'border-amber-500/80 bg-amber-950/30 animate-pulse' : 'border-slate-800'} flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-lg ${isFinished ? 'bg-amber-500 text-slate-950' : 'bg-amber-600/30 text-amber-300'} flex items-center justify-center font-bold text-xs">
                        ⏳
                    </div>
                    <div>
                        <h4 class="font-bold text-xs text-slate-200">${t.label || 'Timer'}</h4>
                        <div class="flex items-center gap-2 mt-0.5">
                            <span class="font-mono text-xs font-bold ${isFinished ? 'text-amber-400' : 'text-slate-300'}">${timeStr}</span>
                            <div class="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div class="h-full bg-amber-500 transition-all duration-1000" style="width: ${pct}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <button onclick="deleteTimer(${_grezzo(_perAttributoJs(t.id))})" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Cancella timer">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>
        `;
    })}`;
    safeCreateIcons();
}

async function deleteTimer(id) {
    await fetch(`/api/timers/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    Stato.timerAttivi = Stato.timerAttivi.filter((t) => t.id !== id);
    renderTimers();
}

function openAddTimerModal() {
    showModal(_html`
        <h3 class="font-bold text-sm text-slate-100 mb-3 flex items-center gap-2">
            <i data-lucide="timer" class="w-4 h-4 text-amber-400"></i> Imposta Nuovo Timer
        </h3>
        <label class="text-slate-400 text-xs block mb-1">Nome o Etichetta (es. Pasta, Tè, Forno):</label>
        <input type="text" id="new-timer-label" value="Timer" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 focus:outline-none focus:border-amber-500">

        <label class="text-slate-400 text-xs block mb-1">Durata (Minuti):</label>
        <input type="number" id="new-timer-min" min="1" max="180" value="5" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-4 focus:outline-none focus:border-amber-500">

        <div class="flex justify-end gap-2">
            <button onclick="closeModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300">Annulla</button>
            <button onclick="saveNewTimerManual()" class="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-xs text-white font-semibold">Avvia Timer</button>
        </div>
    `);
    setTimeout(() => document.getElementById('new-timer-label')?.focus(), 100);
}

async function saveNewTimerManual() {
    const label = document.getElementById('new-timer-label').value.trim() || 'Timer';
    const mins = parseInt(document.getElementById('new-timer-min').value) || 1;
    const secs = mins * 60;
    const res = await fetch('/api/timers', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ label, duration_seconds: secs, user_id: Stato.utenteAttivo || 'alessio' }),
    });
    if (res.ok) {
        closeModal();
        loadTimers();
    }
}

// Il conto alla rovescia qui e' solo estetico: fa scorrere i secondi
// sullo schermo. Chi decide che un timer e' scaduto e' il server, che
// lo annuncia su /ws/eventi — cosi' suona anche a scheda chiusa e
// anche sull'Echo. Se il collegamento agli eventi non c'e' (rete giu',
// versione vecchia del server) il ticker torna a suonare da solo:
// meglio un avviso locale che nessun avviso.
function startTimerTick() {
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(() => {
        let cambiato = false;
        for (const t of Stato.timerAttivi) {
            if (t.remaining_seconds > 0) {
                t.remaining_seconds -= 1;
                cambiato = true;
                if (t.remaining_seconds === 0 && !t._notified && !Stato.eventiCollegati) {
                    t._notified = true;
                    playChimeAlert();
                    speakText(`Attenzione, il timer per ${t.label} è terminato!`);
                }
            }
        }
        if (cambiato || Stato.timerAttivi.length > 0) {
            renderTimers();
        }
    }, 1000);
}

// ============ PROMEMORIA ============
let _promemoria = [];

async function loadReminders() {
    try {
        const res = await fetch('/api/reminders', { headers: getAuthHeaders() });
        if (!res.ok) return;
        _promemoria = (await res.json()).filter((r) => !r.completed);
        renderReminders();
    } catch (e) {
        console.error('Errore loadReminders:', e);
    }
}

function _quandoLeggibile(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso || '';
    const oggi = new Date();
    const stessoGiorno = d.toDateString() === oggi.toDateString();
    const ora = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    return stessoGiorno
        ? `oggi alle ${ora}`
        : `${d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })} alle ${ora}`;
}

function renderReminders() {
    const container = document.getElementById('lista-promemoria');
    if (!container) return;
    if (!_promemoria || _promemoria.length === 0) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = _html`${_promemoria.map(
        (r) => _html`
        <div class="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-lg bg-sky-600/30 text-sky-300 flex items-center justify-center font-bold text-xs">🔔</div>
                <div>
                    <h4 class="font-bold text-xs text-slate-200">${r.text}</h4>
                    <span class="text-[11px] text-slate-400">${_quandoLeggibile(r.remind_at)}</span>
                </div>
            </div>
            <button onclick="deleteReminder(${_grezzo(_perAttributoJs(r.id))})" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Cancella promemoria">
                <i data-lucide="x" class="w-4 h-4"></i>
            </button>
        </div>
    `,
    )}`;
    safeCreateIcons();
}

async function deleteReminder(id) {
    await fetch(`/api/reminders/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    _promemoria = _promemoria.filter((r) => r.id !== id);
    renderReminders();
}

// ============ COSA SCATTERA' FRA POCO (issue #123) ============
// Al posto del nome del modello e della frase di Alexa — due cose che
// non cambiano da un'ora all'altra — la colonna della console dice
// cosa sta per fare la casa. Il prossimo scatto lo sa gia' il server:
// `/api/regole` lo calcola per ogni regola e lo chiama `prossimo`.
async function caricaProssimiScatti() {
    const contenitore = document.getElementById('prossimi-scatti');
    if (!contenitore) return;
    try {
        const risposta = await fetch('/api/regole', { headers: getAuthHeaders() });
        if (!risposta.ok) return;
        const dati = await risposta.json();
        disegnaProssimiScatti(dati.regole || []);
    } catch {
        contenitore.innerHTML =
            '<div class="text-[11px] text-slate-500 text-center py-2">Non riesco a leggere il calendario della casa.</div>';
    }
}

function disegnaProssimiScatti(regole) {
    const contenitore = document.getElementById('prossimi-scatti');
    if (!contenitore) return;

    // Una regola zittita non scattera'; una su evento non ha un orario.
    // Qui si guarda solo cio' che ha una data e sta per arrivare.
    const attese = (regole || [])
        .filter((r) => r.attiva && r.prossimo && !isNaN(new Date(r.prossimo)))
        .sort((a, b) => new Date(a.prossimo) - new Date(b.prossimo))
        .slice(0, 4);

    // L'etichetta sta dentro cio' che si disegna, non sopra il
    // pannello: un titolo fisso in piu' era esattamente il peso che
    // questa colonna doveva smettere di avere.
    const etichetta = _grezzo(
        '<p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Fra poco, da sola</p>',
    );

    if (!attese.length) {
        contenitore.innerHTML = _html`${etichetta}
            <div class="text-[11px] text-slate-500 py-1 leading-relaxed">
                Niente in programma: nelle prossime ore la casa aspetta te.
                <button type="button" onclick="switchTab('automazioni')" class="text-indigo-400 hover:text-indigo-300 font-semibold underline decoration-dotted">Vedi le automazioni</button>
            </div>`;
        return;
    }

    contenitore.innerHTML = _html`${etichetta}${attese.map(
        (r) => _html`
        <div class="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between gap-2.5">
            <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-7 h-7 rounded-lg bg-emerald-600/25 text-emerald-300 flex items-center justify-center shrink-0">
                    <i data-lucide="zap" class="w-3.5 h-3.5"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-200 truncate">${r.nome || 'Automazione'}</h4>
                    <span class="text-[11px] text-emerald-400">${_quandoLeggibile(r.prossimo)}</span>
                </div>
            </div>
        </div>
    `,
    )}`;
    safeCreateIcons();
}
