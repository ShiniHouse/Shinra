// ==================== SETTINGS ====================
function updateMaxTokensLabel(val) {
    const v = parseInt(val);
    let desc = `${v} token`;
    if (v <= 120) desc += ' (breve, ~20-30 parole)';
    else if (v <= 250) desc += ' (medio, ~40-60 parole)';
    else desc += ' (dettagliato, ~80-120 parole)';
    document.getElementById('cfg-max-tokens-val').textContent = desc;
}

async function loadOllamaModels(selectedModel = null) {
    const select = document.getElementById('cfg-model');
    if (!select) return;
    try {
        const res = await fetch('/api/ollama/models', { headers: getAuthHeaders() });
        const data = await res.json();
        if (data.success && data.models && data.models.length > 0) {
            const current = selectedModel || data.active_model || select.value;
            select.innerHTML = data.models.map(m => {
                const isSel = (m.name === current) ? 'selected' : '';
                const sizeInfo = m.size_gb ? ` — ${m.size_gb}` : '';
                const paramInfo = m.parameter_size ? ` (${m.parameter_size})` : '';
                return `<option value="${m.name}" ${isSel}>🧠 ${m.name}${paramInfo}${sizeInfo}</option>`;
            }).join('');
        } else {
            const current = selectedModel || 'qwen2.5:3b';
            select.innerHTML = `<option value="${current}">${current}</option>`;
        }
    } catch (e) {
        console.warn('Impossibile caricare lista modelli Ollama:', e);
    }
}

async function loadSettings() {
    try {
        const res = await fetch('/api/settings', { headers: getAuthHeaders() });
        const cfg = await res.json();
        document.getElementById('cfg-ollama-url').value = cfg.llm.ollama_url || '';

        await loadOllamaModels(cfg.llm.model);

        const maxTok = cfg.llm.max_tokens || 150;
        document.getElementById('cfg-max-tokens').value = maxTok;
        updateMaxTokensLabel(maxTok);

        document.getElementById('cfg-ha-url').value = cfg.home_assistant.url || '';
        document.getElementById('cfg-ha-token').value = cfg.home_assistant.token || '';
        document.getElementById('cfg-default-city').value = cfg.assistant.default_city || '';

        // Sicurezza
        const sec = cfg.security || {};
        const authCb = document.getElementById('cfg-sec-auth-enabled');
        if (authCb) authCb.checked = Boolean(sec.auth_enabled);
        const pinInput = document.getElementById('cfg-sec-admin-pin');
        if (pinInput) pinInput.value = sec.admin_pin || '';

        // Auto-Lock Inattività
        const autoLockVal = localStorage.getItem('shinra_inactivity_timeout_mins') || '5';
        const autoLockSelect = document.getElementById('cfg-sec-auto-lock-timeout');
        if (autoLockSelect) autoLockSelect.value = autoLockVal;

        // Assistente & Alexa Invocazione
        const asstName = cfg.assistant?.name || 'Kyra';
        const alexaInv = cfg.alexa?.invocation_name || 'kyra';
        activeAssistantName = asstName;
        document.querySelectorAll('.assistant-name-label').forEach(el => el.innerText = asstName);

        const asstInput = document.getElementById('cfg-assistant-name');
        const alexaInput = document.getElementById('cfg-alexa-invocation');
        if (asstInput) asstInput.value = asstName;
        if (alexaInput) alexaInput.value = alexaInv;
        updateAlexaGeneratorName(alexaInv);

        // Audio
        const muteCb = document.getElementById('cfg-voice-muted');
        if (muteCb) muteCb.checked = voiceMuted;
    } catch (e) { console.error('Errore loadSettings:', e); }
}

function handleAssistantNameInput(val) {
    const alexaInput = document.getElementById('cfg-alexa-invocation');
    if (alexaInput) {
        const autoVal = (val || '').toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
        alexaInput.value = autoVal || 'kyra';
        updateAlexaGeneratorName(autoVal || 'kyra');
    }
}

function getAlexaInteractionModelJson(name) {
    const cleanName = (name || 'kyra').toLowerCase().trim() || 'kyra';
    const model = {
      "interactionModel": {
        "languageModel": {
          "invocationName": cleanName,
          "intents": [
            { "name": "AMAZON.CancelIntent", "samples": [] },
            { "name": "AMAZON.HelpIntent", "samples": [] },
            { "name": "AMAZON.StopIntent", "samples": [] },
            { "name": "AMAZON.NavigateHomeIntent", "samples": [] },
            { "name": "AMAZON.FallbackIntent", "samples": [] },
            {
              "name": "TurnOnIntent",
              "slots": [{ "name": "device", "type": "AMAZON.SearchQuery" }],
              "samples": [
                "accendi {device}",
                "attiva {device}",
                "apri {device}",
                "accendere {device}",
                "attivare {device}"
              ]
            },
            {
              "name": "TurnOffIntent",
              "slots": [{ "name": "device", "type": "AMAZON.SearchQuery" }],
              "samples": [
                "spegni {device}",
                "disattiva {device}",
                "chiudi {device}",
                "spegnere {device}",
                "disattivare {device}"
              ]
            },
            {
              "name": "ActivateModeIntent",
              "slots": [{ "name": "mode", "type": "AMAZON.SearchQuery" }],
              "samples": [
                "modalità {mode}",
                "modalita {mode}",
                "avvia {mode}",
                "imposta {mode}",
                "attiva modalità {mode}",
                "attiva modalita {mode}"
              ]
            },
            {
              "name": "GeneralQueryIntent",
              "slots": [{ "name": "query", "type": "AMAZON.SearchQuery" }],
              "samples": [
                "dimmi {query}",
                "chiedi {query}",
                "fai {query}",
                "esegui {query}",
                "cosa {query}",
                "come {query}",
                "quando {query}",
                "chi {query}",
                "dove {query}",
                "perché {query}",
                "perche {query}",
                "quanto {query}",
                "quanti {query}",
                "qual è {query}",
                "qual e {query}",
                "cerca {query}",
                "spiegami {query}",
                "fammi {query}",
                "domanda {query}",
                "voglio {query}",
                "vorrei {query}",
                "puoi {query}"
              ]
            }
          ],
          "types": []
        }
      }
    };
    return JSON.stringify(model, null, 2);
}

function updateAlexaGeneratorName(val) {
    const clean = (val !== undefined ? val : (document.getElementById('cfg-alexa-invocation')?.value || 'kyra'));
    const textarea = document.getElementById('alexa-generated-json');
    if (textarea) {
        textarea.value = getAlexaInteractionModelJson(clean);
    }
    // La frase da dire davvero, costruita da cio' che c'e' nel campo.
    // Scritta a mano mentiva appena si cambiava il nome (issue #123).
    const anteprima = document.getElementById('anteprima-invocazione');
    if (anteprima) {
        anteprima.innerText = '«Alexa, apri ' + (String(clean || '').trim().toLowerCase() || 'kyra') + '»';
    }
}

function copyAlexaSkillJson() {
    const textarea = document.getElementById('alexa-generated-json');
    if (!textarea) return;
    navigator.clipboard.writeText(textarea.value).then(() => {
        const btn = document.getElementById('copy-alexa-json-btn');
        if (btn) {
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5 text-emerald-400"></i> Copiato! ✓';
            safeCreateIcons();
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                safeCreateIcons();
            }, 2500);
        }
    }).catch(() => {
        textarea.select();
        document.execCommand('copy');
        alert('JSON copiato negli appunti!');
    });
}

async function saveSettings(e) {
    e.preventDefault();
    const res = await fetch('/api/settings', { headers: getAuthHeaders() });
    const cfg = await res.json();
    cfg.llm.ollama_url = document.getElementById('cfg-ollama-url').value.trim();
    cfg.llm.model = document.getElementById('cfg-model').value.trim();
    cfg.llm.max_tokens = parseInt(document.getElementById('cfg-max-tokens').value) || 150;
    cfg.home_assistant.url = document.getElementById('cfg-ha-url').value.trim();
    cfg.home_assistant.token = document.getElementById('cfg-ha-token').value.trim();
    cfg.assistant.default_city = document.getElementById('cfg-default-city').value.trim();

    if (!cfg.assistant) cfg.assistant = {};
    if (!cfg.alexa) cfg.alexa = {};
    cfg.assistant.name = document.getElementById('cfg-assistant-name')?.value.trim() || 'Kyra';
    cfg.alexa.invocation_name = document.getElementById('cfg-alexa-invocation')?.value.trim().toLowerCase() || 'kyra';

    if (!cfg.security) cfg.security = {};
    cfg.security.auth_enabled = Boolean(document.getElementById('cfg-sec-auth-enabled')?.checked);
    cfg.security.admin_pin = document.getElementById('cfg-sec-admin-pin')?.value.trim() || '';

    const saveRes = await fetch('/api/settings', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(cfg)
    });

    if (saveRes.ok) {
        alert('Impostazioni salvate con successo.');
        await checkAuthStatus();
        await checkSystemHealth();
        await loadSettings();
    } else {
        const errData = await saveRes.json().catch(() => ({}));
        alert(`Errore nel salvataggio: ${errData.detail || saveRes.statusText}`);
    }
}

async function testHaConnection() {
    const resultBox = document.getElementById('ha-test-result');
    resultBox.classList.remove('hidden', 'bg-emerald-950', 'text-emerald-300', 'bg-rose-950', 'text-rose-300', 'bg-yellow-950', 'text-yellow-300');
    resultBox.classList.add('bg-slate-800', 'text-slate-300');
    resultBox.innerHTML = '<span class="animate-pulse">Test di connessione a Home Assistant in corso...</span>';

    // Prima salviamo le credenziali inserite
    const res = await fetch('/api/settings', { headers: getAuthHeaders() });
    const cfg = await res.json();
    cfg.home_assistant.url = document.getElementById('cfg-ha-url').value.trim();
    cfg.home_assistant.token = document.getElementById('cfg-ha-token').value.trim();
    await fetch('/api/settings', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(cfg)
    });

    // Poi verifichiamo lo stato
    const statusRes = await fetch('/api/status', { headers: getAuthHeaders() });
    const statusData = await statusRes.json();
    const ha = statusData.home_assistant || {};

    resultBox.classList.remove('bg-slate-800', 'text-slate-300');
    if (ha.status === 'ok') {
        resultBox.classList.add('bg-emerald-950', 'text-emerald-300', 'border', 'border-emerald-800');
        resultBox.innerHTML = `✅ <strong>Connessione riuscita!</strong> Home Assistant risponde correttamente su ${ha.url || ''}.`;
    } else if (ha.status === 'unauthorized') {
        resultBox.classList.add('bg-rose-950', 'text-rose-300', 'border', 'border-rose-800');
        resultBox.innerHTML = `❌ <strong>Token non valido (401 Unauthorized):</strong> Genera un nuovo Long-Lived Token dal tuo profilo Home Assistant e incollalo qui.`;
    } else if (ha.status === 'unconfigured') {
        resultBox.classList.add('bg-yellow-950', 'text-yellow-300', 'border', 'border-yellow-800');
        resultBox.innerHTML = `⚠️ <strong>Token non inserito:</strong> Incolla il tuo Long-Lived Token.`;
    } else {
        resultBox.classList.add('bg-rose-950', 'text-rose-300', 'border', 'border-rose-800');
        const errMsg = ha.message || "Verifica l'indirizzo IP e la porta 8123";
        resultBox.innerHTML = `❌ <strong>Home Assistant non raggiungibile:</strong> ${errMsg}.`;
    }
    await checkSystemHealth();
}

// Modal Helpers
function showModal(contentHtml, isWide = false) {
    const modal = document.getElementById('modal-container');
    if (isWide) {
        // Niente `overflow-hidden`: serve a far sporgere la X di
        // chiusura fuori dall'angolo, dove la cercano tutti. Gli
        // angoli restano arrotondati lo stesso, perche' a toccarli
        // sono la barra in alto e quella in basso, che hanno il
        // proprio raggio.
        modal.className =
            "bg-slate-900 border border-slate-800 rounded-2xl max-w-6xl w-full p-0 shadow-2xl relative";
    } else {
        modal.className = "bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4";
    }
    modal.innerHTML = contentHtml;
    document.getElementById('modal-backdrop').style.display = 'flex';
    safeCreateIcons();
}

function closeModal() {
    document.getElementById('modal-backdrop').style.display = 'none';
}

// Status Health Check
async function checkSystemHealth() {
    try {
        const res = await fetch('/api/status', { headers: getAuthHeaders() });
        const data = await res.json();

        const ollamaBadge = document.getElementById('ollama-status');
        if (data.ollama && data.ollama.status === 'online') {
            ollamaBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400"></span><span>Ollama: Online</span>`;
            ollamaBadge.style.cssText = 'display:flex; align-items:center; gap:0.375rem; padding:0.25rem 0.625rem; border-radius:9999px; font-size:11px; font-weight:500; background:rgba(6,46,37,0.7); border:1px solid #065f46; color:#6ee7b7';
            const badge = document.getElementById('model-name-badge');
            if (badge) badge.innerText = data.ollama.active_model || data.ollama.current_model || 'online';
        } else {
            ollamaBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500"></span><span>Ollama: Offline</span>`;
            ollamaBadge.style.cssText = 'display:flex; align-items:center; gap:0.375rem; padding:0.25rem 0.625rem; border-radius:9999px; font-size:11px; font-weight:500; background:rgba(69,10,10,0.7); border:1px solid #7f1d1d; color:#fca5a5';
        }

        const haBadge = document.getElementById('ha-status');
        if (data.home_assistant && data.home_assistant.status === 'ok') {
            haBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400"></span><span>HA: Connesso</span>`;
            haBadge.style.cssText = 'display:flex; align-items:center; gap:0.375rem; padding:0.25rem 0.625rem; border-radius:9999px; font-size:11px; font-weight:500; background:rgba(6,46,37,0.7); border:1px solid #065f46; color:#6ee7b7';
        } else {
            const msg = (data.home_assistant && data.home_assistant.message) ? data.home_assistant.message : 'Non configurato';
            haBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-yellow-400"></span><span>HA: ${msg}</span>`;
            haBadge.style.cssText = 'display:flex; align-items:center; gap:0.375rem; padding:0.25rem 0.625rem; border-radius:9999px; font-size:11px; font-weight:500; background:rgba(66,32,6,0.7); border:1px solid #92400e; color:#fde68a';
        }
    } catch (e) { console.warn('Health check error:', e); }
}

// PWA Installation Prompt
let _deferredPwaPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    _deferredPwaPrompt = e;
    const btn = document.getElementById('pwa-settings-install-btn');
    if (btn) btn.classList.remove('opacity-50');
});

async function installPwa() {
    if (_deferredPwaPrompt) {
        _deferredPwaPrompt.prompt();
        const { outcome } = await _deferredPwaPrompt.userChoice;
        if (outcome === 'accepted') {
            const btn = document.getElementById('pwa-settings-install-btn');
            if (btn) btn.innerHTML = '<i data-lucide="check" class="w-3.5 h-3.5"></i> App Installata';
        }
        _deferredPwaPrompt = null;
    } else {
        alert('Per installare l\'app:\n\n🍎 Su iPhone/iPad (Safari):\nTocca il pulsante Condividi e scegli "Aggiungi a schermata Home".\n\n🤖 Su Android/PC (Chrome/Edge):\nClicca sui 3 puntini in alto a destra e seleziona "Installa app" o "Aggiungi a Home".');
    }
}

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js').catch(e => console.warn('SW error:', e));
    });
}

// Inizializzazione — eseguita dopo il caricamento completo della pagina
window.addEventListener('load', function() {
    initPalette();
    initTheme();
    setInterval(applyTheme, 30000);
    checkAuthStatus();
    initTabs();
    safeCreateIcons();
    initVoiceEngine();
    loadUsersDropdown();
    updateEmpatheticGreeting();
    setInterval(updateEmpatheticGreeting, 60000);
    updateLivingCoreState('idle');
    loadTimers();
    loadReminders();
    startTimerTick();
    // Cosa scattera' fra poco. Il prossimo scatto lo calcola il
    // server quando la regola viene salvata o scatta: un minuto di
    // ritardo qui non e' un difetto, e mezz'ora di intervallo lo
    // sarebbe — la colonna deve raccontare adesso.
    caricaProssimiScatti();
    setInterval(caricaProssimiScatti, 60000);
    collegaEventi();
    // Questo dispositivo si presenta come punto di ascolto: da dove
    // parla decide quale luce accende «accendi la luce» (issue #33).
    riempiStanzeNote();
    annunciaQuestoDispositivo();
    checkSystemHealth();
    setInterval(checkSystemHealth, 8000);
    // La presenza non va interrogata a intervalli: arriva sul
    // WebSocket quando cambia. Questa e' solo la fotografia iniziale.
    caricaPresenza();
});
