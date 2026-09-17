// Messages Handling
let activeAssistantName = 'Kyra';

function appendUserMessage(text) {
    const container = document.getElementById('messages-container');
    const div = document.createElement('div');
    div.className = 'flex justify-end gap-3';
    div.innerHTML = `<div class="bg-indigo-600 dark:bg-indigo-600 light:bg-indigo-600 text-white rounded-2xl rounded-tr-none p-3.5 text-sm max-w-xl shadow-md">${text}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function appendAssistantMessage(text, actions = []) {
    const container = document.getElementById('messages-container');
    const div = document.createElement('div');
    div.className = 'flex gap-3 max-w-2xl';

    let actionsHtml = '';
    if (actions && actions.length > 0) {
        actionsHtml = `
            <div class="mt-2.5 pt-2 border-t border-slate-700/60 flex flex-wrap gap-1.5">
                ${actions.map((a) => `<span class="px-2 py-0.5 rounded bg-indigo-950/70 border border-indigo-700/50 text-indigo-300 text-xs font-mono">⚡ ${a.tool}</span>`).join('')}
            </div>
        `;
    }

    div.innerHTML = `
        <div class="living-core !w-8 !h-8 !rounded-lg shrink-0">
            <i data-lucide="sparkles" class="w-4 h-4 text-white"></i>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl rounded-tl-none p-4 text-sm text-slate-200 flex-1 shadow-sm">
            <div class="flex items-center justify-between mb-1">
                <p class="font-bold text-amber-400 dark:text-amber-400 light:text-amber-600 flex items-center gap-1.5">
                    <span class="assistant-name-label">${activeAssistantName}</span>
                    <span class="inline-flex gap-0.5 items-end h-3">
                        <span class="soundwave-bar"></span>
                        <span class="soundwave-bar" style="animation-delay: 0.2s"></span>
                        <span class="soundwave-bar" style="animation-delay: 0.4s"></span>
                    </span>
                </p>
                <button onclick="speakText('${text.replace(/'/g, "\\'")}')" class="text-slate-400 hover:text-amber-400 p-1 transition" title="Riascolta">
                    <i data-lucide="volume-2" class="w-4 h-4"></i>
                </button>
            </div>
            <p class="whitespace-pre-line">${text}</p>
            ${actionsHtml}
        </div>
    `;
    container.appendChild(div);
    safeCreateIcons();
    container.scrollTop = container.scrollHeight;
    speakText(text);
}

// I tool invocati vivono in memoria, non in un pannello acceso
// (issue #123). Il pannello stava un terzo dello schermo di casa e
// parlava a chi costruisce l'hub; la storia non si perde lo stesso,
// si apre quando una risposta non torna.
let _toolInvocati = [];

function logAction(tool, args, result) {
    _toolInvocati.unshift({
        tool: tool,
        argomenti: args,
        risultato: result,
        quando: new Date().toLocaleTimeString(),
    });
    // La memoria di una pagina aperta da giorni non cresce all'infinito.
    if (_toolInvocati.length > 50) _toolInvocati.length = 50;

    const conta = document.getElementById('conta-tool');
    if (conta) {
        conta.innerText = _toolInvocati.length === 1 ? '1 azione' : _toolInvocati.length + ' azioni';
    }
    // Se la finestra e' aperta adesso, si aggiorna sotto gli occhi.
    if (document.getElementById('tool-logs')) _disegnaToolInvocati();
}

function _disegnaToolInvocati() {
    const contenitore = document.getElementById('tool-logs');
    if (!contenitore) return;
    if (!_toolInvocati.length) {
        contenitore.innerHTML =
            '<div class="text-slate-600">Shinra non ha ancora toccato niente. Qui finiscono gli strumenti che usa quando gli parli: accendere una luce, leggere il meteo, avviare un timer.</div>';
        return;
    }
    contenitore.innerHTML = _toolInvocati
        .map(
            (voce) => `
        <div class="p-2 rounded bg-slate-900 border border-slate-800">
            <div class="text-indigo-400 font-bold flex items-center justify-between">
                <span>▶ Tool: ${_testoSicuro(voce.tool)}</span>
                <span class="text-[10px] text-slate-500">${voce.quando}</span>
            </div>
            <div class="text-slate-400 mt-0.5">Argomenti: <span class="text-slate-300">${_testoSicuro(JSON.stringify(voce.argomenti))}</span></div>
            <div class="text-emerald-400 mt-0.5 truncate">Risultato: ${_testoSicuro(JSON.stringify(voce.risultato))}</div>
        </div>
    `,
        )
        .join('');
}

function apriFinestraTool() {
    showModal(`
        <h3 class="text-base font-bold text-slate-100 flex items-center gap-2">
            <i data-lucide="cpu" class="w-4 h-4 text-violet-400"></i> Cosa ha fatto Shinra
        </h3>
        <p class="text-xs text-slate-400">Gli strumenti che ha usato per rispondere, dal piu' recente. Si guarda quando una risposta non torna.</p>
        <div id="tool-logs" class="max-h-[50vh] overflow-y-auto font-mono text-[11px] p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 text-slate-400 space-y-2"></div>
        <div class="flex justify-end">
            <button type="button" onclick="closeModal()" class="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-semibold">Chiudi</button>
        </div>
    `);
    _disegnaToolInvocati();
}

function showTypingIndicator() {
    const container = document.getElementById('messages-container');
    const existing = document.getElementById('typing-indicator');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.id = 'typing-indicator';
    div.className = 'flex gap-3 max-w-2xl items-center';
    div.innerHTML = `
        <div class="living-core !w-8 !h-8 !rounded-lg shrink-0 thinking">
            <i data-lucide="sparkles" class="w-4 h-4 text-white"></i>
        </div>
        <div class="bg-slate-800/80 border border-slate-700/60 rounded-2xl rounded-tl-none px-4 py-3 text-sm text-slate-200 flex items-center gap-1.5 shadow-sm">
            <span class="w-2 h-2 rounded-full bg-amber-400 typing-dot"></span>
            <span class="w-2 h-2 rounded-full bg-amber-400 typing-dot"></span>
            <span class="w-2 h-2 rounded-full bg-amber-400 typing-dot"></span>
            <span class="text-xs text-slate-400 ml-1.5 font-medium">Shinra sta elaborando...</span>
        </div>
    `;
    container.appendChild(div);
    safeCreateIcons();
    container.scrollTop = container.scrollHeight;
}

function hideTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

async function handleSend(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('user-input');
    const text = input ? input.value.trim() : '';
    if (!text) return;

    appendUserMessage(text);
    if (input) {
        input.value = '';
        input.blur(); // Chiude la tastiera virtuale su iPhone evitando blocchi di scrolling/zoom
    }

    const sendBtn = document.getElementById('send-btn');
    if (sendBtn) sendBtn.disabled = true;
    showTypingIndicator();
    updateLivingCoreState('thinking');

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                message: text,
                user_id: activeUserId || 'alessio',
                // Da quale stanza si sta parlando (issue #33). Va
                // sempre, anche scrivendo: chi scrive dalla cucina
                // intende la luce della cucina esattamente come chi
                // parla.
                satellite: satelliteDiQuestoDispositivo(),
            }),
        });
        hideTypingIndicator();
        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            appendAssistantMessage(
                `Errore dal server (${res.status}): ${errData.detail || 'Impossibile elaborare il messaggio'}`,
            );
            updateLivingCoreState('idle');
            return;
        }
        const data = await res.json();
        appendAssistantMessage(data.response, data.actions);
        if (data.actions) data.actions.forEach((a) => logAction(a.tool, a.args, a.result));
    } catch (err) {
        hideTypingIndicator();
        appendAssistantMessage(`Errore di comunicazione: ${err.message || 'Server non raggiungibile'}`);
        updateLivingCoreState('idle');
    } finally {
        if (sendBtn) sendBtn.disabled = false;
    }
}

function sendQuickPrompt(promptText) {
    document.getElementById('user-input').value = promptText;
    handleSend();
}

// ==================== QUESTO DISPOSITIVO COME PUNTO DI ASCOLTO ====================
//
// La dashboard aperta in cucina **è** un satellite: ha un microfono,
// sta in una stanza, e può dire quale. Non serve un Raspberry per
// avere «accendi la luce» che accende quella giusta — serve sapere
// da dove arriva la frase (issue #33).
//
// L'identificativo e la stanza vivono nel browser e non sul server:
// sono una proprietà di *questo* dispositivo, e un elenco di punti di
// ascolto salvato sul server sopravviverebbe ai dispositivi spenti,
// cioè manderebbe risposte in stanze vuote.

const CHIAVE_SATELLITE = 'shinra_satellite_id';
const CHIAVE_STANZA = 'shinra_satellite_stanza';

function satelliteDiQuestoDispositivo() {
    try {
        let id = localStorage.getItem(CHIAVE_SATELLITE);
        if (!id) {
            id = 'sat_' + Math.random().toString(36).slice(2, 10);
            localStorage.setItem(CHIAVE_SATELLITE, id);
        }
        return id;
    } catch {
        // Navigazione privata, o memoria del sito bloccata: si resta
        // un dispositivo senza stanza, che è come funzionava prima.
        return null;
    }
}

function stanzaDiQuestoDispositivo() {
    try {
        return localStorage.getItem(CHIAVE_STANZA) || '';
    } catch {
        return '';
    }
}

async function annunciaQuestoDispositivo() {
    const id = satelliteDiQuestoDispositivo();
    if (!id) return;
    try {
        await fetch('/api/satelliti', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                id,
                nome: 'Questo dispositivo',
                stanza: stanzaDiQuestoDispositivo(),
            }),
        });
    } catch {
        // Non poter dire dove si è non impedisce di parlare.
    }
    mostraStanzaScelta();
}

async function scegliStanza(stanza) {
    try {
        localStorage.setItem(CHIAVE_STANZA, stanza || '');
    } catch {
        alert('Il browser non mi lascia ricordare la stanza su questo dispositivo.');
        return;
    }
    await annunciaQuestoDispositivo();
}

function mostraStanzaScelta() {
    const campo = document.getElementById('scelta-stanza');
    if (!campo) return;
    const stanza = stanzaDiQuestoDispositivo();
    campo.value = stanza;
    // Verde quando la stanza c'è: chi guarda deve poter vedere in un
    // colpo d'occhio se «accendi la luce» sa dove si trova.
    campo.classList.toggle('border-emerald-600', !!stanza);
    campo.classList.toggle('border-slate-700', !stanza);
}

async function riempiStanzeNote() {
    // Le stanze non sono un elenco a parte: sono quelle già scritte
    // sugli alias dei dispositivi. Un secondo elenco divergerebbe dal
    // primo, e «Cucina» contro «cucina » sono due stanze che non si
    // incontreranno mai.
    const elenco = document.getElementById('stanze-note');
    if (!elenco) return;
    try {
        const res = await fetch('/api/aliases', { headers: getAuthHeaders() });
        const alias = await res.json();
        const stanze = [...new Set((alias || []).map((a) => (a.room || '').trim()).filter(Boolean))];
        elenco.innerHTML = stanze
            .sort()
            .map((s) => `<option value="${s}"></option>`)
            .join('');
    } catch {
        // Senza suggerimenti la stanza si scrive a mano, e va bene.
    }
}
