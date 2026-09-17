// ==================== ALIASES CRUD ====================
async function loadAliases() {
    try {
        const res = await fetch('/api/aliases', { headers: getAuthHeaders() });
        const items = await res.json();
        const container = document.getElementById('aliases-list');
        if (!items.length) {
            container.innerHTML = `<p class="text-xs text-slate-500 col-span-3 py-4 text-center">Nessun alias configurato. Clicca "Scopri Dispositivi HA" per iniziare.</p>`;
            return;
        }
        container.innerHTML = items.map(a => `
            <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-1.5 group">
                <div class="flex justify-between items-start">
                    <span class="font-bold text-xs text-indigo-300">"${a.alias}"</span>
                    <button onclick="deleteAlias('${a.id}')" class="text-slate-600 hover:text-rose-400 p-1 opacity-0 group-hover:opacity-100 transition"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
                </div>
                <div class="text-[11px] text-slate-400 font-mono truncate">→ ${a.entity_id}</div>
                <div class="flex items-center gap-2">
                    <span id="stato-${_chiaveStato(a.entity_id)}" class="text-[10px] font-semibold text-slate-500">${_testoStato(a.entity_id)}</span>
                    ${a.room ? `<span class="text-[10px] text-slate-500">📍 ${a.room}</span>` : ''}
                </div>
            </div>
        `).join('');
        safeCreateIcons();
        caricaStatiIniziali();
    } catch(e) { console.error('loadAliases:', e); }
}

// Gli stati di partenza. Senza, le schede restano vuote finche' in casa
// non cambia qualcosa: gli eventi raccontano le differenze, non la
// situazione. Lato server questa chiamata legge dalla cache quando la
// connessione agli eventi e' viva, quindi non tocca la rete.
async function caricaStatiIniziali() {
    try {
        const res = await fetch('/api/ha/entities', { headers: getAuthHeaders() });
        if (!res.ok) return;
        const dati = await res.json();
        if (dati.error) return;
        Object.values(dati.groups || {}).forEach(gruppo => {
            gruppo.forEach(e => aggiornaStatoCasa({
                entity_id: e.entity_id,
                stato: e.state,
                nome: e.friendly_name,
            }));
        });
    } catch (e) {
        console.warn('Stati iniziali non disponibili:', e);
    }
}

// Variabile globale per tenere tutte le entità HA caricate
let _haEntitiesCache = null;

async function discoverHAEntities() {
    const btn = document.getElementById('btn-discover');
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Caricamento...`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/ha/entities', { headers: getAuthHeaders() });
        const data = await res.json();

        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-4 h-4"></i> Aggiorna`;
        safeCreateIcons();

        if (data.error) {
            document.getElementById('ha-entities-groups').innerHTML = `
                <div class="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">
                    ❌ <strong>Home Assistant non raggiungibile</strong><br>${data.message || 'Verifica le impostazioni nella tab ⚙️'}
                </div>`;
            document.getElementById('ha-entities-section').style.display = 'block';
            return;
        }

        _haEntitiesCache = data;
        renderHAEntities(data);

        // Mostra filtro
        document.getElementById('alias-filter-row').style.display = 'flex';
        document.getElementById('alias-filter-count').textContent = `${data.total} dispositivi trovati`;
        document.getElementById('ha-entities-section').style.display = 'block';

    } catch(e) {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="scan-search" class="w-4 h-4"></i> Scopri Dispositivi HA`;
        safeCreateIcons();
        document.getElementById('ha-entities-groups').innerHTML = `<div class="text-xs text-rose-400">Errore: ${e.message}</div>`;
        document.getElementById('ha-entities-section').style.display = 'block';
    }
}

function renderHAEntities(data, filterText = '') {
    const container = document.getElementById('ha-entities-groups');
    const lc = filterText.toLowerCase();

    let html = '';
    let visibleCount = 0;

    for (const entities of Object.values(data.groups)) {
        const filtered = filterText ? entities.filter(e =>
            e.friendly_name.toLowerCase().includes(lc) ||
            e.entity_id.toLowerCase().includes(lc) ||
            (e.alias || '').toLowerCase().includes(lc)
        ) : entities;

        if (!filtered.length) continue;
        visibleCount += filtered.length;

        html += `
            <div class="rounded-xl border border-slate-800 overflow-hidden">
                <div class="bg-slate-800/60 px-4 py-2 text-xs font-semibold text-slate-300 flex items-center justify-between">
                    <span>${entities[0].domain_label}</span>
                    <span class="text-slate-500">${filtered.length} dispositivi</span>
                </div>
                <div class="divide-y divide-slate-800/60">
                    ${filtered.map(e => `
                        <div class="flex items-center justify-between px-4 py-2.5 hover:bg-slate-800/30 transition group">
                            <div class="flex-1 min-w-0">
                                <div class="text-xs font-medium text-slate-200 truncate">${e.friendly_name}</div>
                                <div class="text-[11px] text-slate-500 font-mono truncate">${e.entity_id}</div>
                            </div>
                            <div class="flex items-center gap-2 ml-3 shrink-0">
                                <span class="text-[10px] px-2 py-0.5 rounded-full ${getStateClass(e.state)}">${e.state}</span>
                                ${e.alias
                                    ? `<span class="text-[10px] text-indigo-400 font-semibold bg-indigo-950/60 border border-indigo-800 px-2 py-0.5 rounded-full">"${e.alias}"</span>`
                                    : ''}
                                ${e.controllable
                                    ? `<button onclick="openAliasModalForEntity('${e.entity_id}', '${e.friendly_name.replace(/'/g,"\\'")}', '${e.alias || ''}')"
                                        class="px-2.5 py-1 rounded-lg text-[11px] font-semibold transition border
                                        ${e.alias
                                            ? 'bg-slate-800 border-slate-700 text-slate-400 hover:border-indigo-500 hover:text-indigo-300'
                                            : 'bg-indigo-600/20 border-indigo-600/40 text-indigo-300 hover:bg-indigo-600 hover:text-white'}">
                                        ${e.alias ? '✏️ Modifica' : '+ Alias'}
                                      </button>`
                                    : '<span class="text-[10px] text-slate-600">sola lettura</span>'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>`;
    }

    container.innerHTML = html || `<p class="text-xs text-slate-500 text-center py-4">Nessun risultato per "${filterText}"</p>`;
    if (filterText) {
        document.getElementById('alias-filter-count').textContent = `${visibleCount} trovati`;
    }
}

function getStateClass(state) {
    if (['on', 'home', 'open', 'playing', 'unlocked'].includes(state))
        return 'bg-emerald-950/60 text-emerald-400 border border-emerald-800';
    if (['off', 'away', 'closed', 'paused', 'locked'].includes(state))
        return 'bg-slate-800 text-slate-500 border border-slate-700';
    if (['unavailable', 'unknown'].includes(state))
        return 'bg-rose-950/40 text-rose-500 border border-rose-900';
    return 'bg-slate-800 text-slate-400 border border-slate-700';
}

function filterEntities(text) {
    if (_haEntitiesCache) renderHAEntities(_haEntitiesCache, text);
}

function openAliasModalForEntity(entityId, friendlyName, currentAlias) {
    showModal(`
        <h3 class="font-bold text-sm text-slate-100 mb-1">Assegna Nome Naturale</h3>
        <p class="text-xs text-slate-400 mb-4">Assegna un nome che Shinra riconoscerà nei comandi vocali.</p>

        <div class="space-y-1 mb-4 p-3 bg-slate-950/60 rounded-xl border border-slate-800">
            <div class="text-[11px] text-slate-500">Dispositivo selezionato</div>
            <div class="text-xs font-bold text-slate-100">${friendlyName}</div>
            <div class="text-[11px] font-mono text-indigo-400">${entityId}</div>
        </div>

        <label class="text-xs text-slate-400 block mb-1">Nome naturale (come lo dirai ad Alessio)</label>
        <input type="text" id="new-a-alias" value="${currentAlias}"
            placeholder='es. "lampadario del salotto", "tv", "condizionatore"'
            class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 focus:outline-none focus:border-indigo-500">

        <label class="text-xs text-slate-400 block mb-1">Stanza (opzionale)</label>
        <input type="text" id="new-a-room"
            placeholder='es. Salotto, Camera, Cucina'
            class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-4 focus:outline-none focus:border-indigo-500">

        <input type="hidden" id="new-a-entity" value="${entityId}">

        <div class="flex justify-end gap-2">
            <button onclick="closeModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300 hover:bg-slate-700">Annulla</button>
            <button onclick="saveNewAlias()" class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold">Salva Alias</button>
        </div>
    `);
    setTimeout(() => document.getElementById('new-a-alias')?.focus(), 100);
}

function openAddAliasModal() {
    openAliasModalForEntity('', '', '');
}

async function saveNewAlias() {
    const alias = document.getElementById('new-a-alias').value.trim();
    const entity_id = document.getElementById('new-a-entity').value.trim();
    const room = document.getElementById('new-a-room').value.trim();
    if (!alias || !entity_id) {
        document.getElementById('new-a-alias').focus();
        return;
    }
    await fetch('/api/aliases', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ alias, entity_id, room })
    });
    closeModal();
    loadAliases();
    // Aggiorna il badge dell'entità nella lista HA senza ricaricare tutto
    if (_haEntitiesCache) {
        for (const entities of Object.values(_haEntitiesCache.groups)) {
            const e = entities.find(x => x.entity_id === entity_id);
            if (e) e.alias = alias;
        }
        renderHAEntities(_haEntitiesCache, document.getElementById('alias-filter-input')?.value || '');
    }
}

async function deleteAlias(id) {
    if (!confirm('Rimuovere questo alias?')) return;
    await fetch(`/api/aliases/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadAliases();
}
