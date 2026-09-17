// ==================== MODULAR ROUTINE BUILDER ====================
let _allModesCache = [];
let _modeAccordionState = {};

function toggleModeSteps(modeId) {
    _modeAccordionState[modeId] = !_modeAccordionState[modeId];
    const stepsEl = document.getElementById(`mode-steps-${modeId}`);
    const btnEl = document.getElementById(`mode-steps-toggle-${modeId}`);
    if (stepsEl) stepsEl.classList.toggle('hidden', !_modeAccordionState[modeId]);
    if (btnEl) btnEl.innerText = _modeAccordionState[modeId] ? 'Nascondi Moduli ▲' : 'Vedi Moduli ▼';
    safeCreateIcons();
}

async function loadModes() {
    try {
        const res = await fetch('/api/modes', { headers: getAuthHeaders() });
        _allModesCache = await res.json();
        // La scorciatoia offre di far partire una routine gia'
        // disegnata: l'elenco lo sa solo adesso, e prima di adesso
        // avrebbe proposto una tendina vuota (#126).
        if (document.getElementById('scorciatoia-cosa')) disegnaScorciatoia();
        const container = document.getElementById('modes-list');
        if (!container) return;

        if (!_allModesCache || _allModesCache.length === 0) {
            container.innerHTML = _html`<div class="col-span-2 text-center py-8 text-slate-500 text-xs">
                Nessuna routine configurata. Clicca "+ Nuova Routine Modulare" per crearne una.
            </div>`;
            return;
        }

        container.innerHTML = _html`${_allModesCache.map((m) => {
            const triggers = (m.trigger_phrases || []).map(
                (t) =>
                    _html`<span class="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-[10px] text-slate-300 font-mono">"${t}"</span>`,
            );
            const actions = m.actions || [];
            const isOpen = Boolean(_modeAccordionState[m.id]);

            const stepsHtml = actions.map((act, idx) => {
                let title = 'Azione';
                let desc = '';
                let badge = '';

                if (act.type === 'ha_device' || act.type === 'ha_service') {
                    title = act.entity_id || act.data?.entity_id || 'Dispositivo HA';
                    const cmd = act.action || act.service || 'turn_on';
                    desc = cmd === 'turn_on' ? 'Accendi' : cmd === 'turn_off' ? 'Spegni' : cmd;
                    badge = _html`<span class="text-[10px] text-indigo-400 bg-indigo-950/80 px-1.5 py-0.5 rounded border border-indigo-800">💡 HA</span>`;
                } else if (act.type === 'delay') {
                    title = `Pausa ${act.seconds || act.delay_seconds || 1}s`;
                    desc = 'Attesa prima del prossimo step';
                    badge = _html`<span class="text-[10px] text-amber-400 bg-amber-950/80 px-1.5 py-0.5 rounded border border-amber-800">⏱️ Pausa</span>`;
                } else if (act.type === 'tts') {
                    title = 'Annuncio Vocale';
                    desc = `"${act.message || ''}"`;
                    badge = _html`<span class="text-[10px] text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-800">🗣️ Parla</span>`;
                }

                return _html`
                    <div class="relative flex items-center gap-3 p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/80 ${idx < actions.length - 1 ? 'mb-2' : ''}">
                        <div class="w-6 h-6 rounded-lg bg-indigo-600/30 text-indigo-300 flex items-center justify-center text-xs shrink-0 font-bold">
                            ${idx + 1}
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center justify-between">
                                <span class="text-xs font-semibold text-slate-200 truncate">${title}</span>
                                ${badge}
                            </div>
                            <p class="text-[11px] text-slate-400 truncate">${desc}</p>
                        </div>
                    </div>
                `;
            });

            return _html`
                <div id="mode-card-${m.id}" class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-col justify-between space-y-3 shadow-sm hover:border-slate-700 transition group">
                    <div>
                        <!-- Header Routine -->
                        <div class="flex justify-between items-start">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center text-white shadow-md shadow-indigo-600/30 shrink-0">
                                    <i data-lucide="${m.icon || 'workflow'}" class="w-5 h-5"></i>
                                </div>
                                <div>
                                    <h3 class="font-bold text-sm text-slate-100">${m.name}</h3>
                                    <span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-950/60 border border-indigo-800 text-indigo-300">${actions.length} moduli collegati</span>
                                </div>
                            </div>
                            <div class="flex items-center gap-1">
                                <button onclick="openModularModeBuilder('${m.id}')" class="p-1.5 text-slate-400 hover:text-indigo-300 rounded-lg hover:bg-slate-800 transition" title="Modifica nel Visual Flow">
                                    <i data-lucide="edit-3" class="w-4 h-4"></i>
                                </button>
                                <button onclick="deleteMode('${m.id}')" class="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-slate-800 transition" title="Elimina routine">
                                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                                </button>
                            </div>
                        </div>

                        <!-- Inneschi Vocali -->
                        <div class="mt-3">
                            <div class="flex flex-wrap gap-1.5">
                                ${triggers || '<span class="text-xs text-slate-500">Nessun comando vocale configurato</span>'}
                            </div>
                        </div>

                        <!-- Pipeline Moduli (Collapsible) -->
                        <div class="mt-3 pt-2 border-t border-slate-800/60">
                            <button type="button" onclick="toggleModeSteps('${m.id}')" id="mode-steps-toggle-${m.id}" class="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition block mb-2">
                                ${isOpen ? 'Nascondi Moduli ▲' : 'Vedi Moduli ▼'}
                            </button>
                            <div id="mode-steps-${m.id}" class="${isOpen ? '' : 'hidden'} space-y-1">
                                ${stepsHtml || '<div class="text-xs text-slate-500">Nessun modulo associato.</div>'}
                            </div>
                        </div>
                    </div>

                    <!-- Footer / Test & Flow Edit -->
                    <div class="pt-3 border-t border-slate-800 flex justify-between items-center">
                        <button onclick="openModularModeBuilder('${m.id}')" class="text-xs text-slate-400 hover:text-indigo-300 flex items-center gap-1 transition">
                            <i data-lucide="workflow" class="w-3.5 h-3.5"></i> Editor Visivo
                        </button>
                        <button onclick="triggerModularMode(${_grezzo(_perAttributoJs(m.name))}, ${_grezzo(_perAttributoJs(m.id))})" id="btn-run-mode-${m.id}" class="px-3.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/40 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
                            <i data-lucide="play" class="w-3.5 h-3.5"></i> Esegui
                        </button>
                    </div>
                </div>
            `;
        })}`;
        safeCreateIcons();
    } catch (e) {
        console.error('loadModes error:', e);
    }
}

async function triggerModularMode(name, modeId) {
    const btn = document.getElementById(`btn-run-mode-${modeId}`);
    const card = document.getElementById(`mode-card-${modeId}`);
    if (btn) btn.innerHTML = _html`<span class="animate-spin">⏳</span> Esecuzione...`;
    if (card) card.classList.add('border-indigo-500', 'ring-1', 'ring-indigo-500/50');

    try {
        const res = await fetch(`/api/modes/${encodeURIComponent(name)}/activate`, {
            headers: getAuthHeaders(),
            method: 'POST',
        });
        const data = await res.json();
        if (data.messaggio) speakText(data.messaggio);
    } catch (e) {
        console.error('Errore attivazione modalità:', e);
    }

    setTimeout(() => {
        if (btn) btn.innerHTML = _html`<i data-lucide="play" class="w-3.5 h-3.5"></i> ▶️ Esegui Test`;
        if (card) card.classList.remove('border-indigo-500', 'ring-1', 'ring-indigo-500/50');
        safeCreateIcons();
    }, 1200);
}
