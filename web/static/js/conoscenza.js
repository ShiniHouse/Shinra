// ==================== KNOWLEDGE TEMPLATES ====================
const KNOWLEDGE_TEMPLATES = [
    {
        id: 'casa',
        icon: '🏠',
        label: 'Casa & Indirizzo',
        fields: [
            { key: 'indirizzo', label: 'Indirizzo completo', placeholder: 'es. Via Roma 10, Arezzo, 52100' },
            { key: 'piano', label: 'Piano / Interno', placeholder: 'es. Piano 2, interno 4' },
            { key: 'citofono', label: 'Citofono / Campanello', placeholder: 'es. Rossi' },
            { key: 'wifi_nome', label: 'Nome rete WiFi', placeholder: 'es. CasaMia_5G' },
        ],
    },
    {
        id: 'famiglia',
        icon: '👨‍👩‍👧',
        label: 'Famiglia & Conviventi',
        fields: [
            {
                key: 'componenti',
                label: 'Componenti del nucleo',
                placeholder: 'es. Alessio (admin), Giulia (adulto), Marco (10 anni)',
            },
            { key: 'animali', label: 'Animali domestici', placeholder: 'es. Rex, cane labrador 3 anni' },
            {
                key: 'compleanni',
                label: 'Compleanni importanti',
                placeholder: 'es. Giulia il 15 marzo, Marco il 8 luglio',
            },
        ],
    },
    {
        id: 'abitudini',
        icon: '📅',
        label: 'Abitudini & Routine',
        fields: [
            {
                key: 'sveglia',
                label: 'Orario sveglia solito',
                placeholder: 'es. 7:00 nei giorni feriali, 9:00 weekend',
            },
            {
                key: 'lavoro',
                label: 'Orari lavoro / scuola',
                placeholder: 'es. Alessio lavora 9-18, Marco scuola 8-16',
            },
            { key: 'rientro', label: 'Orario rientro a casa', placeholder: 'es. solitamente verso le 19:00' },
            { key: 'hobby', label: 'Hobby & passioni', placeholder: 'es. calcio, lettura, videogiochi' },
            {
                key: 'cibo',
                label: 'Cucina / piatti preferiti',
                placeholder: 'es. pasta al pomodoro, pizza margherita',
            },
        ],
    },
    {
        id: 'salute',
        icon: '🏥',
        label: 'Salute & Emergenze',
        fields: [
            { key: 'medico', label: 'Medico di base', placeholder: 'es. Dr. Rossi, tel. 0123-456789' },
            {
                key: 'pronto_soc',
                label: 'Pronto soccorso vicino',
                placeholder: 'es. Ospedale San Donato, Via X',
            },
            {
                key: 'farmacia',
                label: 'Farmacia di fiducia',
                placeholder: 'es. Farmacia Centrale, aperta 24h',
            },
            {
                key: 'allergie',
                label: 'Allergie / intolleranze',
                placeholder: 'es. Giulia allergica alle arachidi',
            },
            { key: 'gruppo_sg', label: 'Gruppo sanguigno', placeholder: 'es. Alessio A+, Giulia 0-' },
        ],
    },
    {
        id: 'casa_tecnica',
        icon: '🔧',
        label: 'Contatti & Tecnici',
        fields: [
            {
                key: 'idraulico',
                label: 'Idraulico di fiducia',
                placeholder: 'es. Mario Verdi, tel. 333-1234567',
            },
            {
                key: 'elettricista',
                label: 'Elettricista',
                placeholder: 'es. Luigi Bianchi, tel. 347-7654321',
            },
            {
                key: 'portiere',
                label: 'Portiere / Amministratore',
                placeholder: 'es. Sig. Ferrari, tel. 0575-123456',
            },
            {
                key: 'assicurazione',
                label: 'Assicurazione casa',
                placeholder: 'es. Unipol polizza n. 12345, tel. 800-xxx',
            },
        ],
    },
    {
        id: 'veicoli',
        icon: '🚗',
        label: 'Veicoli & Spostamenti',
        fields: [
            {
                key: 'auto1',
                label: 'Auto principale',
                placeholder: 'es. Fiat Panda, targa EF123GH, colore bianco',
            },
            { key: 'auto2', label: 'Secondo veicolo', placeholder: 'es. Vespa 125, targa AA000AA' },
            { key: 'parcheggio', label: 'Box / Parcheggio', placeholder: 'es. Box n. 12 in Via Roma' },
        ],
    },
    {
        id: 'digitale',
        icon: '📱',
        label: 'Preferenze Digitali',
        fields: [
            { key: 'streaming', label: 'Servizi streaming', placeholder: 'es. Netflix, Disney+, Spotify' },
            {
                key: 'musica',
                label: 'Generi musicali preferiti',
                placeholder: 'es. rock anni 80, jazz, musica italiana',
            },
            {
                key: 'smart_tv',
                label: 'TV principale',
                placeholder: 'es. Samsung 55" in salotto, entity: media_player.tv_salotto',
            },
            {
                key: 'voce_alexa',
                label: 'Echo Alexa principale',
                placeholder: 'es. Echo Show in cucina, Echo Dot in camera',
            },
        ],
    },
    {
        id: 'note_libere',
        icon: '📝',
        label: 'Note & Preferenze Varie',
        fields: [
            {
                key: 'lingua',
                label: 'Lingua preferita risposta',
                placeholder: 'es. sempre in italiano, tono informale',
            },
            {
                key: 'privacy',
                label: 'Note sulla privacy',
                placeholder: 'es. non leggere messaggi ad alta voce se ci sono ospiti',
            },
            {
                key: 'note',
                label: 'Altre note importanti',
                placeholder: 'es. il campanello è rotto dal 2024, intercome non funziona',
            },
        ],
    },
];

let _allKnowledgeItems = [];

async function loadKnowledge() {
    try {
        const res = await fetch('/api/knowledge', { headers: getAuthHeaders() });
        const items = await res.json();
        _allKnowledgeItems = items;
        const container = document.getElementById('knowledge-list');

        if (!items.length) {
            container.innerHTML = _html`<p class="text-xs text-slate-500 col-span-2 py-3 text-center">Nessun fatto memorizzato. Compila una categoria qui sopra o aggiungi un fatto libero.</p>`;
        } else {
            const catColors = {
                casa: 'indigo',
                famiglia: 'violet',
                abitudini: 'sky',
                salute: 'rose',
                casa_tecnica: 'amber',
                veicoli: 'green',
                digitale: 'purple',
                note_libere: 'slate',
                generale: 'slate',
            };
            container.innerHTML = _html`${items.map((k) => {
                const cat = k.category || 'generale';
                const col = catColors[cat] || 'slate';
                return _html`
                <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-start gap-3 group hover:border-slate-700 transition">
                    <div class="flex-1 min-w-0">
                        <span class="px-2 py-0.5 rounded bg-${col}-950/60 border border-${col}-800 text-[10px] text-${col}-300 font-mono uppercase">${cat}</span>
                        <p class="text-xs text-slate-200 mt-1.5 leading-relaxed">${k.text}</p>
                    </div>
                    <button onclick="deleteKnowledge(${_grezzo(_perAttributoJs(k.id))})" class="text-slate-600 hover:text-rose-400 transition p-1 opacity-0 group-hover:opacity-100 shrink-0" title="Elimina fatto">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </div>`;
            })}`;
        }
        safeCreateIcons();
        renderKnowledgeTemplates(items);
    } catch (e) {
        console.error('loadKnowledge:', e);
    }
}

function renderKnowledgeTemplates(existingItems) {
    const container = document.getElementById('knowledge-templates-section');
    if (!container) return;

    // Mappa delle chiavi compilate
    const savedMap = {};
    existingItems.forEach((k) => {
        if (k._key) savedMap[k._key] = k.text.replace(/^[^:]+:\s*/, '');
    });

    container.innerHTML = _html`${KNOWLEDGE_TEMPLATES.map((section) => {
        const filledCount = section.fields.filter((f) => savedMap[`${section.id}.${f.key}`]).length;
        const totalCount = section.fields.length;
        const isComplete = filledCount === totalCount;

        let riquadro;
        if (filledCount === 0) {
            riquadro = _html`<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">Da compilare</span>`;
        } else if (isComplete) {
            riquadro = _html`<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800 flex items-center gap-1">✓ ${filledCount}/${totalCount}</span>`;
        } else {
            riquadro = _html`<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-950/60 text-indigo-300 border border-indigo-800">${filledCount}/${totalCount} compilati</span>`;
        }

        // Genera chip di anteprima dei valori inseriti
        const anteprime = section.fields
            .filter((f) => savedMap[`${section.id}.${f.key}`])
            .map(
                (f) =>
                    _html`<span class="px-2 py-0.5 rounded-md bg-slate-950 border border-slate-800 text-[10px] text-slate-300 truncate max-w-[140px]" title="${f.label}: ${savedMap[`${section.id}.${f.key}`]}">${f.label}: ${savedMap[`${section.id}.${f.key}`]}</span>`,
            )
            .slice(0, 3);

        return _html`
        <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 hover:border-slate-700 transition flex flex-col justify-between space-y-3 group shadow-sm">
            <div class="space-y-2">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2.5">
                        <div class="w-8 h-8 rounded-xl bg-slate-800 flex items-center justify-center text-base shadow-inner">
                            ${section.icon}
                        </div>
                        <div>
                            <h4 class="font-bold text-xs text-slate-100">${section.label}</h4>
                            <span class="text-[10px] text-slate-500">${totalCount} parametri</span>
                        </div>
                    </div>
                    ${riquadro}
                </div>
                <div class="flex flex-wrap gap-1 min-h-[22px] pt-1">
                    ${
                        anteprime.length
                            ? anteprime
                            : _grezzo(
                                  '<span class="text-[10px] text-slate-600 italic">Nessun dato inserito.</span>',
                              )
                    }
                    ${filledCount > 3 ? _html`<span class="text-[10px] text-slate-500 font-semibold self-center">+${filledCount - 3} altri</span>` : ''}
                </div>
            </div>
            <div class="pt-2 border-t border-slate-800/80 flex justify-end">
                <button onclick="openKnowledgeCategoryModal(${_grezzo(_perAttributoJs(section.id))})" class="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 border border-indigo-600/40 text-indigo-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition">
                    <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> ${filledCount > 0 ? 'Modifica Dati' : 'Compila Categoria'}
                </button>
            </div>
        </div>
        `;
    })}`;
    safeCreateIcons();
}

function openKnowledgeCategoryModal(sectionId) {
    const section = KNOWLEDGE_TEMPLATES.find((s) => s.id === sectionId);
    if (!section) return;

    const existingMap = {};
    _allKnowledgeItems.forEach((k) => {
        if (k._key && k._key.startsWith(sectionId + '.')) {
            const fieldKey = k._key.split('.')[1];
            existingMap[fieldKey] = k.text.replace(/^[^:]+:\s*/, '');
        }
    });

    showModal(
        _html`
        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                <span class="text-xl">${section.icon}</span> ${section.label}
            </h3>
            <button onclick="closeModal()" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>
        <p class="text-xs text-slate-400 mt-2">Compila o modifica i dettagli per Shinra. Lascia vuoti i campi che non vuoi memorizzare.</p>
        <div class="space-y-3 mt-4 max-h-[60vh] overflow-y-auto pr-1">
            ${section.fields.map((f) => {
                const val = existingMap[f.key] || '';
                return _html`
                <div>
                    <label class="text-[11px] font-semibold text-slate-300 block mb-1">${f.label}</label>
                    <input type="text" id="modal-kt-${section.id}-${f.key}"
                        value="${val}"
                        placeholder="${f.placeholder}"
                        class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
                </div>
                `;
            })}
        </div>
        <div class="flex justify-end gap-2 pt-4 border-t border-slate-800 mt-4">
            <button onclick="closeModal()" class="px-3.5 py-2 rounded-xl bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 transition">Annulla</button>
            <button onclick="saveKnowledgeCategory(${_grezzo(_perAttributoJs(section.id))})" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5 transition shadow-md shadow-indigo-600/30">
                <i data-lucide="check" class="w-3.5 h-3.5"></i> Salva Informazioni
            </button>
        </div>
    `,
        false,
    );
}

async function saveKnowledgeCategory(sectionId) {
    const section = KNOWLEDGE_TEMPLATES.find((s) => s.id === sectionId);
    if (!section) return;

    for (const f of section.fields) {
        const inp = document.getElementById(`modal-kt-${section.id}-${f.key}`);
        const val = inp ? inp.value.trim() : '';
        if (val) {
            const text = `${f.label}: ${val}`;
            await fetch('/api/knowledge', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    text,
                    category: section.id,
                    enabled: true,
                    _key: `${section.id}.${f.key}`,
                }),
            });
        }
    }
    closeModal();
    await loadKnowledge();
}

function openAddKnowledgeModal() {
    showModal(_html`
        <h3 class="font-bold text-sm text-slate-100 mb-1">Aggiungi Fatto Libero</h3>
        <p class="text-xs text-slate-400 mb-4">Scrivi qualsiasi informazione in forma di frase naturale.</p>
        <label class="text-xs text-slate-400 block mb-1">Fatto / Informazione</label>
        <textarea id="new-k-text" rows="3" placeholder="es. La combinazione del cancello è 1234. Il gatto si chiama Micio ed è ipoallergenico."
            class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 resize-none focus:outline-none focus:border-indigo-500"></textarea>
        <label class="text-xs text-slate-400 block mb-1">Categoria</label>
        <select id="new-k-cat" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-300 mb-4 focus:outline-none focus:border-indigo-500">
            <option value="generale">generale</option>
            <option value="casa">casa</option>
            <option value="famiglia">famiglia</option>
            <option value="abitudini">abitudini</option>
            <option value="salute">salute</option>
            <option value="casa_tecnica">tecnici & contatti</option>
            <option value="veicoli">veicoli</option>
            <option value="digitale">digitale</option>
        </select>
        <div class="flex justify-end gap-2">
            <button onclick="closeModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300 hover:bg-slate-700">Annulla</button>
            <button onclick="saveNewKnowledge()" class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold">Salva</button>
        </div>
    `);
    setTimeout(() => document.getElementById('new-k-text')?.focus(), 100);
}
