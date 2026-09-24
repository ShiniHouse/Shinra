// ==================== VISUAL FLOW CANVAS (STILE VISIO / NODE-RED) ====================

function openModularModeBuilder(existingId = null) {
    let mode = {
        id: '',
        name: '',
        icon: 'workflow',
        description: '',
        trigger_phrases: [],
        nodes: [],
        edges: [],
    };
    if (existingId) {
        const found = Stato.routine.find((m) => m.id === existingId);
        if (found) mode = JSON.parse(JSON.stringify(found));
    }

    Stato.tela.id = mode.id || '';
    Stato.tela.name = mode.name || (existingId ? '' : 'Nuova Routine');
    Stato.tela.icon = mode.icon || 'workflow';
    Stato.tela.description = mode.description || '';
    Stato.tela.trigger_phrases = mode.trigger_phrases || [];

    // Se la routine ha già nodi e archi grafici carichiamoli, altrimenti convertiamo le vecchie actions in grafo
    if (mode.nodes && mode.nodes.length > 0) {
        Stato.tela.nodes = mode.nodes;
        Stato.tela.edges = mode.edges || [];
    } else if (mode.actions && mode.actions.length > 0) {
        // Auto-conversione in layout orizzontale a nodi
        const nTrigger = {
            id: 'node_trig',
            type: 'trigger',
            x: 40,
            y: 140,
            data: { phrases: mode.trigger_phrases || [] },
        };
        Stato.tela.nodes = [nTrigger];
        Stato.tela.edges = [];
        let prevId = 'node_trig';

        mode.actions.forEach((act, idx) => {
            const nId = `node_${idx + 1}`;
            Stato.tela.nodes.push({
                id: nId,
                type: act.type || 'ha_device',
                x: 40 + (idx + 1) * 270,
                y: 140,
                data: {
                    entity_id: act.entity_id || act.data?.entity_id || '',
                    action: act.action || act.service || 'turn_on',
                    seconds: act.seconds || act.delay_seconds || 5,
                    message: act.message || '',
                },
            });
            Stato.tela.edges.push({ from: prevId, to: nId });
            prevId = nId;
        });
    } else {
        // Routine vuota predefinita con nodo Trigger
        Stato.tela.nodes = [
            {
                id: 'node_trig',
                type: 'trigger',
                x: 50,
                y: 140,
                data: { phrases: ['modalità ' + (Stato.tela.name.toLowerCase() || 'relax')] },
            },
            { id: 'node_ha1', type: 'ha_device', x: 340, y: 140, data: { entity_id: '', action: 'turn_on' } },
        ];
        Stato.tela.edges = [{ from: 'node_trig', to: 'node_ha1' }];
    }

    renderFlowCanvasModal();
}

function renderFlowCanvasModal() {
    const triggersStr = Stato.tela.trigger_phrases.join(', ');

    showModal(
        _html`
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
                    <input type="text" id="cv-name" value="${Stato.tela.name || ''}" placeholder="Nome Routine (es. Cinema, Notte)" oninput="Stato.tela.name = this.value" class="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-100 font-bold focus:outline-none focus:border-indigo-500 w-40">
                    <input type="text" id="cv-triggers" value="${triggersStr}" placeholder="Frasi vocali: es. modalità cinema, relax" oninput="Stato.tela.trigger_phrases = this.value.split(',').map(s=>s.trim()).filter(s=>s.length>0)" class="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-slate-100 focus:outline-none focus:border-indigo-500 flex-1 min-w-[180px]">
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
                <!-- Il piano dei nodi copre tutta la tela e sta sopra ai cavi.
                     Se prende gli eventi del mouse, li prende anche dove
                     non c'e' nessun nodo — e li' sotto c'e' la
                     crocetta che stacca un cavo, che quindi non si poteva
                     premere. Il piano fa da telaio e basta: a ricevere i
                     clic sono i nodi, uno per uno. -->
                <div id="flow-nodes-container" class="absolute inset-0 z-20 pointer-events-none">
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
    `,
        true,
    );

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
        if (Stato.tela.isDraggingNode) {
            const node = Stato.tela.nodes.find((n) => n.id === Stato.tela.isDraggingNode);
            if (node) {
                node.x = Math.max(10, Math.min(rect.width - 240, mouseX - Stato.tela.dragOffset.x));
                node.y = Math.max(10, Math.min(rect.height - 180, mouseY - Stato.tela.dragOffset.y));
                const el = document.getElementById(`c-node-${node.id}`);
                if (el) {
                    el.style.left = `${node.x}px`;
                    el.style.top = `${node.y}px`;
                }
                renderCanvasWires();
            }
        }

        // 2. Connecting Wire Draft
        if (Stato.tela.connectingSourceId) {
            renderCanvasWires({ x: mouseX, y: mouseY });
        }
    };

    // Global Mouse Up su Canvas
    canvas.onmouseup = () => {
        Stato.tela.isDraggingNode = null;
        if (Stato.tela.connectingSourceId) {
            Stato.tela.connectingSourceId = null;
            renderCanvasWires();
        }
    };
}
