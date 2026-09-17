function updateNodeData(nodeId, field, val) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (node) {
        node.data[field] = val;
    }
}

function setQuickDelay(nodeId, secs) {
    updateNodeData(nodeId, 'seconds', secs);
    renderCanvasElements();
}

function startDragNode(nodeId, e) {
    if (
        e.target.tagName === 'INPUT' ||
        e.target.tagName === 'SELECT' ||
        e.target.tagName === 'TEXTAREA' ||
        e.target.tagName === 'BUTTON'
    )
        return;
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const canvas = document.getElementById('flow-canvas');
    const rect = canvas.getBoundingClientRect();
    _canvasState.isDraggingNode = nodeId;
    _canvasState.dragOffset = {
        x: e.clientX - rect.left - node.x,
        y: e.clientY - rect.top - node.y,
    };
}

function onPinMouseDown(sourceNodeId, e, ramo = null) {
    e.stopPropagation();
    _canvasState.connectingSourceId = sourceNodeId;
    // Da quale uscita parte il cavo. Solo le condizioni ne hanno due,
    // e l'etichetta sta sull'**arco**: e' l'arco a sapere da quale
    // uscita parte, ed e' l'unica informazione che serve al motore
    // per percorrerne uno solo (issue #28).
    _canvasState.connectingRamo = ramo;
}

function onPinMouseUp(targetNodeId, e) {
    e.stopPropagation();
    if (_canvasState.connectingSourceId && _canvasState.connectingSourceId !== targetNodeId) {
        // Aggiunge la connessione se non già esistente. Due archi con
        // lo stesso arrivo ma rami diversi sono connessioni diverse:
        // e' come si disegna «se sì fai questo, se no fai lo stesso
        // ma dopo qualcos'altro».
        const ramo = _canvasState.connectingRamo || null;
        const exists = _canvasState.edges.some(
            (x) =>
                x.from === _canvasState.connectingSourceId &&
                x.to === targetNodeId &&
                (x.ramo || null) === ramo,
        );
        if (!exists) {
            const nuovo = { from: _canvasState.connectingSourceId, to: targetNodeId };
            if (ramo) nuovo.ramo = ramo;
            _canvasState.edges.push(nuovo);
        }
        _canvasState.connectingSourceId = null;
        _canvasState.connectingRamo = null;
        renderCanvasElements();
    }
}

// ---- Condizioni (issue #28) ----
//
// Il vocabolario e' quello del motore di regole: le stesse condizioni
// scritte allo stesso modo, cosi' che non si comportino diversamente
// a seconda di dove le hai scritte.

function setTipoCondizione(nodeId, tipo) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    // Si riparte da zero al cambio di tipo: i campi di una condizione
    // non valgono per un'altra, e lasciarli in giro produce una
    // condizione che porta con sé dati che nessuno legge.
    const predefiniti = {
        presenza: { tipo: 'presenza', abitata: true },
        stato_entita: { tipo: 'stato_entita', entity_id: '', stato: '' },
        fra_le_ore: { tipo: 'fra_le_ore', dalle: '20:00', alle: '23:00' },
        giorni: { tipo: 'giorni', giorni: [] },
    };
    node.data.condizione = predefiniti[tipo] || { tipo: tipo };
    renderCanvasElements();
}

function setTipoInnesco(nodeId, tipo) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    // Come per le condizioni: si riparte da zero. I campi di un
    // innesco a orario non valgono per uno su soglia, e lasciarli in
    // giro produce una regola che porta dietro dati che nessuno legge.
    const predefiniti = {
        voce: { tipo: 'voce' },
        orario: { tipo: 'orario', ora: '07:00', giorni: [] },
        alba: { tipo: 'alba', scarto_minuti: 0 },
        tramonto: { tipo: 'tramonto', scarto_minuti: 0 },
        stato: { tipo: 'stato', entity_id: '', confronto: 'attraversa_sotto', valore: '' },
        evento: { tipo: 'evento', evento: '' },
    };
    node.data.trigger = predefiniti[tipo] || { tipo: tipo };
    renderCanvasElements();
}

function setDatoInnesco(nodeId, campo, valore) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    node.data.trigger = node.data.trigger || { tipo: 'voce' };
    node.data.trigger[campo] = valore;
}

function alternaGiornoInnesco(nodeId, giorno) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const t = (node.data.trigger = node.data.trigger || { tipo: 'orario' });
    const scelti = new Set(t.giorni || []);
    scelti.has(giorno) ? scelti.delete(giorno) : scelti.add(giorno);
    t.giorni = [...scelti].sort();
    renderCanvasElements();
}

function setDatoCondizione(nodeId, campo, valore) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    node.data.condizione = node.data.condizione || {};
    node.data.condizione[campo] = valore;
}

function alternaGiorno(nodeId, giorno) {
    const node = _canvasState.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const c = (node.data.condizione = node.data.condizione || { tipo: 'giorni' });
    const scelti = new Set(c.giorni || []);
    scelti.has(giorno) ? scelti.delete(giorno) : scelti.add(giorno);
    c.giorni = [...scelti].sort();
    renderCanvasElements();
}

function addCanvasNode(type) {
    const id = `node_${Date.now().toString().slice(-5)}`;
    const count = _canvasState.nodes.length;
    const newNode = {
        id: id,
        type: type,
        x: 80 + (count % 3) * 260,
        y: 100 + Math.floor(count / 3) * 160,
        data: {
            entity_id: '',
            action: 'turn_on',
            seconds: 5,
            message: '',
        },
    };
    // Una condizione nasce con qualcosa dentro: un nodo vuoto e' vero
    // per definizione, e chi lo trascina si accorge del ramo sbagliato
    // solo eseguendo.
    if (type === 'condizione') newNode.data.condizione = { tipo: 'presenza', abitata: true };
    if (type === 'notifica') {
        newNode.data.titolo = '';
        newNode.data.testo = '';
    }
    _canvasState.nodes.push(newNode);
    renderCanvasElements();
}

function deleteCanvasNode(nodeId) {
    _canvasState.nodes = _canvasState.nodes.filter((n) => n.id !== nodeId);
    _canvasState.edges = _canvasState.edges.filter((e) => e.from !== nodeId && e.to !== nodeId);
    renderCanvasElements();
}

function deleteCanvasEdge(idx) {
    _canvasState.edges.splice(idx, 1);
    renderCanvasWires();
    updateCanvasStats();
}

function renderCanvasWires(draftPos = null) {
    const svg = document.getElementById('flow-svg-layer');
    if (!svg) return;

    let pathsHtml = '';

    _canvasState.edges.forEach((edge, idx) => {
        const fromNode = _canvasState.nodes.find((n) => n.id === edge.from);
        const toNode = _canvasState.nodes.find((n) => n.id === edge.to);
        if (fromNode && toNode) {
            const x1 = fromNode.x + 240; // output pin (right side)
            const y1 = fromNode.y + 20; // pin y position
            const x2 = toNode.x; // input pin (left side)
            const y2 = toNode.y + 20;

            const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
            const pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;

            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;

            pathsHtml += `
                <g class="wire-group">
                    <!-- Glow shadow -->
                    <path d="${pathD}" stroke="rgba(99, 102, 241, 0.2)" stroke-width="8" fill="none" />
                    <!-- Main line -->
                    <path id="wire-${edge.from}-${edge.to}" d="${pathD}" class="flow-wire" stroke="url(#wireGradient)" stroke-width="3" fill="none" />
                    <!-- Wire Delete Button -->
                    <circle cx="${midX}" cy="${midY}" r="7" fill="#0f172a" stroke="#6366f1" stroke-width="1.5" class="pointer-events-auto cursor-pointer hover:fill-rose-600" onclick="deleteCanvasEdge(${idx})" />
                    <text x="${midX}" y="${midY + 3}" fill="#cbd5e1" font-size="9" text-anchor="middle" font-weight="bold" class="pointer-events-none">×</text>
                </g>
            `;
        }
    });

    // Disegna cavo di bozza durante il trascinamento
    if (draftPos && _canvasState.connectingSourceId) {
        const srcNode = _canvasState.nodes.find((n) => n.id === _canvasState.connectingSourceId);
        if (srcNode) {
            const x1 = srcNode.x + 240;
            const y1 = srcNode.y + 20;
            const x2 = draftPos.x;
            const y2 = draftPos.y;
            const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
            const pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
            pathsHtml += `<path d="${pathD}" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="4 4" fill="none" />`;
        }
    }

    svg.innerHTML = `
        <defs>
            <linearGradient id="wireGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#6366f1" />
                <stop offset="100%" stop-color="#a855f7" />
            </linearGradient>
        </defs>
        ${pathsHtml}
    `;
}

// La simulazione la fa il server, non questa pagina.
//
// Prima c'era una visita in ampiezza scritta qui dentro, e percorreva
// **tutti** gli archi: mostrava un nodo condizione che accende
// entrambi i rami, cioe' l'unica cosa che una condizione non fa. Una
// simulazione che mostra un percorso diverso da quello vero e' peggio
// che nessuna simulazione, perche' ci si crede. Adesso la domanda la
// fa `/api/modes/simula` allo stesso codice che esegue la routine, e
// qui resta solo il disegno (issue #28).
async function simulateCanvasFlow() {
    const btn = document.getElementById('btn-sim-canvas');
    const testoPulsante = '▶️ Prova il flusso';
    if (!_canvasState.nodes.length) return;
    if (btn) btn.innerHTML = '<span class="animate-spin">⏳</span> Simulazione...';

    let esito;
    try {
        const res = await fetch('/api/modes/simula', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ nodes: _canvasState.nodes, edges: _canvasState.edges }),
        });
        if (!res.ok) throw new Error('simulazione rifiutata');
        esito = await res.json();
    } catch {
        if (btn) btn.innerHTML = testoPulsante;
        alert('Non riesco a simulare adesso: il server non ha risposto.');
        return;
    }

    spegniLaSimulazione();

    const decisioni = new Map((esito.decisioni || []).map((d) => [d.node_id, d]));
    const visitati = esito.visitati || [];
    mostraLeDecisioni(esito.decisioni || []);

    for (const idNodo of visitati) {
        const el = document.getElementById(`c-node-${idNodo}`);
        if (el) el.classList.add('ring-2', 'ring-violet-400', 'border-violet-400', 'scale-[1.02]');

        const nodo = _canvasState.nodes.find((n) => n.id === idNodo);
        if (nodo && nodo.type === 'delay') {
            await new Promise((r) => setTimeout(r, Math.min((nodo.data.seconds || 3) * 1000, 3000)));
        } else if (nodo && nodo.type === 'tts') {
            playChimeAlert();
            if (nodo.data.message) speakText(nodo.data.message);
            await new Promise((r) => setTimeout(r, 1000));
        } else {
            await new Promise((r) => setTimeout(r, 600));
        }

        if (el) el.classList.remove('ring-2', 'ring-violet-400', 'border-violet-400', 'scale-[1.02]');

        // Si accende solo il cavo percorso: da una condizione esce il
        // ramo scelto e basta, ed e' tutta la differenza fra vedere
        // cosa succede e vedere cosa potrebbe succedere.
        const scelta = decisioni.get(idNodo);
        const uscenti = _canvasState.edges.filter(
            (e) =>
                e.from === idNodo &&
                visitati.includes(e.to) &&
                (!scelta || !e.ramo || e.ramo === scelta.ramo),
        );
        for (const arco of uscenti) {
            const cavo = document.getElementById(`wire-${arco.from}-${arco.to}`);
            if (cavo) cavo.classList.add('flow-wire-sim');
        }
        await new Promise((r) => setTimeout(r, 400));
    }

    if (btn) btn.innerHTML = testoPulsante;
}

function spegniLaSimulazione() {
    document.querySelectorAll('.flow-wire-sim').forEach((el) => el.classList.remove('flow-wire-sim'));
    document.querySelectorAll('.decisione-del-nodo').forEach((el) => el.remove());
}

function mostraLeDecisioni(decisioni) {
    // Il ramo preso senza il perche' e' indistinguibile da un ramo
    // preso a caso: chi guarda vuole sapere che la condizione ha detto
    // no perche' in casa non c'e' nessuno, non solo che ha detto no.
    (decisioni || []).forEach((d) => {
        const el = document.getElementById(`c-node-${d.node_id}`);
        if (!el) return;
        const etichetta = document.createElement('div');
        etichetta.className =
            'decisione-del-nodo absolute -bottom-6 left-0 right-0 text-[10px] font-semibold text-center px-1 truncate ' +
            (d.ramo === 'vero' ? 'text-emerald-400' : 'text-rose-400');
        etichetta.title = d.motivo || '';
        etichetta.innerText =
            d.ramo === 'vero' ? '→ ramo sì' : '→ ramo no: ' + (d.motivo || 'la condizione non è soddisfatta');
        el.appendChild(etichetta);
    });
}

async function saveCanvasMode() {
    if (!_canvasState.name) {
        alert('Inserisci un nome per la routine.');
        return;
    }

    // Converte anche in array lineare di actions per garantire retrocompatibilità al 100%
    const linearActions = [];
    _canvasState.nodes.forEach((n) => {
        if (n.type !== 'trigger') {
            linearActions.push({
                type: n.type,
                entity_id: n.data.entity_id,
                action: n.data.action,
                seconds: n.data.seconds,
                message: n.data.message,
            });
        }
    });

    const payload = {
        id: _canvasState.id || undefined,
        name: _canvasState.name,
        icon: _canvasState.icon || 'workflow',
        description: _canvasState.description || '',
        trigger_phrases: _canvasState.trigger_phrases,
        enabled: true,
        nodes: _canvasState.nodes,
        edges: _canvasState.edges,
        actions: linearActions,
    };

    const res = await fetch('/api/modes', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
    });

    if (res.ok) {
        closeModal();
        loadModes();
    } else if (res.status === 400) {
        // Il server dice cosa non va **e quali nodi**: illuminarli è
        // l'unica forma in cui l'errore serve a qualcosa. «Il grafo
        // non è valido» manda a guardarne trenta, e chi ne ha
        // disegnati trenta non lo fa (issue #28).
        const dettaglio = (await res.json().catch(() => ({}))).detail || {};
        const problemi = dettaglio.problemi || [];
        illuminaNodiInErrore(problemi);
        alert(
            'Non salvo questa routine:\n\n' + problemi.map((p) => '• ' + p.messaggio).join('\n\n') ||
                dettaglio.messaggio ||
                'Il grafo non è valido.',
        );
    } else {
        alert('Errore nel salvataggio della routine.');
    }
}

function illuminaNodiInErrore(problemi) {
    document.querySelectorAll('.flow-node').forEach((el) => el.classList.remove('nodo-in-errore'));
    (problemi || []).forEach((p) =>
        (p.nodi || []).forEach((id) => {
            const el = document.getElementById(`c-node-${id}`);
            if (el) el.classList.add('nodo-in-errore');
        }),
    );
}

async function deleteMode(id) {
    if (!confirm('Eliminare questa routine?')) return;
    await fetch(`/api/modes/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadModes();
}
