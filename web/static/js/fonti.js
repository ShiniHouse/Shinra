// ==================== SOURCES CATALOG & BULK CONTROLS ====================
const SOURCES_CATALOG = [
    {
        category: '📰 Notizie Italia',
        items: [
            {
                id: 'corriere',
                name: 'Corriere della Sera',
                cat: 'italia',
                url: 'https://www.corriere.it/rss/homepage.xml',
            },
            {
                id: 'repubblica',
                name: 'La Repubblica',
                cat: 'italia',
                url: 'https://www.repubblica.it/rss/homepage/rss2.0.xml',
            },
            { id: 'skytg24', name: 'Sky TG24', cat: 'italia', url: 'https://tg24.sky.it/feed/rss' },
            { id: 'lastampa', name: 'La Stampa', cat: 'italia', url: 'https://www.lastampa.it/rss.xml' },
            {
                id: 'ilmessaggero',
                name: 'Il Messaggero',
                cat: 'italia',
                url: 'https://www.ilmessaggero.it/rss/home.xml',
            },
        ],
    },
    {
        category: '💹 Economia & Finanza',
        items: [
            {
                id: 'sole24ore',
                name: 'Il Sole 24 Ore',
                cat: 'economia',
                url: 'https://www.ilsole24ore.com/rss/home.xml',
            },
            {
                id: 'milanofinanza',
                name: 'Milano Finanza',
                cat: 'economia',
                url: 'https://www.milanofinanza.it/rss',
            },
            {
                id: 'reuters_biz',
                name: 'Reuters Business',
                cat: 'economia',
                url: 'https://feeds.reuters.com/reuters/businessNews',
            },
        ],
    },
    {
        category: '🖥️ Tecnologia & AI',
        items: [
            { id: 'wired_it', name: 'Wired Italia', cat: 'tecnologia', url: 'https://www.wired.it/feed/rss' },
            {
                id: 'tomshw',
                name: "Tom's Hardware Italia",
                cat: 'tecnologia',
                url: 'https://www.tomshw.it/feed',
            },
            {
                id: 'hwupgrade',
                name: 'Hardware Upgrade',
                cat: 'tecnologia',
                url: 'https://www.hwupgrade.it/rss/news.xml',
            },
            { id: 'techcrunch', name: 'TechCrunch', cat: 'tecnologia', url: 'https://techcrunch.com/feed/' },
            {
                id: 'theverge',
                name: 'The Verge',
                cat: 'tecnologia',
                url: 'https://www.theverge.com/rss/index.xml',
            },
            { id: 'hn', name: 'Hacker News Top', cat: 'tecnologia', url: 'https://hnrss.org/frontpage' },
        ],
    },
    {
        category: '🌍 Notizie Internazionali',
        items: [
            {
                id: 'bbc_world',
                name: 'BBC World News',
                cat: 'mondo',
                url: 'http://feeds.bbci.co.uk/news/world/rss.xml',
            },
            {
                id: 'guardian',
                name: 'The Guardian',
                cat: 'mondo',
                url: 'https://www.theguardian.com/world/rss',
            },
            {
                id: 'reuters_top',
                name: 'Reuters Top News',
                cat: 'mondo',
                url: 'https://feeds.reuters.com/reuters/topNews',
            },
        ],
    },
    {
        category: '🔬 Scienza & Spazio',
        items: [
            {
                id: 'nasa',
                name: 'NASA Breaking News',
                cat: 'scienza',
                url: 'https://www.nasa.gov/rss/dyn/breaking_news.rss',
            },
            {
                id: 'lescienze',
                name: 'Le Scienze',
                cat: 'scienza',
                url: 'https://www.lescienze.it/rss/rss.xml',
            },
            {
                id: 'natgeo',
                name: 'National Geographic IT',
                cat: 'scienza',
                url: 'https://www.nationalgeographic.it/feed',
            },
            {
                id: 'sciencedaily',
                name: 'Science Daily',
                cat: 'scienza',
                url: 'https://www.sciencedaily.com/rss/top.xml',
            },
        ],
    },
    {
        category: '🏠 Smart Home & Domotica',
        items: [
            {
                id: 'smarthome_it',
                name: 'Domotica Plus',
                cat: 'domotica',
                url: 'https://www.domoticaplus.it/feed/',
            },
            {
                id: 'ha_blog',
                name: 'Home Assistant Blog',
                cat: 'domotica',
                url: 'https://www.home-assistant.io/atom.xml',
            },
        ],
    },
];

async function bulkToggleSources(enable) {
    try {
        const res = await fetch('/api/sources/bulk-toggle', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ enabled: enable }),
        });
        if (res.ok) {
            await loadSources();
        }
    } catch (e) {
        console.error('bulkToggleSources error:', e);
    }
}

async function loadSources() {
    try {
        const res = await fetch('/api/sources', { headers: getAuthHeaders() });
        const items = await res.json();
        const container = document.getElementById('sources-list');

        if (!items.length) {
            container.innerHTML = _html`<p class="text-xs text-slate-500 col-span-2 py-3 text-center">Nessuna fonte attiva. Aggiungine dal catalogo qui sotto o clicca "Attiva Tutte".</p>`;
        } else {
            container.innerHTML = _html`${items.map((s) => {
                const isEnabled = s.enabled !== false;
                return _html`
                <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-start gap-2 group hover:border-slate-700 transition">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <h4 class="font-semibold text-xs text-slate-200">${s.name}</h4>
                            <span class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-400">${s.category}</span>
                            <span class="px-1.5 py-0.2 text-[9px] rounded font-mono ${isEnabled ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-rose-950 text-rose-300 border border-rose-800'}">${isEnabled ? 'Attivo' : 'Disattivato'}</span>
                        </div>
                        <p class="text-[11px] text-slate-500 truncate mt-1">${s.url}</p>
                    </div>
                    <div class="flex items-center gap-1 shrink-0">
                        <button onclick="toggleSingleSource(${_grezzo(_perAttributoJs(s.id))}, ${!isEnabled})" class="text-slate-500 hover:text-indigo-400 p-1 transition" title="${isEnabled ? 'Disattiva' : 'Attiva'}">
                            <i data-lucide="${isEnabled ? 'toggle-right' : 'toggle-left'}" class="w-4 h-4 ${isEnabled ? 'text-indigo-400' : 'text-slate-600'}"></i>
                        </button>
                        <button onclick="deleteSource(${_grezzo(_perAttributoJs(s.id))})" class="text-slate-600 hover:text-rose-400 p-1 opacity-0 group-hover:opacity-100 transition" title="Elimina fonte">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>`;
            })}`;
        }
        safeCreateIcons();

        // Rende il catalogo con stato e fisarmonica
        const activeUrls = new Set(items.filter((s) => s.enabled !== false).map((s) => s.url));
        renderSourcesCatalog(activeUrls);
    } catch (e) {
        console.error('loadSources:', e);
    }
}

async function toggleSingleSource(sourceId, enable) {
    const res = await fetch('/api/sources', { headers: getAuthHeaders() });
    const items = await res.json();
    const source = items.find((s) => s.id === sourceId);
    if (source) {
        source.enabled = enable;
        await fetch('/api/sources', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(source),
        });
        await loadSources();
    }
}

let _sourcesAccordionState = {};

function toggleSourceCategory(idx) {
    _sourcesAccordionState[idx] = !_sourcesAccordionState[idx];
    const content = document.getElementById(`src-cat-content-${idx}`);
    const chevron = document.getElementById(`src-cat-chevron-${idx}`);
    if (content) content.classList.toggle('hidden', !_sourcesAccordionState[idx]);
    if (chevron) chevron.style.transform = _sourcesAccordionState[idx] ? 'rotate(180deg)' : 'rotate(0deg)';
}

function renderSourcesCatalog(activeUrls) {
    const container = document.getElementById('sources-catalog');
    if (!container) return;

    container.innerHTML = _html`${SOURCES_CATALOG.map((group, idx) => {
        const activeCount = group.items.filter((s) => activeUrls.has(s.url)).length;
        const total = group.items.length;
        if (_sourcesAccordionState[idx] === undefined) _sourcesAccordionState[idx] = idx === 0;
        const isOpen = Boolean(_sourcesAccordionState[idx]);

        return _html`
        <div class="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-sm">
            <button type="button" onclick="toggleSourceCategory(${idx})" class="w-full bg-slate-800/40 hover:bg-slate-800/70 px-4 py-3 text-xs font-semibold text-slate-200 flex items-center justify-between transition">
                <div class="flex items-center gap-2">
                    <span>${group.category}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] ${activeCount > 0 ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800' : 'bg-slate-800 text-slate-400'}">${activeCount}/${total} attive</span>
                </div>
                <i data-lucide="chevron-down" id="src-cat-chevron-${idx}" class="w-4 h-4 text-slate-400 transition-transform duration-200" style="transform: ${isOpen ? 'rotate(180deg)' : 'rotate(0deg)'}"></i>
            </button>
            <div id="src-cat-content-${idx}" class="${isOpen ? '' : 'hidden'} divide-y divide-slate-800/60">
                ${group.items.map((src) => {
                    const added = activeUrls.has(src.url);
                    return _html`
                    <div class="flex items-center justify-between px-4 py-2.5 hover:bg-slate-800/20 transition">
                        <div class="flex-1 min-w-0">
                            <span class="text-xs font-medium text-slate-200">${src.name}</span>
                            <span class="text-[11px] text-slate-500 ml-2 font-mono hidden sm:inline">${src.url.replace('https://', '').split('/')[0]}</span>
                        </div>
                        ${
                            added
                                ? _html`<span class="text-[11px] text-emerald-400 font-semibold px-2.5 py-1 bg-emerald-950/40 border border-emerald-800 rounded-full flex items-center gap-1">✓ Attiva</span>`
                                : _html`<button onclick="addCatalogSource(${_grezzo(_perAttributoJs(src.id))},${_grezzo(_perAttributoJs(src.name))},${_grezzo(_perAttributoJs(src.cat))},${_grezzo(_perAttributoJs(src.url))})"
                                class="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-indigo-600/20 border border-indigo-600/40 text-indigo-300 hover:bg-indigo-600 hover:text-white transition">
                                + Aggiungi
                               </button>`
                        }
                    </div>`;
                })}
            </div>
        </div>`;
    })}`;
    safeCreateIcons();
}

async function addCatalogSource(id, name, category, url) {
    await fetch('/api/sources', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ id, name, category, url, enabled: true }),
    });
    loadSources();
}

function openAddSourceModal() {
    showModal(_html`
        <h3 class="font-bold text-sm text-slate-100 mb-1">Aggiungi URL RSS Personalizzato</h3>
        <p class="text-xs text-slate-400 mb-4">Inserisci l'URL di qualsiasi feed RSS che vuoi aggiungere.</p>
        <label class="text-xs text-slate-400 block mb-1">Nome Fonte</label>
        <input type="text" id="new-s-name" placeholder="es. Il Fatto Quotidiano" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 focus:outline-none focus:border-indigo-500">
        <label class="text-xs text-slate-400 block mb-1">Categoria</label>
        <input type="text" id="new-s-cat" placeholder="es. politica, sport, cultura" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 focus:outline-none focus:border-indigo-500">
        <label class="text-xs text-slate-400 block mb-1">URL Feed RSS</label>
        <input type="url" id="new-s-url" placeholder="https://..." class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-4 focus:outline-none focus:border-indigo-500">
        <div class="flex justify-end gap-2">
            <button onclick="closeModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300 hover:bg-slate-700">Annulla</button>
            <button onclick="saveNewSource()" class="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold">Salva Fonte</button>
        </div>
    `);
    setTimeout(() => document.getElementById('new-s-name')?.focus(), 100);
}

async function saveNewSource() {
    const name = document.getElementById('new-s-name').value.trim();
    const category = document.getElementById('new-s-cat').value.trim() || 'generale';
    const url = document.getElementById('new-s-url').value.trim();
    if (!name || !url) return;
    await fetch('/api/sources', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ name, category, url, enabled: true }),
    });
    closeModal();
    loadSources();
}

async function deleteSource(id) {
    if (!confirm('Rimuovere questa fonte?')) return;
    await fetch(`/api/sources/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadSources();
}
