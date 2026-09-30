import { Stato } from './stato.js';
import { Gesti } from './gesti.js';
import { _args, _grezzo, _html } from './sicurezza.js';
import { safeCreateIcons } from './avvio.js';
import { renderCanvasWires, setDatoInnesco, updateNodeData } from './tela_nodi.js';

export function renderCanvasElements() {
    const container = document.getElementById('flow-nodes-container');
    if (!container) return;

    container.innerHTML = _html`${Stato.tela.nodes.map((node) => {
        let headerBg = 'from-indigo-600 to-violet-600';
        let icon = 'workflow';
        let typeLabel = 'Modulo';
        let bodyHtml = _grezzo('');

        if (node.type === 'trigger') {
            headerBg = 'from-amber-600 to-orange-600';
            icon = 'zap';
            const t = node.data.trigger || { tipo: 'voce' };
            const etichette = {
                voce: '⚡ Innesco Vocale',
                orario: '🕒 A un orario',
                alba: "🌅 All'alba",
                tramonto: '🌇 Al tramonto',
                stato: '📈 Su un valore',
                evento: '📡 Su un evento',
            };
            typeLabel = etichette[t.tipo] || etichette.voce;
            const ph = (node.data.phrases || []).join(', ');
            bodyHtml = _html`
                <div class="space-y-2 text-xs">
                    <select data-al-cambio="setTipoInnesco" data-args="${_args(node.id)}" data-argomento="valore" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                        <option value="voce" ${t.tipo === 'voce' ? 'selected' : ''}>Quando lo chiedo a voce</option>
                        <option value="orario" ${t.tipo === 'orario' ? 'selected' : ''}>A un orario</option>
                        <option value="alba" ${t.tipo === 'alba' ? 'selected' : ''}>All'alba</option>
                        <option value="tramonto" ${t.tipo === 'tramonto' ? 'selected' : ''}>Al tramonto</option>
                        <option value="stato" ${t.tipo === 'stato' ? 'selected' : ''}>Quando un valore supera una soglia</option>
                        <option value="evento" ${t.tipo === 'evento' ? 'selected' : ''}>Su un evento della casa</option>
                    </select>
                    ${
                        t.tipo === 'voce'
                            ? _html`
                        <label class="text-[10px] text-slate-400 font-semibold block">Frasi di Attivazione:</label>
                        <input type="text" value="${ph}" data-mentre-scrivi="aggiornaFrasiNodo" data-args="${_args(node.id)}" data-argomento="valore" placeholder="es. attiva cinema, cinema" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-amber-500">
                    `
                            : ''
                    }
                    ${
                        t.tipo === 'orario'
                            ? _html`
                        <input type="time" value="${t.ora || '07:00'}" data-al-cambio="setDatoInnesco" data-args="${_args(node.id, 'ora')}" data-argomento="valore" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                        <div class="flex gap-0.5">
                            ${['L', 'M', 'M', 'G', 'V', 'S', 'D'].map(
                                (g, i) => _html`
                                <button type="button" data-gesto="alternaGiornoInnesco" data-args="${_args(node.id, i)}" class="flex-1 py-1 rounded text-[10px] font-bold ${(t.giorni || []).includes(i) ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-400'}">${g}</button>
                            `,
                            )}
                        </div>
                        <p class="text-[10px] text-slate-500">Nessun giorno scelto vuol dire tutti i giorni.</p>
                    `
                            : ''
                    }
                    ${
                        t.tipo === 'alba' || t.tipo === 'tramonto'
                            ? _html`
                        <div class="flex items-center gap-2">
                            <input type="number" value="${t.scarto_minuti || 0}" data-al-cambio="setScartoMinuti" data-args="${_args(node.id)}" data-argomento="valore" class="w-20 bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 text-center">
                            <span class="text-[11px] text-slate-400">minuti di scarto (negativi = prima)</span>
                        </div>
                    `
                            : ''
                    }
                    ${
                        t.tipo === 'stato'
                            ? _html`
                        <input type="text" value="${t.entity_id || ''}" data-mentre-scrivi="setDatoInnesco" data-args="${_args(node.id, 'entity_id')}" data-argomento="valore" placeholder="es. sensor.temperatura_salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <select data-al-cambio="setDatoInnesco" data-args="${_args(node.id, 'confronto')}" data-argomento="valore" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                            <option value="attraversa_sotto" ${t.confronto === 'attraversa_sotto' ? 'selected' : ''}>quando scende sotto</option>
                            <option value="attraversa_sopra" ${t.confronto === 'attraversa_sopra' ? 'selected' : ''}>quando sale sopra</option>
                            <option value="diventa" ${t.confronto === 'diventa' ? 'selected' : ''}>quando diventa</option>
                        </select>
                        <input type="text" value="${t.valore !== undefined ? t.valore : ''}" data-mentre-scrivi="setDatoInnesco" data-args="${_args(node.id, 'valore')}" data-argomento="valore" placeholder="es. 15" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <p class="text-[10px] text-slate-500 leading-snug">Scatta nel momento in cui la soglia viene attraversata, non a ogni lettura che sta di là.</p>
                    `
                            : ''
                    }
                    ${
                        t.tipo === 'evento'
                            ? _html`
                        <input type="text" value="${t.evento || ''}" data-mentre-scrivi="setDatoInnesco" data-args="${_args(node.id, 'evento')}" data-argomento="valore" placeholder="es. casa.vuota" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <input type="text" value="${t.entity_id || ''}" data-mentre-scrivi="setDatoInnesco" data-args="${_args(node.id, 'entity_id')}" data-argomento="valore" placeholder="solo per questa entità (facoltativo)" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    `
                            : ''
                    }
                    ${
                        t.tipo !== 'voce'
                            ? _html`
                        <p class="text-[10px] text-amber-400 leading-snug">Al salvataggio questa routine parte da sola: diventa una regola del motore delle automazioni. Per fermarla, togli l'innesco e risalva.</p>
                    `
                            : ''
                    }
                </div>
            `;
        } else if (node.type === 'ha_device' || node.type === 'ha_service') {
            headerBg = 'from-indigo-600 to-blue-600';
            icon = 'power';
            typeLabel = '💡 Dispositivo HA';
            bodyHtml = _html`
                <div class="space-y-2 text-xs">
                    <div>
                        <label class="text-[10px] text-slate-400 font-semibold block mb-0.5">Dispositivo / Alias:</label>
                        <input type="text" value="${node.data.entity_id || ''}" data-mentre-scrivi="updateNodeData" data-args="${_args(node.id, 'entity_id')}" data-argomento="valore" placeholder="es. light.salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-indigo-500">
                    </div>
                    <div class="flex gap-1.5">
                        <select data-al-cambio="updateNodeData" data-args="${_args(node.id, 'action')}" data-argomento="valore" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
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
            bodyHtml = _html`
                <div class="space-y-2 text-xs">
                    <label class="text-[10px] text-slate-400 font-semibold block">Attesa prima del prossimo step:</label>
                    <div class="flex items-center gap-2">
                        <input type="number" min="1" max="300" value="${node.data.seconds || 5}" data-mentre-scrivi="aggiornaSecondiNodo" data-args="${_args(node.id)}" data-argomento="valore" class="w-20 bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 font-bold text-center">
                        <span class="text-xs text-slate-400">secondi</span>
                    </div>
                    <div class="flex gap-1">
                        <button type="button" data-gesto="setQuickDelay" data-args="${_args(node.id, 3)}" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">3s</button>
                        <button type="button" data-gesto="setQuickDelay" data-args="${_args(node.id, 5)}" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">5s</button>
                        <button type="button" data-gesto="setQuickDelay" data-args="${_args(node.id, 10)}" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">10s</button>
                        <button type="button" data-gesto="setQuickDelay" data-args="${_args(node.id, 30)}" class="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 hover:bg-slate-700">30s</button>
                    </div>
                </div>
            `;
        } else if (node.type === 'tts') {
            headerBg = 'from-emerald-600 to-teal-600';
            icon = 'message-circle';
            typeLabel = '🗣️ Annuncio Vocale';
            bodyHtml = _html`
                <div class="space-y-1 text-xs">
                    <label class="text-[10px] text-slate-400 font-semibold block">Frase da pronunciare:</label>
                    <textarea rows="2" data-mentre-scrivi="updateNodeData" data-args="${_args(node.id, 'message')}" data-argomento="valore" placeholder="es. Luci regolate, buona visione!" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100 focus:outline-none focus:border-emerald-500">${node.data.message || ''}</textarea>
                </div>
            `;
        } else if (node.type === 'condizione') {
            headerBg = 'from-violet-600 to-fuchsia-600';
            icon = 'git-branch';
            typeLabel = '🔀 Condizione';
            const c = node.data.condizione || {};
            bodyHtml = _html`
                <div class="space-y-2 text-xs">
                    <select data-al-cambio="setTipoCondizione" data-args="${_args(node.id)}" data-argomento="valore" class="w-full bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-200">
                        <option value="presenza" ${c.tipo === 'presenza' ? 'selected' : ''}>C'è qualcuno in casa</option>
                        <option value="stato_entita" ${c.tipo === 'stato_entita' ? 'selected' : ''}>Un dispositivo è in uno stato</option>
                        <option value="fra_le_ore" ${c.tipo === 'fra_le_ore' ? 'selected' : ''}>Siamo in una fascia oraria</option>
                        <option value="giorni" ${c.tipo === 'giorni' ? 'selected' : ''}>È uno di certi giorni</option>
                    </select>
                    ${
                        c.tipo === 'stato_entita'
                            ? _html`
                        <input type="text" value="${c.entity_id || ''}" data-mentre-scrivi="setDatoCondizione" data-args="${_args(node.id, 'entity_id')}" data-argomento="valore" placeholder="es. light.salotto" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                        <input type="text" value="${c.stato || ''}" data-mentre-scrivi="setDatoCondizione" data-args="${_args(node.id, 'stato')}" data-argomento="valore" placeholder="stato atteso, es. on" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    `
                            : ''
                    }
                    ${
                        c.tipo === 'fra_le_ore'
                            ? _html`
                        <div class="flex items-center gap-1.5">
                            <input type="time" value="${c.dalle || '20:00'}" data-al-cambio="setDatoCondizione" data-args="${_args(node.id, 'dalle')}" data-argomento="valore" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                            <span class="text-slate-500 text-[10px]">e</span>
                            <input type="time" value="${c.alle || '23:00'}" data-al-cambio="setDatoCondizione" data-args="${_args(node.id, 'alle')}" data-argomento="valore" class="flex-1 bg-slate-900 border border-slate-700 rounded p-1 text-xs text-slate-100">
                        </div>
                    `
                            : ''
                    }
                    ${
                        c.tipo === 'giorni'
                            ? _html`
                        <div class="flex gap-0.5">
                            ${['L', 'M', 'M', 'G', 'V', 'S', 'D'].map(
                                (g, i) => _html`
                                <button type="button" data-gesto="alternaGiorno" data-args="${_args(node.id, i)}" class="flex-1 py-1 rounded text-[10px] font-bold ${(c.giorni || []).includes(i) ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-400'}">${g}</button>
                            `,
                            )}
                        </div>
                    `
                            : ''
                    }
                    ${
                        c.tipo === 'presenza'
                            ? _html`
                        <label class="flex items-center gap-2 text-[11px] text-slate-300">
                            <input type="checkbox" ${c.abitata !== false ? 'checked' : ''} data-al-cambio="setDatoCondizione" data-args="${_args(node.id, 'abitata')}" data-argomento="spunta">
                            Vero quando in casa c'è qualcuno
                        </label>
                    `
                            : ''
                    }
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
            bodyHtml = _html`
                <div class="space-y-2 text-xs">
                    <input type="text" value="${node.data.titolo || ''}" data-mentre-scrivi="updateNodeData" data-args="${_args(node.id, 'titolo')}" data-argomento="valore" placeholder="Titolo" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">
                    <textarea rows="2" data-mentre-scrivi="updateNodeData" data-args="${_args(node.id, 'testo')}" data-argomento="valore" placeholder="es. la lavatrice ha finito" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-100">${node.data.testo || ''}</textarea>
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

        return _html`
            <div id="c-node-${node.id}" class="flow-node absolute w-60 pointer-events-auto rounded-xl bg-slate-950/90 border border-slate-700 shadow-xl backdrop-blur" style="left: ${node.x}px; top: ${node.y}px;">
                <!-- Input Pin (Left) -->
                ${hasInputPin ? _html`<div data-al-rilascio="onPinMouseUp" data-args="${_args(node.id)}" data-argomento="evento" class="port-pin port-pin-in" title="Collega qui il cavo in ingresso"></div>` : ''}

                <!-- Output Pin (Right) -->
                ${
                    isCondizione
                        ? _html`
                <div data-al-premere="onPinMouseDown" data-args="${_args(node.id, 'vero')}" data-argomento="evento" class="port-pin port-pin-out port-pin-vero" title="Ramo SÌ: la condizione è soddisfatta"></div>
                <div data-al-premere="onPinMouseDown" data-args="${_args(node.id, 'falso')}" data-argomento="evento" class="port-pin port-pin-out port-pin-falso" title="Ramo NO: la condizione non è soddisfatta"></div>
                `
                        : _html`<div data-al-premere="onPinMouseDown" data-args="${_args(node.id, null)}" data-argomento="evento" class="port-pin port-pin-out" title="Trascina cavo verso un altro nodo"></div>`
                }

                <!-- Node Header -->
                <div class="flow-node-header flex items-center justify-between px-3 py-2 bg-gradient-to-r ${headerBg} rounded-t-xl cursor-move text-white font-bold text-xs" data-al-premere="startDragNode" data-args="${_args(node.id)}" data-argomento="evento">
                    <div class="flex items-center gap-1.5">
                        <i data-lucide="${icon}" class="w-3.5 h-3.5"></i>
                        <span>${typeLabel}</span>
                    </div>
                    ${node.type !== 'trigger' ? _html`<button type="button" data-gesto="deleteCanvasNode" data-args="${_args(node.id)}" class="text-white/70 hover:text-white p-0.5" title="Elimina nodo"><i data-lucide="x" class="w-3.5 h-3.5"></i></button>` : ''}
                </div>

                <!-- Node Body -->
                <div class="p-3">
                    ${bodyHtml}
                </div>
            </div>
        `;
    })}`;

    safeCreateIcons();
    renderCanvasWires();
    updateCanvasStats();
}

export function updateCanvasStats() {
    const el = document.getElementById('canvas-stats');
    if (el) el.innerText = `Nodi: ${Stato.tela.nodes.length} | Connessioni: ${Stato.tela.edges.length}`;
}

// I campi del nodo che non scrivono il valore cosi' com'e': prima la
// conversione stava nell'attributo (`parseInt(this.value)||1`), adesso ha
// una funzione con un nome.
function aggiornaFrasiNodo(nodeId, valore) {
    updateNodeData(
        nodeId,
        'phrases',
        valore.split(',').map((s) => s.trim()),
    );
}

function aggiornaSecondiNodo(nodeId, valore) {
    updateNodeData(nodeId, 'seconds', parseInt(valore) || 1);
}

function setScartoMinuti(nodeId, valore) {
    setDatoInnesco(nodeId, 'scarto_minuti', parseInt(valore) || 0);
}

// I gesti che il markup di quest'area puo' chiedere (#34).
Gesti.registra({
    aggiornaFrasiNodo,
    aggiornaSecondiNodo,
    setScartoMinuti,
});
