// ==================== VISUAL FLOW CANVAS (STILE VISIO / NODE-RED) ====================
let _canvasState = {
    id: '',
    name: '',
    icon: 'workflow',
    description: '',
    trigger_phrases: [],
    nodes: [],
    edges: [],
    isDraggingNode: null,
    dragOffset: { x: 0, y: 0 },
    connectingSourceId: null
};

function openModularModeBuilder(existingId = null) {
    let mode = { id: '', name: '', icon: 'workflow', description: '', trigger_phrases: [], nodes: [], edges: [] };
    if (existingId) {
        const found = _allModesCache.find(m => m.id === existingId);
        if (found) mode = JSON.parse(JSON.stringify(found));
    }

    _canvasState.id = mode.id || '';
    _canvasState.name = mode.name || (existingId ? '' : 'Nuova Routine');
    _canvasState.icon = mode.icon || 'workflow';
    _canvasState.description = mode.description || '';
    _canvasState.trigger_phrases = mode.trigger_phrases || [];

    // Se la routine ha già nodi e archi grafici carichiamoli, altrimenti convertiamo le vecchie actions in grafo
    if (mode.nodes && mode.nodes.length > 0) {
        _canvasState.nodes = mode.nodes;
        _canvasState.edges = mode.edges || [];
    } else if (mode.actions && mode.actions.length > 0) {
        // Auto-conversione in layout orizzontale a nodi
        const nTrigger = { id: 'node_trig', type: 'trigger', x: 40, y: 140, data: { phrases: mode.trigger_phrases || [] } };
        _canvasState.nodes = [nTrigger];
        _canvasState.edges = [];
        let prevId = 'node_trig';

        mode.actions.forEach((act, idx) => {
            const nId = `node_${idx + 1}`;
            _canvasState.nodes.push({
                id: nId,
                type: act.type || 'ha_device',
                x: 40 + (idx + 1) * 270,
                y: 140,
                data: {
                    entity_id: act.entity_id || act.data?.entity_id || '',
                    action: act.action || act.service || 'turn_on',
                    seconds: act.seconds || act.delay_seconds || 5,
                    message: act.message || ''
                }
            });
            _canvasState.edges.push({ from: prevId, to: nId });
            prevId = nId;
        });
    } else {
        // Routine vuota predefinita con nodo Trigger
        _canvasState.nodes = [
            { id: 'node_trig', type: 'trigger', x: 50, y: 140, data: { phrases: ['modalità ' + (_canvasState.name.toLowerCase() || 'relax')] } },
            { id: 'node_ha1', type: 'ha_device', x: 340, y: 140, data: { entity_id: '', action: 'turn_on' } }
        ];
        _canvasState.edges = [
            { from: 'node_trig', to: 'node_ha1' }
        ];
    }

    renderFlowCanvasModal();
}

function renderFlowCanvasModal() {
    const triggersStr = _canvasState.trigger_phrases.join(', ');

    showModal(`
        <!-- La chiusura sta fuori dalla finestra, nell'angolo.
             Stava in fila dopo «Salva», e una X accanto a un pulsante
             di salvataggio non e' una terza azione fra cui scegliere:
             e' l'uscita, e va dove la cercano le mani. -->
        <button type="button" onclick="closeModal()" title="Chiudi l'editor"
                class="absolute -top-3.5 -right-3.5 z-50 w-9 h-9 rounded-full bg-slate-800 border border-slate-700 text-slate-300 hover:bg-rose-600 hover:text-white hover:border-rose-500 shadow-xl flex items-center justify-center transition">
            <i data-lucide="x" class="w-4 h-4"></i>
        </button>
        <div class="flex flex-col h-[85vh] w-full select-none">
            <!-- Top Control Toolbar -->
            <div class="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-900/90 border-b border-slate-800 rounded-t-2xl">
                <!-- Routine Info -->
                <div class="flex items-center gap-2 flex-wrap flex-1 min-w-[280px]">
                    <div class="w-8 h-8 rounded-lg bg-indigo-600/40 text-indigo-300 flex items-center justify-center font-bold">
                        <i data-lucide="workflow" class="w-4 h-4"></i>
                    </div>
                    <input type="text" id="cv-name" value="${_canvasState.name || ''}" placeholder="Nome Routine (es. Cinema, Notte)" oninput="_canvasState.name = this.value" class="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-100 font-bold focus:outline-none focus:border-indigo-500 w-40">
                    <input type="text" id="cv-triggers" value="${triggersStr}" placeholder="Frasi vocali: es. modalità cinema, relax" oninput="_canvasState.trigger_phrases = this.value.split(',').map(s=>s.trim()).filter(s=>s.length>0)" class="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 flex-1 min-w-[180px]">
                </div>

                <!-- I blocchi da aggiungere. La parola «Aggiungi»
                     davanti costa due centimetri e toglie la domanda:
                     cinque pulsanti colorati in fila, senza, si
                     leggono come cinque comandi da dare adesso. -->
                <div class="flex items-center gap-1.5 flex-wrap">
                    <span class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mr-0.5">Aggiungi</span>
                    <button type="button" onclick="addCanvasNode('ha_device')" class="px-2.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-200 hover:text-white rounded-lg text-xs font-semibold border border-indigo-500/40 transition flex items-center gap-1">
                        + 💡 Dispositivo HA
                    </button>
                    <button type="button" onclick="addCanvasNode('delay')" class="px-2.5 py-1.5 bg-amber-600/30 hover:bg-amber-600 text-amber-200 hover:text-white rounded-lg text-xs font-semibold border border-amber-500/40 transition flex items-center gap-1">
                        + ⏱️ Ritardo (Pausa)
                    </button>
                    <button type="button" onclick="addCanvasNode('tts')" class="px-2.5 py-1.5 bg-emerald-600/30 hover:bg-emerald-600 text-emerald-200 hover:text-white rounded-lg text-xs font-semibold border border-emerald-500/40 transition flex items-center gap-1">
                        + 🗣️ Voce Shinra
                    </button>
                    <button type="button" onclick="addCanvasNode('condizione')" class="px-2.5 py-1.5 bg-violet-600/30 hover:bg-violet-600 text-violet-200 hover:text-white rounded-lg text-xs font-semibold border border-violet-500/40 transition flex items-center gap-1">
                        + 🔀 Condizione
                    </button>
                    <button type="button" onclick="addCanvasNode('notifica')" class="px-2.5 py-1.5 bg-sky-600/30 hover:bg-sky-600 text-sky-200 hover:text-white rounded-lg text-xs font-semibold border border-sky-500/40 transition flex items-center gap-1">
                        + 🔔 Notifica
                    </button>
                </div>

                <!-- Le due azioni vere, e si vede quale delle due
                     chiude il lavoro: «Prova» e' un aiuto, «Salva» e'
                     la conclusione. Prima erano due pulsanti pieni
                     affiancati, entrambi col loro colore acceso, e
                     sembravano alternative alla pari. -->
                <div class="flex items-center gap-2 shrink-0">
                    <button type="button" onclick="simulateCanvasFlow()" id="btn-sim-canvas" class="px-3 py-1.5 bg-violet-600/20 hover:bg-violet-600 text-violet-200 hover:text-white border border-violet-500/40 rounded-lg text-xs font-semibold transition flex items-center gap-1.5">
                        ▶️ Prova il flusso
                    </button>
                    <button type="button" onclick="saveCanvasMode()" class="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow transition flex items-center gap-1.5">
                        💾 Salva
                    </button>
                </div>
            </div>

            <!-- Flow Canvas Viewport (Visio 2D Grid) -->
            <div id="flow-canvas" class="tela-flusso relative flex-1 w-full overflow-hidden cursor-default">
                <!-- SVG Cables Layer -->
                <svg id="flow-svg-layer" class="absolute inset-0 w-full h-full pointer-events-none z-10" style="overflow: visible;">
                    <defs>
                        <linearGradient id="wireGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stop-color="#6366f1" />
                            <stop offset="100%" stop-color="#a855f7" />
                        </linearGradient>
                    </defs>
                </svg>

                <!-- DOM Nodes Layer -->
                <div id="flow-nodes-container" class="absolute inset-0 z-20 pointer-events-auto">
                    <!-- Nodi generati dinamicamente -->
                </div>
            </div>

            <!-- Canvas Footer Help -->
            <div class="px-4 py-2 bg-slate-900/90 border-t border-slate-800 rounded-b-2xl text-[11px] text-slate-400 flex items-center justify-between">
                <span class="flex items-center gap-2">
                    <span>💡 <strong>Suggerimento:</strong> Trascina la porta <strong>destra (●)</strong> di un blocco verso la porta <strong>sinistra (●)</strong> di un altro per collegarli! Trascina i nodi per spostarli.</span>
                </span>
                <span class="text-slate-500 font-mono text-[10px]" id="canvas-stats">Nodi: 0 | Connessioni: 0</span>
            </div>
        </div>
    `, true);

    initCanvasInteractions();
    renderCanvasElements();
}

function initCanvasInteractions() {
    const canvas = document.getElementById('flow-canvas');
    if (!canvas) return;

    // Global Mouse Move su Canvas per Drag dei Nodi e Disegno Cavo Attivo
    canvas.onmousemove = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // 1. Dragging Node
        if (_canvasState.isDraggingNode) {
            const node = _canvasState.nodes.find(n => n.id === _canvasState.isDraggingNode);
            if (node) {
                node.x = Math.max(10, Math.min(rect.width - 240, mouseX - _canvasState.dragOffset.x));
                node.y = Math.max(10, Math.min(rect.height - 180, mouseY - _canvasState.dragOffset.y));
                const el = document.getElementById(`c-node-${node.id}`);
                if (el) {
                    el.style.left = `${node.x}px`;
                    el.style.top = `${node.y}px`;
                }
                renderCanvasWires();
            }
        }

        // 2. Connecting Wire Draft
        if (_canvasState.connectingSourceId) {
            renderCanvasWires({ x: mouseX, y: mouseY });
        }
    };

    // Global Mouse Up su Canvas
    canvas.onmouseup = () => {
        _canvasState.isDraggingNode = null;
        if (_canvasState.connectingSourceId) {
            _canvasState.connectingSourceId = null;
            renderCanvasWires();
        }
    };
}

function renderCanvasElements() {
    const container = document.getElementById('flow-nodes-container');
    if (!container) return;

    // Costruisce opzioni dispositivi per select
    const aliases = (typeof data_store !== 'undefined' ? [] : (_haEntitiesCache ? Object.values(_haEntitiesCache.groups).flat() : []));

    container.innerHTML = _canvasState.nodes.map(node => {
        let headerBg = 'from-indigo-600 to-violet-600';
        let icon = 'workflow';
        let typeLabel = 'Modulo';
        let bodyHtml = '';

        if (node.type === 'trigger') {
            headerBg = 'from-amber-600 to-orange-600';
            icon = 'zap';
            const t = node.data.trigger || { tipo: 'voce' };
            const etichette = {
                voce: '⚡ Innesco Vocale', orario: '🕒 A un orario', alba: '🌅 All\'alba',
                tramonto: '🌇 Al tramonto', stato: '📈 Su un valore', evento: '📡 Su un evento'
            };
            typeLabel = etichette[t.tipo] || etichette.voce;
            const ph = (node.data.phrases || []).join(', ');
            bodyHtml = `
                <div class="space-y-2 text-xs">
                    <select onchange="setTipoInnesco('${node.id}', this.value)" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                        <option value="voce" ${t.tipo === 'voce' ? 'selected' : ''}>Quando lo chiedo a voce</option>
                        <option value="orario" ${t.tipo === 'orario' ? 'selected' : ''}>A un orario</option>
                        <option value="alba" ${t.tipo === 'alba' ? 'selected' : ''}>All'alba</option>
                        <option value="tramonto" ${t.tipo === 'tramonto' ? 'selected' : ''}>Al tramonto</option>
                        <option value="stato" ${t.tipo === 'stato' ? 'selected' : ''}>Quando un valore supera una soglia</option>
                        <option value="evento" ${t.tipo === 'evento' ? 'selected' : ''}>Su un evento della casa</option>
                    </select>
                    ${t.tipo === 'voce' ? `
                        <label class="text-[10px] text-slate-400 font-semibold block">Frasi di Attivazione:</label>
                        <input type="text" value="${ph}" oninput="updateNodeData('${node.id}', 'phrases', this.value.split(',').map(s=>s.trim()))" placeholder="es. attiva cinema, cinema" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-amber-500">
                    ` : ''}
                    ${t.tipo === 'orario' ? `
                        <input type="time" value="${t.ora || '07:00'}" onchange="setDatoInnesco('${node.id}', 'ora', this.value)" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                        <div class="flex gap-0.5">
                            ${['L','M','M','G','V','S','D'].map((g, i) => `
                                <button type="button" onclick="alternaGiornoInnesco('${node.id}', ${i})" class="flex-1 py-1 rounded text-[10px] font-bold ${(t.giorni || []).includes(i) ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-400'}">${g}</button>
                            `).join('')}
                        </div>
                        <p class="text-[10px] text-slate-500">Nessun giorno scelto vuol dire tutti i giorni.</p>
                    ` : ''}
                    ${(t.tipo === 'alba' || t.tipo === 'tramonto') ? `
                        <div class="flex items-center gap-2">
                            <input type="number" value="${t.scarto_minuti || 0}" onchange="setDatoInnesco('${node.id}', 'scarto_minuti', parseInt(this.value)||0)" class="w-20 bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 text-center">
                            <span class="text-[11px] text-slate-400">minuti di scarto (negativi = prima)</span>
                        </div>
                    ` : ''}
                    ${t.tipo === 'stato' ? `
                        <input type="text" value="${t.entity_id || ''}" oninput="setDatoInnesco('${node.id}', 'entity_id', this.value)" placeholder="es. sensor.temperatura_salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <select onchange="setDatoInnesco('${node.id}', 'confronto', this.value)" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                            <option value="attraversa_sotto" ${t.confronto === 'attraversa_sotto' ? 'selected' : ''}>quando scende sotto</option>
                            <option value="attraversa_sopra" ${t.confronto === 'attraversa_sopra' ? 'selected' : ''}>quando sale sopra</option>
                            <option value="diventa" ${t.confronto === 'diventa' ? 'selected' : ''}>quando diventa</option>
                        </select>
                        <input type="text" value="${t.valore !== undefined ? t.valore : ''}" oninput="setDatoInnesco('${node.id}', 'valore', this.value)" placeholder="es. 15" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <p class="text-[10px] text-slate-500 leading-snug">Scatta nel momento in cui la soglia viene attraversata, non a ogni lettura che sta di là.</p>
                    ` : ''}
                    ${t.tipo === 'evento' ? `
                        <input type="text" value="${t.evento || ''}" oninput="setDatoInnesco('${node.id}', 'evento', this.value)" placeholder="es. casa.vuota" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <input type="text" value="${t.entity_id || ''}" oninput="setDatoInnesco('${node.id}', 'entity_id', this.value)" placeholder="solo per questa entità (facoltativo)" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    ` : ''}
                    ${t.tipo !== 'voce' ? `
                        <p class="text-[10px] text-amber-400 leading-snug">Al salvataggio questa routine parte da sola: diventa una regola del motore delle automazioni. Per fermarla, togli l'innesco e risalva.</p>
                    ` : ''}
                </div>
            `;
        } else if (node.type === 'ha_device' || node.type === 'ha_service') {
            headerBg = 'from-indigo-600 to-blue-600';
            icon = 'power';
            typeLabel = '💡 Dispositivo HA';
            bodyHtml = `
                <div class="space-y-2 text-xs">
                    <div>
                        <label class="text-[10px] text-slate-400 font-semibold block mb-0.5">Dispositivo / Alias:</label>
                        <input type="text" value="${node.data.entity_id || ''}" oninput="updateNodeData('${node.id}', 'entity_id', this.value)" placeholder="es. light.salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500">
                    </div>
                    <div class="flex gap-1.5">
                        <select onchange="updateNodeData('${node.id}', 'action', this.value)" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                            <option value="turn_on" ${node.data.action === 'turn_on' ? 'selected' : ''}>Accendi</option>
                            <option value="turn_off" ${node.data.action === 'turn_off' ? 'selected' : ''}>Spegni</option>
                            <option value="toggle" ${node.data.action === 'toggle' ? 'selected' : ''}>Inverti</option>
                        </select>
                    </div>
                </div>
            `;
        } else if (node.type === 'delay') {
            headerBg = 'from-amber-600 to-yellow-600';
            icon = 'clock';
            typeLabel = '⏱️ Ritardo (Pausa)';
            bodyHtml = `
                <div class="space-y-2 text-xs">
                    <label class="text-[10px] text-slate-400 font-semibold block">Attesa prima del prossimo step:</label>
                    <div class="flex items-center gap-2">
                        <input type="number" min="1" max="300" value="${node.data.seconds || 5}" oninput="updateNodeData('${node.id}', 'seconds', parseInt(this.value)||1)" class="w-20 bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-bold text-center">
                        <span class="text-xs text-slate-400">secondi</span>
                    </div>
                    <div class="flex gap-1">
                        <button type="button" onclick="setQuickDelay('${node.id}', 3)" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">3s</button>
                        <button type="button" onclick="setQuickDelay('${node.id}', 5)" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">5s</button>
                        <button type="button" onclick="setQuickDelay('${node.id}', 10)" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">10s</button>
                        <button type="button" onclick="setQuickDelay('${node.id}', 30)" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">30s</button>
                    </div>
                </div>
            `;
        } else if (node.type === 'tts') {
            headerBg = 'from-emerald-600 to-teal-600';
            icon = 'message-circle';
            typeLabel = '🗣️ Annuncio Vocale';
            bodyHtml = `
                <div class="space-y-1 text-xs">
                    <label class="text-[10px] text-slate-400 font-semibold block">Frase da pronunciare:</label>
                    <textarea rows="2" oninput="updateNodeData('${node.id}', 'message', this.value)" placeholder="es. Luci regolate, buona visione!" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500">${node.data.message || ''}</textarea>
                </div>
            `;
        } else if (node.type === 'condizione') {
            headerBg = 'from-violet-600 to-fuchsia-600';
            icon = 'git-branch';
            typeLabel = '🔀 Condizione';
            const c = node.data.condizione || {};
            bodyHtml = `
                <div class="space-y-2 text-xs">
                    <select onchange="setTipoCondizione('${node.id}', this.value)" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                        <option value="presenza" ${c.tipo === 'presenza' ? 'selected' : ''}>C'è qualcuno in casa</option>
                        <option value="stato_entita" ${c.tipo === 'stato_entita' ? 'selected' : ''}>Un dispositivo è in uno stato</option>
                        <option value="fra_le_ore" ${c.tipo === 'fra_le_ore' ? 'selected' : ''}>Siamo in una fascia oraria</option>
                        <option value="giorni" ${c.tipo === 'giorni' ? 'selected' : ''}>È uno di certi giorni</option>
                    </select>
                    ${c.tipo === 'stato_entita' ? `
                        <input type="text" value="${c.entity_id || ''}" oninput="setDatoCondizione('${node.id}', 'entity_id', this.value)" placeholder="es. light.salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <input type="text" value="${c.stato || ''}" oninput="setDatoCondizione('${node.id}', 'stato', this.value)" placeholder="stato atteso, es. on" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    ` : ''}
                    ${c.tipo === 'fra_le_ore' ? `
                        <div class="flex items-center gap-1.5">
                            <input type="time" value="${c.dalle || '20:00'}" onchange="setDatoCondizione('${node.id}', 'dalle', this.value)" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                            <span class="text-slate-500 text-[10px]">e</span>
                            <input type="time" value="${c.alle || '23:00'}" onchange="setDatoCondizione('${node.id}', 'alle', this.value)" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                        </div>
                    ` : ''}
                    ${c.tipo === 'giorni' ? `
                        <div class="flex gap-0.5">
                            ${['L','M','M','G','V','S','D'].map((g, i) => `
                                <button type="button" onclick="alternaGiorno('${node.id}', ${i})" class="flex-1 py-1 rounded text-[10px] font-bold ${(c.giorni || []).includes(i) ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-400'}">${g}</button>
                            `).join('')}
                        </div>
                    ` : ''}
                    ${c.tipo === 'presenza' ? `
                        <label class="flex items-center gap-2 text-[11px] text-slate-300">
                            <input type="checkbox" ${c.abitata !== false ? 'checked' : ''} onchange="setDatoCondizione('${node.id}', 'abitata', this.checked)">
                            Vero quando in casa c'è qualcuno
                        </label>
                    ` : ''}
                    <p class="text-[10px] text-slate-500 leading-snug">
                        Collega <span class="text-emerald-400 font-semibold">entrambe</span> le uscite:
                        il pallino verde è il ramo sì, quello rosso il ramo no.
                    </p>
                </div>
            `;
        } else if (node.type === 'notifica') {
            headerBg = 'from-sky-600 to-cyan-600';
            icon = 'bell';
            typeLabel = '🔔 Notifica';
            bodyHtml = `
                <div class="space-y-2 text-xs">
                    <input type="text" value="${node.data.titolo || ''}" oninput="updateNodeData('${node.id}', 'titolo', this.value)" placeholder="Titolo" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    <textarea rows="2" oninput="updateNodeData('${node.id}', 'testo', this.value)" placeholder="es. la lavatrice ha finito" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">${node.data.testo || ''}</textarea>
                    <p class="text-[10px] text-slate-500 leading-snug">
                        Arriva sul telefono, anche a chi non è in casa — a differenza
                        dell'annuncio vocale, che lo sente solo chi è nella stanza.
                    </p>
                </div>
            `;
        }

        const hasInputPin = node.type !== 'trigger';
        // Una condizione ha due uscite. Un'uscita sola non sarebbe una
        // condizione: sarebbe un filtro che a volte ferma tutto, e chi
        // lo disegna si aspetta due strade (issue #28).
        const isCondizione = node.type === 'condizione';

        return `
            <div id="c-node-${node.id}" class="flow-node absolute w-60 rounded-xl bg-slate-950/90 border border-slate-700 shadow-xl backdrop-blur" style="left: ${node.x}px; top: ${node.y}px;">
                <!-- Input Pin (Left) -->
                ${hasInputPin ? `<div onmouseup="onPinMouseUp('${node.id}', event)" class="port-pin port-pin-in" title="Collega qui il cavo in ingresso"></div>` : ''}

                <!-- Output Pin (Right) -->
                ${isCondizione ? `
                <div onmousedown="onPinMouseDown('${node.id}', event, 'vero')" class="port-pin port-pin-out port-pin-vero" title="Ramo SÌ: la condizione è soddisfatta"></div>
                <div onmousedown="onPinMouseDown('${node.id}', event, 'falso')" class="port-pin port-pin-out port-pin-falso" title="Ramo NO: la condizione non è soddisfatta"></div>
                ` : `<div onmousedown="onPinMouseDown('${node.id}', event)" class="port-pin port-pin-out" title="Trascina cavo verso un altro nodo"></div>`}

                <!-- Node Header -->
                <div class="flow-node-header flex items-center justify-between px-3 py-2 bg-gradient-to-r ${headerBg} rounded-t-xl cursor-move text-white font-bold text-xs" onmousedown="startDragNode('${node.id}', event)">
                    <div class="flex items-center gap-1.5">
                        <i data-lucide="${icon}" class="w-3.5 h-3.5"></i>
                        <span>${typeLabel}</span>
                    </div>
                    ${node.type !== 'trigger' ? `<button type="button" onclick="deleteCanvasNode('${node.id}')" class="text-white/70 hover:text-white p-0.5" title="Elimina nodo"><i data-lucide="x" class="w-3.5 h-3.5"></i></button>` : ''}
                </div>

                <!-- Node Body -->
                <div class="p-3">
                    ${bodyHtml}
                </div>
            </div>
        `;
    }).join('');

    safeCreateIcons();
    renderCanvasWires();
    updateCanvasStats();
}

function updateCanvasStats() {
    const el = document.getElementById('canvas-stats');
    if (el) el.innerText = `Nodi: ${_canvasState.nodes.length} | Connessioni: ${_canvasState.edges.length}`;
}
