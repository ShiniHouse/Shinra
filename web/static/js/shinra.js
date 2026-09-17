function safeCreateIcons() {
    try {
        if (typeof lucide !== 'undefined' && lucide.createIcons) {
            lucide.createIcons();
        }
    } catch (e) { console.warn('Lucide icon render:', e); }
}

// ==================== PALETTE MANAGER (3 DESIGN ATMOSPHERES) ====================
let currentPalette = localStorage.getItem('shinra_palette') || 'aurora';

function initPalette() {
    currentPalette = localStorage.getItem('shinra_palette') || 'aurora';
    setPalette(currentPalette);
}

function setPalette(name) {
    if (!['aurora', 'sandstone', 'stealth'].includes(name)) name = 'aurora';
    currentPalette = name;
    localStorage.setItem('shinra_palette', name);
    document.documentElement.setAttribute('data-palette', name);

    // Update UI Selection Badges & Border Highlights
    ['aurora', 'sandstone', 'stealth'].forEach(p => {
        const card = document.getElementById(`palette-card-${p}`);
        const badge = document.getElementById(`badge-palette-${p}`);
        if (card) {
            if (p === name) {
                card.classList.add('border-indigo-500', 'ring-2', 'ring-indigo-500/40', 'bg-slate-900/90');
                card.classList.remove('border-slate-800', 'bg-slate-900/50');
            } else {
                card.classList.remove('border-indigo-500', 'ring-2', 'ring-indigo-500/40', 'bg-slate-900/90');
                card.classList.add('border-slate-800', 'bg-slate-900/50');
            }
        }
        if (badge) {
            badge.classList.toggle('hidden', p !== name);
        }
    });
    safeCreateIcons();
}

// ==================== 3-WAY THEME ENGINE (AUTO SOLAR / DAY / NIGHT) ====================
let currentThemeSetting = localStorage.getItem('shinra_theme_mode') || 'auto';

function getSolarTheme() {
    const now = new Date();
    const hour = now.getHours() + (now.getMinutes() / 60);
    // Giorno Solare: dalle 07:00 alle 19:30, Notte: dalle 19:30 alle 07:00
    return (hour >= 7.0 && hour < 19.5) ? 'light' : 'dark';
}

function initTheme() {
    currentThemeSetting = localStorage.getItem('shinra_theme_mode') || 'auto';
    applyTheme();
}

function cycleTheme() {
    if (currentThemeSetting === 'auto') {
        currentThemeSetting = 'light';
    } else if (currentThemeSetting === 'light') {
        currentThemeSetting = 'dark';
    } else {
        currentThemeSetting = 'auto';
    }
    localStorage.setItem('shinra_theme_mode', currentThemeSetting);
    applyTheme();
}

function applyTheme() {
    let effectiveTheme = currentThemeSetting;
    if (currentThemeSetting === 'auto') {
        effectiveTheme = getSolarTheme();
    }

    if (effectiveTheme === 'light') {
        document.documentElement.classList.remove('dark');
        document.documentElement.classList.add('light');
    } else {
        document.documentElement.classList.remove('light');
        document.documentElement.classList.add('dark');
    }

    updateThemeUI(effectiveTheme);
}

function updateThemeUI(effectiveTheme) {
    const icon = document.getElementById('theme-toggle-icon');
    const label = document.getElementById('theme-toggle-label');
    const btn = document.getElementById('theme-toggle-btn');
    if (!icon || !label) return;

    if (currentThemeSetting === 'auto') {
        const isDay = (effectiveTheme === 'light');
        icon.innerHTML = `<i data-lucide="${isDay ? 'sun-medium' : 'moon'}" class="w-3.5 h-3.5 ${isDay ? 'text-amber-500' : 'text-indigo-400'}"></i>`;
        label.innerHTML = `Auto <span class="text-[10px] opacity-75 font-normal">(${isDay ? 'Giorno' : 'Notte'})</span>`;
        if (btn) btn.title = `Modalità Automatica attiva (${isDay ? 'Luce Solare fino alle 19:30' : 'Modalità Notturna fino alle 07:00'}). Clicca per forzare Giorno.`;
    } else if (currentThemeSetting === 'light') {
        icon.innerHTML = `<i data-lucide="sun" class="w-3.5 h-3.5 text-amber-500"></i>`;
        label.innerText = 'Giorno';
        if (btn) btn.title = 'Modalità Giorno forzata. Clicca per passare a Notte.';
    } else {
        icon.innerHTML = `<i data-lucide="moon" class="w-3.5 h-3.5 text-indigo-400"></i>`;
        label.innerText = 'Notte';
        if (btn) btn.title = 'Modalità Notte forzata. Clicca per tornare in Auto.';
    }
    safeCreateIcons();
}

// ==================== SECURITY & AUTH ENGINE ====================
function getAuthHeaders(customHeaders = {}) {
    const token = sessionStorage.getItem('shinra_auth_token') || '';
    const headers = { 'Content-Type': 'application/json', ...customHeaders };
    if (token) {
        headers['X-Shinra-Auth'] = `Bearer ${token}`;
    }
    return headers;
}

// Un corpo `FormData` porta con se' il proprio Content-Type, e dentro
// c'e' il «boundary»: la stringa che separa i pezzi del caricamento.
// Solo il browser la conosce, perche' se la inventa lui al momento
// dell'invio. Scriverci sopra `application/json` non cambia il corpo,
// cambia l'etichetta: il server legge «e' JSON», prova a leggerlo come
// JSON, non trova il file, e risponde 422.
//
// E' esattamente cosi' che il microfono della dashboard non ha mai
// trascritto niente: la rotta era giusta, il file partiva davvero, ma
// arrivava con l'etichetta sbagliata.
function intestazioniPerModulo() {
    const intestazioni = getAuthHeaders();
    delete intestazioni['Content-Type'];
    return intestazioni;
}

// ============ UN RIFIUTO NON DEVE SEMBRARE UN VUOTO ============
//
// Quasi ogni schermata legge cosi':
//
//     const dati = await res.json();
//     render(dati.regole || []);
//
// Con un 401 il corpo e' `{"detail": ...}`, `dati.regole` non esiste, e
// la schermata mostra «non c'e' niente». «Non c'e' niente» e «non ho il
// permesso di vederlo» diventano la stessa cosa, in una decina di posti
// — ed e' esattamente la domanda con cui e' cominciata la issue #125.
//
// Il controllo sta qui, attorno a `fetch`, e non in ogni chiamata, per
// la stessa ragione per cui il contesto del registro sta in un
// middleware e non nelle singole rotte: cosi' nessuna chiamata nuova
// puo' dimenticarsene.
(function sorvegliaIRifiuti() {
    const originale = window.fetch.bind(window);
    window.fetch = async (risorsa, opzioni) => {
        const risposta = await originale(risorsa, opzioni);
        const indirizzo = typeof risorsa === 'string' ? risorsa : (risorsa && risorsa.url) || '';
        // Le rotte di accesso rispondono 401 quando il PIN e'
        // sbagliato: li' non e' un guasto, e' la risposta, e chi sta
        // entrando la sta gia' leggendo sotto la tastiera.
        const daSorvegliare = indirizzo.startsWith('/api/') && !indirizzo.startsWith('/api/auth/');
        if (daSorvegliare && (risposta.status === 401 || risposta.status === 403)) {
            mostraRifiuto(risposta.status);
        }
        return risposta;
    };
})();

function mostraRifiuto(stato) {
    let barra = document.getElementById('barra-rifiuto');
    if (!barra) {
        barra = document.createElement('div');
        barra.id = 'barra-rifiuto';
        barra.className = 'fixed top-0 left-0 right-0 z-[1000] px-4 py-2.5 bg-rose-600 text-white text-xs font-semibold flex items-center justify-center gap-3 shadow-lg';
        document.body.appendChild(barra);
    }
    // Il secondo periodo e' il punto di tutta la correzione: dice che
    // le schermate vuote potrebbero non esserlo.
    const messaggio = stato === 403
        ? 'Non hai il permesso di vedere questa parte. Quello che manca non e\' assente: e\' riservato.'
        : 'La sessione e\' scaduta. Le schermate che vedi vuote potrebbero non esserlo: rientra per saperlo.';
    barra.innerHTML = `<span>${messaggio}</span>`;
    if (stato !== 403) {
        const entra = document.createElement('button');
        entra.type = 'button';
        entra.className = 'px-2.5 py-1 rounded-lg bg-white/20 hover:bg-white/30 transition font-bold';
        entra.textContent = 'Rientra';
        entra.onclick = () => { nascondiRifiuto(); lockSession(); };
        barra.appendChild(entra);
    }
    const chiudi = document.createElement('button');
    chiudi.type = 'button';
    chiudi.className = 'px-2 py-1 rounded-lg hover:bg-white/20 transition';
    chiudi.textContent = '✕';
    chiudi.title = 'Nascondi l\'avviso';
    chiudi.onclick = nascondiRifiuto;
    barra.appendChild(chiudi);
    barra.classList.remove('hidden');
}

function nascondiRifiuto() {
    const barra = document.getElementById('barra-rifiuto');
    if (barra) barra.classList.add('hidden');
}

async function checkAuthStatus() {
    try {
        const res = await fetch('/api/auth/status', {
            headers: getAuthHeaders()
        });
        if (!res.ok) return;
        const data = await res.json();
        const lockBtn = document.getElementById('lock-session-btn');
        const lockModal = document.getElementById('lock-screen-modal');

        if (data.auth_enabled) {
            if (lockBtn) lockBtn.style.display = 'flex';
            if (!data.authenticated && data.protect_dashboard) {
                if (lockModal) lockModal.style.display = 'flex';
                caricaProfiliAccesso();
            } else {
                if (lockModal) lockModal.style.display = 'none';
            }
        } else {
            if (lockBtn) lockBtn.style.display = 'none';
            if (lockModal) lockModal.style.display = 'none';
        }
        safeCreateIcons();
    } catch (e) {
        console.warn('Errore verifica stato autenticazione:', e);
    }
}

// ---- Accesso: prima si sceglie chi si e', poi si digita il proprio PIN ----
let _profiloDaAccedere = null;

async function caricaProfiliAccesso() {
    const box = document.getElementById('unlock-profili');
    if (!box) return;
    try {
        const res = await fetch('/api/auth/profili');
        if (!res.ok) return;
        const profili = (await res.json()).filter(p => p.ha_pin);

        if (profili.length === 0) {
            box.innerHTML = `<div class="col-span-2 text-xs text-slate-400 p-3 rounded-xl bg-slate-950 border border-slate-800">
                Nessun profilo ha ancora un PIN. Il PIN del primo accesso e' nel log del server.</div>`;
            return;
        }

        // Con un solo profilo la scelta non serve: si va dritti al PIN.
        if (profili.length === 1) {
            box.classList.add('hidden');
            scegliProfiloAccesso(profili[0].id, profili[0].name);
            return;
        }

        box.classList.remove('hidden');
        box.innerHTML = profili.map(p => `
            <button type="button" onclick="scegliProfiloAccesso('${p.id}', '${(p.name || '').replace(/'/g, "\\'")}')"
                class="p-3 rounded-2xl bg-slate-950 border border-slate-800 hover:border-indigo-500 hover:bg-slate-900 transition text-left flex items-center gap-2.5">
                <span class="w-8 h-8 rounded-xl bg-indigo-600/25 text-indigo-300 flex items-center justify-center font-bold text-sm shrink-0">
                    ${(p.name || '?').charAt(0).toUpperCase()}
                </span>
                <span class="text-sm font-semibold text-slate-200 truncate">${p.name || p.id}</span>
            </button>`).join('');
    } catch (e) {
        console.warn('Impossibile caricare i profili di accesso:', e);
    }
}

function scegliProfiloAccesso(userId, nome) {
    _profiloDaAccedere = userId;
    const box = document.getElementById('unlock-profili');
    const form = document.getElementById('unlock-form-pin');
    const etichetta = document.getElementById('unlock-profilo-scelto');
    const sottotitolo = document.getElementById('unlock-sottotitolo');
    if (box) box.classList.add('hidden');
    if (form) form.classList.remove('hidden');
    if (etichetta) etichetta.innerText = nome || userId;
    if (sottotitolo) sottotitolo.innerText = 'Inserisci il tuo PIN.';
    setTimeout(() => document.getElementById('unlock-pin-input')?.focus(), 80);
}

function tornaAllaSceltaProfilo() {
    _profiloDaAccedere = null;
    const box = document.getElementById('unlock-profili');
    const form = document.getElementById('unlock-form-pin');
    const sottotitolo = document.getElementById('unlock-sottotitolo');
    const errBox = document.getElementById('unlock-error-msg');
    if (box) box.classList.remove('hidden');
    if (form) form.classList.add('hidden');
    if (sottotitolo) sottotitolo.innerText = 'Scegli il tuo profilo per accedere.';
    if (errBox) errBox.classList.add('hidden');
    caricaProfiliAccesso();
}

async function handleUnlockSubmit(e) {
    if (e) e.preventDefault();
    const pinInput = document.getElementById('unlock-pin-input');
    const errBox = document.getElementById('unlock-error-msg');
    const pin = (pinInput ? pinInput.value : '').trim();
    if (!pin) return;

    try {
        const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ pin: pin, user_id: _profiloDaAccedere })
        });

        if (res.ok) {
            const data = await res.json();
            sessionStorage.setItem('shinra_auth_token', data.token);
            // L'utente attivo non e' piu' una scelta da menu: e' chi
            // ha appena dimostrato di essere se stesso con il PIN.
            if (data.utente && data.utente.id) {
                activeUserId = data.utente.id;
                try { localStorage.setItem('shinra_active_user', data.utente.id); } catch (e) {}
                if (typeof updateActiveUserBanner === 'function') updateActiveUserBanner();
                if (typeof loadUsersDropdown === 'function') loadUsersDropdown();
            }
            if (errBox) errBox.classList.add('hidden');
            if (pinInput) pinInput.value = '';
            const lockModal = document.getElementById('lock-screen-modal');
            if (lockModal) lockModal.style.display = 'none';

            // Ricarica i dati protetti
            checkSystemHealth();
            caricaPresenza();
            loadKnowledge();
            loadSettings();
            loadTimers();
            loadReminders();
            // Il WebSocket era stato rifiutato senza sessione: ora si puo'.
            _attesaRiconnessione = 1000;
            collegaEventi();
        } else {
            const errData = await res.json().catch(() => ({}));
            if (errBox) {
                errBox.innerText = errData.detail || 'PIN o Password errata.';
                errBox.classList.remove('hidden');
            }
            if (pinInput) {
                pinInput.value = '';
                pinInput.focus();
            }
        }
    } catch (err) {
        if (errBox) {
            errBox.innerText = 'Errore di connessione al server.';
            errBox.classList.remove('hidden');
        }
    }
}

async function lockSession() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: getAuthHeaders()
        });
    } catch (e) {}
    sessionStorage.removeItem('shinra_auth_token');
    await checkAuthStatus();
}

// ==================== INACTIVITY AUTO-LOCK CONTROLLER ====================
let inactivityTimeoutMinutes = parseInt(localStorage.getItem('shinra_inactivity_timeout_mins') || '5', 10);
let inactivityTimer = null;

function setAutoLockTimeout(val) {
    inactivityTimeoutMinutes = parseInt(val, 10);
    localStorage.setItem('shinra_inactivity_timeout_mins', inactivityTimeoutMinutes);
    resetInactivityTimer();
}

function resetInactivityTimer() {
    if (inactivityTimer) {
        clearTimeout(inactivityTimer);
        inactivityTimer = null;
    }

    if (inactivityTimeoutMinutes <= 0) return;
    const lockModal = document.getElementById('lock-screen-modal');
    if (lockModal && lockModal.style.display === 'flex') return;

    inactivityTimer = setTimeout(async () => {
        const isAuthEnabled = document.getElementById('cfg-sec-auth-enabled')?.checked;
        const token = sessionStorage.getItem('shinra_auth_token');
        if (isAuthEnabled || token) {
            console.log(`[Shinra Security] Auto-lock attivato dopo ${inactivityTimeoutMinutes} min di inattività.`);
            await lockSession();
        }
    }, inactivityTimeoutMinutes * 60 * 1000);
}

['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'].forEach(evt => {
    window.addEventListener(evt, resetInactivityTimer, { passive: true });
});

function setVoiceMuteState(isMuted) {
    voiceMuted = isMuted;
    localStorage.setItem('shinra_voice_muted', isMuted);
    if (voiceMuted) {
        if (currentAudioPlayer) {
            currentAudioPlayer.pause();
            currentAudioPlayer = null;
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    }
    syncVoiceUI();
}

// ==================== SHINRA LIVING CORE & EMPATHIC GREETING ====================
function updateLivingCoreState(state) {
    const core = document.getElementById('header-living-core');
    if (!core) return;
    core.classList.remove('listening', 'thinking', 'speaking');
    if (state && state !== 'idle') {
        core.classList.add(state);
    }
}

function updateEmpatheticGreeting() {
    const el = document.getElementById('empathetic-greeting');
    if (!el) return;
    const hour = new Date().getHours();
    const userName = (typeof activeUserId !== 'undefined' && activeUserId) ? (activeUserId.charAt(0).toUpperCase() + activeUserId.slice(1)) : 'Alessio';

    let greeting = '';
    if (hour >= 5 && hour < 12) {
        greeting = `Buongiorno ${userName}. Casa accogliente e pronta per la giornata.`;
    } else if (hour >= 12 && hour < 18) {
        greeting = `Buon pomeriggio ${userName}. Gestisco la casa, timer e notizie per te.`;
    } else if (hour >= 18 && hour < 23) {
        greeting = `Buonasera ${userName}. Ambienti regolati per il relax serale.`;
    } else {
        greeting = `Notte fonda ${userName}. Modalità silenziosa attiva.`;
    }
    el.innerText = greeting;
}

let activeUserId = "alessio";
let usersData = [];


// Store del display originale per ogni tab
const tabDisplayMap = {
    'console':     'grid',
    'knowledge':   'block',
    'sources':     'block',
    'aliases':     'block',
    'automazioni': 'block',
    'users':       'block',
    'settings':    'block',
};

// Le destinazioni di prima che adesso sono la stessa schermata.
// Stanno qui e non nei punti che le chiamano: una scorciatoia scritta
// altrove nella pagina — o un collegamento che qualcuno si e' salvato
// — deve continuare a portare dove serve, non in una scheda che non
// esiste piu'. Riferimento: #128.
const SCHEDE_UNITE = {
    'modes':  'automazioni',
    'regole': 'automazioni',
};

// Le quattro che stanno dietro «Configurazione». Il pulsante di primo
// livello si accende per tutte e quattro: chi e' dentro deve vedere da
// dove ci e' entrato, altrimenti la barra non dice piu' dov'e'.
const SCHEDE_DI_CONFIGURAZIONE = ['knowledge', 'sources', 'users', 'settings'];

// ==================== MOBILE MENU HAMBURGER CONTROLLER ====================
let isMobileMenuOpen = false;

function toggleMobileMenu() {
    const drawer = document.getElementById('mobile-menu-drawer');
    const icon = document.getElementById('mobile-menu-icon');
    if (!drawer) return;

    isMobileMenuOpen = !isMobileMenuOpen;
    if (isMobileMenuOpen) {
        drawer.classList.remove('hidden');
        if (icon) icon.setAttribute('data-lucide', 'x');
    } else {
        drawer.classList.add('hidden');
        if (icon) icon.setAttribute('data-lucide', 'menu');
    }
    safeCreateIcons();
}

function switchTabMobile(tabId) {
    switchTab(tabId);
    toggleMobileMenu();
}

// ==================== MENU DI CONFIGURAZIONE (desktop) ====================
let _menuConfigurazioneAperto = false;

function chiudiMenuConfigurazione() {
    const menu = document.getElementById('menu-configurazione');
    const bottone = document.getElementById('tab-btn-configurazione');
    if (menu) menu.classList.add('hidden');
    if (bottone) bottone.setAttribute('aria-expanded', 'false');
    _menuConfigurazioneAperto = false;
}

function alternaMenuConfigurazione(evento) {
    // Senza questo, il clic arriva anche al guardiano qui sotto e il
    // menu si chiude nello stesso istante in cui si e' aperto.
    if (evento) evento.stopPropagation();
    const menu = document.getElementById('menu-configurazione');
    const bottone = document.getElementById('tab-btn-configurazione');
    if (!menu) return;
    if (_menuConfigurazioneAperto) { chiudiMenuConfigurazione(); return; }
    menu.classList.remove('hidden');
    if (bottone) bottone.setAttribute('aria-expanded', 'true');
    _menuConfigurazioneAperto = true;
}

// Un menu che resta aperto dietro alla schermata e' un pezzo di
// interfaccia che nessuno ha chiesto: si chiude da fuori e con Esc.
document.addEventListener('click', function (evento) {
    if (!_menuConfigurazioneAperto) return;
    const menu = document.getElementById('menu-configurazione');
    const bottone = document.getElementById('tab-btn-configurazione');
    if (menu && menu.contains(evento.target)) return;
    if (bottone && bottone.contains(evento.target)) return;
    chiudiMenuConfigurazione();
});

document.addEventListener('keydown', function (evento) {
    if (evento.key === 'Escape') chiudiMenuConfigurazione();
});

// Tab Navigation — usa style.display invece di hidden class (evita conflitti Tailwind JIT)
function switchTab(tabId) {
    // Le vecchie destinazioni prima di tutto: da qui in giu' esiste
    // solo il nome nuovo.
    tabId = SCHEDE_UNITE[tabId] || tabId;

    // Nasconde tutti i tab
    Object.keys(tabDisplayMap).forEach(id => {
        const el = document.getElementById(`tab-${id}`);
        if (el) el.style.display = 'none';
    });

    // Resetta tutti i pulsanti desktop
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('bg-indigo-600/30', 'text-indigo-300', 'border-indigo-500/40', 'border');
        el.classList.add('text-slate-400');
    });

    // Mostra il tab selezionato
    const targetEl = document.getElementById(`tab-${tabId}`);
    if (targetEl) targetEl.style.display = tabDisplayMap[tabId] || 'block';

    // Attiva il pulsante selezionato. Le quattro schede dietro
    // «Configurazione» non hanno un pulsante proprio: si accende il
    // loro ingresso, che e' da dove ci si e' passati.
    const btn = document.getElementById(`tab-btn-${tabId}`)
        || (SCHEDE_DI_CONFIGURAZIONE.includes(tabId)
            ? document.getElementById('tab-btn-configurazione')
            : null);
    if (btn) {
        btn.classList.add('bg-indigo-600/30', 'text-indigo-300', 'border-indigo-500/40', 'border');
        btn.classList.remove('text-slate-400');
    }

    // Scegliere dove andare chiude il menu da cui si e' scelto.
    chiudiMenuConfigurazione();

    if (tabId === 'knowledge') loadKnowledge();
    if (tabId === 'sources') loadSources();
    if (tabId === 'aliases') loadAliases();
    // Una scheda sola, due elenchi: le automazioni e le routine da cui
    // nascono. Caricarne uno solo lascerebbe meta' schermata vuota
    // senza che niente lo spieghi.
    if (tabId === 'automazioni') { loadRegole(); loadModes(); disegnaScorciatoia(); }
    if (tabId === 'users') loadUsers();
    if (tabId === 'settings') { loadSettings(); preparaSezioniImpostazioni(); }
}

// ============ SEZIONI DELLE IMPOSTAZIONI (issue #124) ============
// La scheda era 421 righe di markup con tutto aperto insieme: non una
// schermata da leggere, una schermata in cui si cerca. Adesso si apre
// quella che serve.
//
// L'apri-e-chiudi lo fa `<details>` da solo, anche senza questo
// copione: qui c'e' soltanto il ricordo di quale era aperta, per chi
// torna a sistemare la stessa cosa.

const MEMORIA_SEZIONE = 'shinra.impostazioni.sezione';

// `localStorage` non risponde sempre: finestra anonima, dati del sito
// bloccati, spazio esaurito. Sono comodita', non dati: se manca, la
// schermata si apre sulla prima sezione e non se ne accorge nessuno.
function _ricordaSezione(nome) {
    try {
        if (nome) {
            window.localStorage.setItem(MEMORIA_SEZIONE, nome);
        } else {
            window.localStorage.removeItem(MEMORIA_SEZIONE);
        }
    } catch (e) { /* senza memoria si vive */ }
}

function _sezioneRicordata() {
    try {
        return window.localStorage.getItem(MEMORIA_SEZIONE);
    } catch (e) {
        return null;
    }
}

function preparaSezioniImpostazioni() {
    const sezioni = document.querySelectorAll('.sezione-impostazioni');
    if (!sezioni.length) return;

    const ricordata = _sezioneRicordata();
    if (ricordata) {
        let trovata = false;
        sezioni.forEach(sezione => {
            const sua = sezione.getAttribute('data-sezione') === ricordata;
            sezione.open = sua;
            trovata = trovata || sua;
        });
        // Una sezione tolta dalla pagina lascia in memoria un nome che
        // non apre piu' niente: meglio la prima che nessuna.
        if (!trovata) {
            sezioni[0].open = true;
            _ricordaSezione(null);
        }
    }

    sezioni.forEach(sezione => {
        if (sezione.dataset.ascolta === 'si') return;
        sezione.dataset.ascolta = 'si';
        sezione.addEventListener('toggle', () => {
            if (!sezione.open) {
                // Chiudere l'ultima aperta non lascia un ricordo che
                // la riaprirebbe al prossimo giro.
                if (_sezioneRicordata() === sezione.getAttribute('data-sezione')) {
                    _ricordaSezione(null);
                }
                return;
            }
            // Una sola aperta per volta: e' il punto della scheda —
            // trovare un'impostazione dev'essere un clic, non uno
            // scorrimento lungo un muro.
            sezioni.forEach(altra => {
                if (altra !== sezione) altra.open = false;
            });
            _ricordaSezione(sezione.getAttribute('data-sezione'));
            safeCreateIcons();
        });
    });
}

// Inizializzazione del layout tab all'avvio
function initTabs() {
    Object.keys(tabDisplayMap).forEach(id => {
        const el = document.getElementById(`tab-${id}`);
        if (el) el.style.display = id === 'console' ? tabDisplayMap['console'] : 'none';
    });
}

// ==================== USER AVATAR & PROFILE HELPERS ====================
function getUserAvatarInfo(u) {
    const gender = u.gender || 'unspecified';
    const age = u.age_group || 'adult';
    const role = u.role || 'adult';
    const avatarType = u.avatar_type || '';

    if (role === 'guest' || u.id === 'guest' || avatarType === 'guest') {
        return { emoji: '🤖', label: 'Ospite', color: 'slate', badge: 'Ospite', border: 'border-slate-700', bg: 'bg-slate-800/80', text: 'text-slate-300' };
    }
    if (avatarType === 'female_child' || (age === 'child' && gender === 'female')) {
        return { emoji: '👧', label: 'Bimba', color: 'pink', badge: 'Junior 👧', border: 'border-pink-500/50', bg: 'bg-pink-500/20', text: 'text-pink-300' };
    }
    if (avatarType === 'male_child' || (age === 'child' && gender === 'male')) {
        return { emoji: '👦', label: 'Bimbo', color: 'cyan', badge: 'Junior 👦', border: 'border-cyan-500/50', bg: 'bg-cyan-500/20', text: 'text-cyan-300' };
    }
    if (avatarType === 'female_adult' || (age !== 'child' && gender === 'female')) {
        return { emoji: '👩', label: 'Donna', color: 'rose', badge: 'Famiglia', border: 'border-rose-500/50', bg: 'bg-rose-500/20', text: 'text-rose-300' };
    }
    if (avatarType === 'male_adult' || (age !== 'child' && gender === 'male')) {
        return { emoji: '👨', label: 'Uomo', color: 'indigo', badge: 'Famiglia', border: 'border-indigo-500/50', bg: 'bg-indigo-500/20', text: 'text-indigo-300' };
    }
    return { emoji: '🧑', label: 'Membro', color: 'amber', badge: 'Membro', border: 'border-amber-500/50', bg: 'bg-amber-500/20', text: 'text-amber-300' };
}

// Active User Management
async function loadUsersDropdown() {
    try {
        const res = await fetch('/api/users', { headers: getAuthHeaders() });
        usersData = await res.json();
        const select = document.getElementById('user-select');
        const mobileSelect = document.getElementById('mobile-user-select');
        const optionsHtml = usersData.map(u => {
            const av = getUserAvatarInfo(u);
            return `<option value="${u.id}" ${u.id === activeUserId ? 'selected' : ''}>${av.emoji} ${u.name} (${u.role})</option>`;
        }).join('');

        if (select) select.innerHTML = optionsHtml;
        if (mobileSelect) mobileSelect.innerHTML = optionsHtml;
        updateActiveUserBanner();
    } catch (e) { console.error(e); }
}

function changeActiveUser(userId) {
    activeUserId = userId;
    const select = document.getElementById('user-select');
    const mobileSelect = document.getElementById('mobile-user-select');
    if (select && select.value !== userId) select.value = userId;
    if (mobileSelect && mobileSelect.value !== userId) mobileSelect.value = userId;
    updateActiveUserBanner();
}

function updateActiveUserBanner() {
    const user = usersData.find(u => u.id === activeUserId) || { name: 'Utente', role: 'adult', age_group: 'adult' };
    const av = getUserAvatarInfo(user);
    const nameEl = document.getElementById('banner-user-name');
    const roleEl = document.getElementById('banner-user-role');
    if (nameEl) nameEl.innerHTML = `${av.emoji} ${user.name}`;
    if (roleEl) roleEl.innerText = `${user.role} • ${av.label}`;
}

// ==================== SPEECH RECOGNITION (COMPATIBILE IOS SAFARI / PWA) ====================
let activeRecognition = null;
let isRecording = false;

function stopRecording() {
    isRecording = false;
    const btn = document.getElementById('mic-btn');
    if (btn) btn.classList.remove('bg-rose-600', 'text-white', 'mic-active');
    const st = document.getElementById('recording-status');
    if (st) st.classList.add('hidden');
    updateLivingCoreState('idle');
}

// ---- Il microfono, dalla issue #31 ----
//
// Prima di questa versione qui c'era solo la Web Speech API, che manda
// l'audio ai server del produttore del browser: Google su Chrome, Apple
// su Safari. Ogni parola detta all'assistente usciva di casa, mentre il
// README prometteva «Zero Cloud per i Dati Privati».
//
// Adesso l'audio si registra e si manda al server, che lo trascrive con
// Whisper e non lo inoltra a nessuno. La Web Speech API resta
// raggiungibile mettendo `voce.motore: browser` in configurazione: e'
// una scelta, e la dashboard dice cosa comporta.

let statoVoce = null;
let registratore = null;

async function leggiStatoVoce() {
    // Si tiene da parte solo una risposta definitiva. Finche' il
    // modello si sta caricando, «non ancora pronto» e' vero adesso e
    // falso fra un minuto: ricordarselo vorrebbe dire un microfono
    // che resta spento fino al prossimo ricaricamento della pagina.
    if (statoVoce && (!statoVoce.in_casa || statoVoce.modello_caricato)) return statoVoce;
    try {
        const res = await fetch('/api/voce/stato', { headers: getAuthHeaders() });
        if (res.ok) statoVoce = await res.json();
    } catch (e) { console.warn('stato voce:', e); }
    return statoVoce;
}

async function toggleSpeechRecognition() {
    const stato = await leggiStatoVoce();

    // `in_casa` falso vuol dire che la configurazione ha scelto il
    // browser: si usa la vecchia strada, sapendo cosa comporta.
    if (stato && stato.in_casa) return toggleTrascrizioneLocale(stato);

    return toggleWebSpeech();
}

async function toggleTrascrizioneLocale(stato) {
    if (isRecording && registratore) {
        try { registratore.stop(); } catch (e) {}
        return;
    }
    if (!stato.pronto) {
        // Meglio dirlo prima di registrare: chi preme e poi scopre che
        // non serviva a niente ha gia' parlato.
        alert(stato.spiegazione || 'Il riconoscimento vocale non e\' disponibile.');
        return;
    }
    if (!stato.modello_caricato) {
        // Stessa ragione del controllo qui sopra, un passo piu' in
        // la': il motore c'e', ma i pesi non sono ancora in memoria.
        // Registrare adesso vuol dire parlare dentro un'attesa che
        // finira' tagliata da qualunque proxy stia davanti al server.
        //
        // Il messaggio arriva dal server e non e' scritto qui, perche'
        // «sto preparando» e «ci ho provato e non ci sono riuscito»
        // sono due cose diverse e solo il server sa quale delle due.
        alert(stato.spiegazione_modello || 'Sto ancora preparando il modello di riconoscimento. Riprova fra un minuto.');
        return;
    }
    if (!navigator.mediaDevices || !window.MediaRecorder) {
        alert("Questo browser non sa registrare audio. Puoi digitare il tuo messaggio.");
        return;
    }

    let flusso;
    try {
        flusso = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
        alert("Accesso al microfono non consentito. Controlla i permessi del browser.");
        return;
    }

    const pezzi = [];
    registratore = new MediaRecorder(flusso);

    registratore.ondataavailable = e => { if (e.data && e.data.size) pezzi.push(e.data); };

    registratore.onstart = () => {
        isRecording = true;
        const btn = document.getElementById('mic-btn');
        if (btn) btn.classList.add('bg-rose-600', 'text-white', 'mic-active');
        const st = document.getElementById('recording-status');
        if (st) {
            st.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span> 🎙️ In ascolto... parla pure!';
            st.classList.remove('hidden');
        }
        updateLivingCoreState('listening');
    };

    registratore.onstop = async () => {
        // Il microfono si spegne davvero: senza questo, la spia di
        // registrazione del browser resta accesa dopo che si e' finito
        // di parlare, e non c'e' modo peggiore di far credere a
        // qualcuno che lo stai ascoltando sempre.
        flusso.getTracks().forEach(t => t.stop());
        stopRecording();

        const registrazione = new Blob(pezzi, { type: registratore.mimeType || 'audio/webm' });
        if (!registrazione.size) return;

        const st = document.getElementById('recording-status');
        if (st) {
            st.innerHTML = '<span class="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span> Trascrivo...';
            st.classList.remove('hidden');
        }

        try {
            const modulo = new FormData();
            modulo.append('audio', registrazione, 'comando.webm');
            modulo.append('tipo', registratore.mimeType || 'audio/webm');

            const res = await fetch('/api/voce/trascrivi', {
                method: 'POST', headers: intestazioniPerModulo(), body: modulo
            });
            if (!res.ok) { alert(await _dettaglioErrore(res)); return; }

            const esito = await res.json();
            if (esito.vuota) {
                if (st) st.innerHTML = 'Non ho sentito niente.';
                setTimeout(() => { if (st) st.classList.add('hidden'); }, 2000);
                return;
            }

            const input = document.getElementById('user-input');
            if (input) { input.value = esito.testo; handleSend(); }
        } catch (e) {
            alert('Non sono riuscito a trascrivere: ' + ((e && e.message) || e));
        } finally {
            if (st) st.classList.add('hidden');
        }
    };

    registratore.start();
}

async function toggleWebSpeech() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert("Il riconoscimento vocale non è supportato in questa versione del browser. Puoi digitare il tuo messaggio.");
        return;
    }

    if (isRecording && activeRecognition) {
        try { activeRecognition.stop(); } catch(e) {}
        stopRecording();
        return;
    }

    // Su iOS Safari PWA: sblocca la sessione microfono se necessario
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(t => t.stop());
        } catch (micErr) {
            console.warn('Permesso microfono non concesso da iOS:', micErr);
            alert("Accesso al microfono non consentito da iOS. Vai in Impostazioni iPhone ➔ Safari ➔ Microfono e seleziona 'Consenti'.");
            return;
        }
    }

    try {
        activeRecognition = new SpeechRec();
        activeRecognition.lang = 'it-IT';
        activeRecognition.continuous = false;
        activeRecognition.interimResults = true;
        activeRecognition.maxAlternatives = 1;

        let finalTranscript = '';

        activeRecognition.onstart = () => {
            isRecording = true;
            const btn = document.getElementById('mic-btn');
            if (btn) btn.classList.add('bg-rose-600', 'text-white', 'mic-active');
            const st = document.getElementById('recording-status');
            if (st) {
                st.innerHTML = '<span class="w-2 h-2 rounded-full bg-rose-500 animate-ping"></span> 🎙️ In ascolto... parla pure!';
                st.classList.remove('hidden');
            }
            updateLivingCoreState('listening');
        };

        activeRecognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += piece;
                } else {
                    interim += piece;
                }
            }
            const display = (finalTranscript || interim).trim();
            const input = document.getElementById('user-input');
            if (input && display) {
                input.value = display;
            }
        };

        activeRecognition.onerror = (event) => {
            console.warn('SpeechRecognition error:', event.error);
            stopRecording();
            if (event.error === 'not-allowed') {
                alert("Permesso microfono non autorizzato su iOS. Controlla le impostazioni di Safari.");
            }
        };

        activeRecognition.onend = () => {
            stopRecording();
            const input = document.getElementById('user-input');
            if (input && input.value.trim().length > 0) {
                handleSend();
            }
        };

        activeRecognition.start();
    } catch (err) {
        console.error('Errore avvio SpeechRecognition:', err);
        stopRecording();
    }
}

// ==================== MOTORE VOCALE UMANIZZATO HD ====================
let neuralVoice = localStorage.getItem('shinra_neural_voice') || 'it-IT-DiegoNeural';
let voiceMuted = localStorage.getItem('shinra_voice_muted') === 'true';
let voiceRate = parseFloat(localStorage.getItem('shinra_voice_rate')) || 1.0;
let voicePitch = parseFloat(localStorage.getItem('shinra_voice_pitch')) || 1.0;
let selectedVoiceURI = localStorage.getItem('shinra_voice_uri') || 'auto';
let availableVoices = [];
let currentAudioPlayer = null;

function initVoiceEngine() {
    syncVoiceUI();
    if ('speechSynthesis' in window) {
        function loadBrowserVoices() {
            availableVoices = window.speechSynthesis.getVoices();
            populateVoiceSelect();
        }
        loadBrowserVoices();
        if (window.speechSynthesis.onvoiceschanged !== undefined) {
            window.speechSynthesis.onvoiceschanged = loadBrowserVoices;
        }
    }
}

function populateVoiceSelect() {
    const select = document.getElementById('cfg-browser-voice');
    if (!select) return;

    const itVoices = availableVoices.filter(v => v.lang.startsWith('it') || v.lang.startsWith('IT'));
    select.innerHTML = '<option value="auto">✨ Selezione Automatica Migliore (Naturale)</option>';

    itVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.voiceURI;
        opt.textContent = `${v.name} (${v.lang})`;
        if (v.voiceURI === selectedVoiceURI) opt.selected = true;
        select.appendChild(opt);
    });
}

function syncVoiceUI() {
    // Settings tab
    const cfgNeural = document.getElementById('cfg-neural-voice');
    if (cfgNeural) cfgNeural.value = neuralVoice;

    const cfgMuted = document.getElementById('cfg-voice-muted');
    if (cfgMuted) cfgMuted.checked = voiceMuted;

    const cfgRate = document.getElementById('cfg-voice-rate');
    if (cfgRate) {
        cfgRate.value = voiceRate;
        const rVal = document.getElementById('rate-val');
        if (rVal) rVal.textContent = voiceRate + 'x';
    }

    const cfgPitch = document.getElementById('cfg-voice-pitch');
    if (cfgPitch) {
        cfgPitch.value = voicePitch;
        const pVal = document.getElementById('pitch-val');
        if (pVal) pVal.textContent = voicePitch;
    }
}

function setNeuralVoice(voiceId) {
    neuralVoice = voiceId;
    localStorage.setItem('shinra_neural_voice', voiceId);
    syncVoiceUI();
}

function toggleVoiceMute() {
    voiceMuted = !voiceMuted;
    localStorage.setItem('shinra_voice_muted', voiceMuted);
    if (voiceMuted) {
        if (currentAudioPlayer) {
            currentAudioPlayer.pause();
            currentAudioPlayer = null;
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    }
    syncVoiceUI();
}

function setSpecificVoice(uri) {
    selectedVoiceURI = uri;
    localStorage.setItem('shinra_voice_uri', uri);
}

function setVoiceRate(r) {
    voiceRate = parseFloat(r);
    localStorage.setItem('shinra_voice_rate', r);
    const rVal = document.getElementById('rate-val');
    if (rVal) rVal.textContent = r + 'x';
}

function setVoicePitch(p) {
    voicePitch = parseFloat(p);
    localStorage.setItem('shinra_voice_pitch', p);
    const pVal = document.getElementById('pitch-val');
    if (pVal) pVal.textContent = p;
}

function cleanTextForSpeech(text) {
    if (!text) return "";
    let clean = text
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`.*?`/g, '')
        .replace(/https?:\/\/\S+/g, '')
        .replace(/[*_~#>[\]]/g, '')
        .replace(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')
        .replace(/\bHA\b/g, 'Home Assistant')
        .replace(/\bdegli alias\b/gi, 'degli alias')
        .replace(/\b°C\b/g, 'gradi')
        .replace(/\s+/g, ' ')
        .trim();
    return clean;
}

async function speakText(text) {
    if (voiceMuted) return;

    const clean = cleanTextForSpeech(text);
    if (!clean) return;

    updateLivingCoreState('speaking');

    // Se la voce selezionata è una voce neurale HD del server
    if (neuralVoice !== 'browser') {
        try {
            if (currentAudioPlayer) {
                currentAudioPlayer.pause();
                currentAudioPlayer = null;
            }
            const res = await fetch('/api/tts', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    text: clean,
                    voice: neuralVoice
                })
            });
            if (res.ok) {
                const blob = await res.blob();
                const audioUrl = URL.createObjectURL(blob);
                currentAudioPlayer = new Audio(audioUrl);
                currentAudioPlayer.onended = () => updateLivingCoreState('idle');
                currentAudioPlayer.onerror = () => updateLivingCoreState('idle');
                currentAudioPlayer.play().catch(e => {
                    console.warn('Audio playback block/error:', e);
                    updateLivingCoreState('idle');
                });
                return;
            }
        } catch (e) {
            console.warn('Fallback a sintesi browser per errore server TTS:', e);
        }
    }

    // Fallback locale Web Speech API
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.lang = 'it-IT';
        if (selectedVoiceURI && selectedVoiceURI !== 'auto') {
            const specific = availableVoices.find(v => v.voiceURI === selectedVoiceURI || v.name === selectedVoiceURI);
            if (specific) utterance.voice = specific;
        }
        utterance.pitch = voicePitch;
        utterance.rate = voiceRate;
        utterance.onend = () => updateLivingCoreState('idle');
        utterance.onerror = () => updateLivingCoreState('idle');
        window.speechSynthesis.speak(utterance);
    } else {
        updateLivingCoreState('idle');
    }
}

async function testVoicePreview() {
    const previewText = neuralVoice.includes('Diego') || neuralVoice.includes('Giuseppe')
        ? "Sistemi operativi. Voce neurale ad alta definizione calibrata e pronta."
        : "Ciao, sono Shinra. La mia voce neurale ad alta definizione è pronta.";

    const wasMuted = voiceMuted;
    voiceMuted = false;
    await speakText(previewText);
    voiceMuted = wasMuted;
}


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
                ${actions.map(a => `<span class="px-2 py-0.5 rounded bg-indigo-950/70 border border-indigo-700/50 text-indigo-300 text-xs font-mono">⚡ ${a.tool}</span>`).join('')}
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
        quando: new Date().toLocaleTimeString()
    });
    // La memoria di una pagina aperta da giorni non cresce all'infinito.
    if (_toolInvocati.length > 50) _toolInvocati.length = 50;

    const conta = document.getElementById('conta-tool');
    if (conta) {
        conta.innerText = _toolInvocati.length === 1
            ? '1 azione'
            : _toolInvocati.length + ' azioni';
    }
    // Se la finestra e' aperta adesso, si aggiorna sotto gli occhi.
    if (document.getElementById('tool-logs')) _disegnaToolInvocati();
}

function _disegnaToolInvocati() {
    const contenitore = document.getElementById('tool-logs');
    if (!contenitore) return;
    if (!_toolInvocati.length) {
        contenitore.innerHTML = '<div class="text-slate-600">Shinra non ha ancora toccato niente. Qui finiscono gli strumenti che usa quando gli parli: accendere una luce, leggere il meteo, avviare un timer.</div>';
        return;
    }
    contenitore.innerHTML = _toolInvocati.map(voce => `
        <div class="p-2 rounded bg-slate-900 border border-slate-800">
            <div class="text-indigo-400 font-bold flex items-center justify-between">
                <span>▶ Tool: ${_testoSicuro(voce.tool)}</span>
                <span class="text-[10px] text-slate-500">${voce.quando}</span>
            </div>
            <div class="text-slate-400 mt-0.5">Argomenti: <span class="text-slate-300">${_testoSicuro(JSON.stringify(voce.argomenti))}</span></div>
            <div class="text-emerald-400 mt-0.5 truncate">Risultato: ${_testoSicuro(JSON.stringify(voce.risultato))}</div>
        </div>
    `).join('');
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
                satellite: satelliteDiQuestoDispositivo()
            })
        });
        hideTypingIndicator();
        if (!res.ok) {
            const errData = await res.json().catch(() => ({ detail: res.statusText }));
            appendAssistantMessage(`Errore dal server (${res.status}): ${errData.detail || 'Impossibile elaborare il messaggio'}`);
            updateLivingCoreState('idle');
            return;
        }
        const data = await res.json();
        appendAssistantMessage(data.response, data.actions);
        if (data.actions) data.actions.forEach(a => logAction(a.tool, a.args, a.result));
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
    } catch (e) {
        // Navigazione privata, o memoria del sito bloccata: si resta
        // un dispositivo senza stanza, che è come funzionava prima.
        return null;
    }
}

function stanzaDiQuestoDispositivo() {
    try {
        return localStorage.getItem(CHIAVE_STANZA) || '';
    } catch (e) {
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
                stanza: stanzaDiQuestoDispositivo()
            })
        });
    } catch (e) {
        // Non poter dire dove si è non impedisce di parlare.
    }
    mostraStanzaScelta();
}

async function scegliStanza(stanza) {
    try {
        localStorage.setItem(CHIAVE_STANZA, stanza || '');
    } catch (e) {
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
        const stanze = [...new Set((alias || []).map(a => (a.room || '').trim()).filter(Boolean))];
        elenco.innerHTML = stanze.sort().map(s => `<option value="${s}"></option>`).join('');
    } catch (e) {
        // Senza suggerimenti la stanza si scrive a mano, e va bene.
    }
}

// ==================== KNOWLEDGE TEMPLATES ====================
const KNOWLEDGE_TEMPLATES = [
    {
        id: 'casa', icon: '🏠', label: 'Casa & Indirizzo',
        fields: [
            { key: 'indirizzo',   label: 'Indirizzo completo',     placeholder: 'es. Via Roma 10, Arezzo, 52100' },
            { key: 'piano',       label: 'Piano / Interno',         placeholder: 'es. Piano 2, interno 4' },
            { key: 'citofono',    label: 'Citofono / Campanello',   placeholder: 'es. Rossi' },
            { key: 'wifi_nome',   label: 'Nome rete WiFi',          placeholder: 'es. CasaMia_5G' },
        ]
    },
    {
        id: 'famiglia', icon: '👨‍👩‍👧', label: 'Famiglia & Conviventi',
        fields: [
            { key: 'componenti',  label: 'Componenti del nucleo',   placeholder: 'es. Alessio (admin), Giulia (adulto), Marco (10 anni)' },
            { key: 'animali',     label: 'Animali domestici',        placeholder: 'es. Rex, cane labrador 3 anni' },
            { key: 'compleanni',  label: 'Compleanni importanti',    placeholder: 'es. Giulia il 15 marzo, Marco il 8 luglio' },
        ]
    },
    {
        id: 'abitudini', icon: '📅', label: 'Abitudini & Routine',
        fields: [
            { key: 'sveglia',     label: 'Orario sveglia solito',   placeholder: 'es. 7:00 nei giorni feriali, 9:00 weekend' },
            { key: 'lavoro',      label: 'Orari lavoro / scuola',   placeholder: 'es. Alessio lavora 9-18, Marco scuola 8-16' },
            { key: 'rientro',     label: 'Orario rientro a casa',   placeholder: 'es. solitamente verso le 19:00' },
            { key: 'hobby',       label: 'Hobby & passioni',         placeholder: 'es. calcio, lettura, videogiochi' },
            { key: 'cibo',        label: 'Cucina / piatti preferiti',placeholder: 'es. pasta al pomodoro, pizza margherita' },
        ]
    },
    {
        id: 'salute', icon: '🏥', label: 'Salute & Emergenze',
        fields: [
            { key: 'medico',      label: 'Medico di base',          placeholder: 'es. Dr. Rossi, tel. 0123-456789' },
            { key: 'pronto_soc', label: 'Pronto soccorso vicino',   placeholder: 'es. Ospedale San Donato, Via X' },
            { key: 'farmacia',    label: 'Farmacia di fiducia',      placeholder: 'es. Farmacia Centrale, aperta 24h' },
            { key: 'allergie',    label: 'Allergie / intolleranze',  placeholder: 'es. Giulia allergica alle arachidi' },
            { key: 'gruppo_sg',   label: 'Gruppo sanguigno',         placeholder: 'es. Alessio A+, Giulia 0-' },
        ]
    },
    {
        id: 'casa_tecnica', icon: '🔧', label: 'Contatti & Tecnici',
        fields: [
            { key: 'idraulico',   label: 'Idraulico di fiducia',    placeholder: 'es. Mario Verdi, tel. 333-1234567' },
            { key: 'elettricista',label: 'Elettricista',             placeholder: 'es. Luigi Bianchi, tel. 347-7654321' },
            { key: 'portiere',    label: 'Portiere / Amministratore',placeholder: 'es. Sig. Ferrari, tel. 0575-123456' },
            { key: 'assicurazione',label: 'Assicurazione casa',     placeholder: 'es. Unipol polizza n. 12345, tel. 800-xxx' },
        ]
    },
    {
        id: 'veicoli', icon: '🚗', label: 'Veicoli & Spostamenti',
        fields: [
            { key: 'auto1',       label: 'Auto principale',          placeholder: 'es. Fiat Panda, targa EF123GH, colore bianco' },
            { key: 'auto2',       label: 'Secondo veicolo',          placeholder: 'es. Vespa 125, targa AA000AA' },
            { key: 'parcheggio',  label: 'Box / Parcheggio',         placeholder: 'es. Box n. 12 in Via Roma' },
        ]
    },
    {
        id: 'digitale', icon: '📱', label: 'Preferenze Digitali',
        fields: [
            { key: 'streaming',   label: 'Servizi streaming',        placeholder: 'es. Netflix, Disney+, Spotify' },
            { key: 'musica',      label: 'Generi musicali preferiti',placeholder: 'es. rock anni 80, jazz, musica italiana' },
            { key: 'smart_tv',    label: 'TV principale',            placeholder: 'es. Samsung 55" in salotto, entity: media_player.tv_salotto' },
            { key: 'voce_alexa',  label: 'Echo Alexa principale',    placeholder: 'es. Echo Show in cucina, Echo Dot in camera' },
        ]
    },
    {
        id: 'note_libere', icon: '📝', label: 'Note & Preferenze Varie',
        fields: [
            { key: 'lingua',      label: 'Lingua preferita risposta',placeholder: 'es. sempre in italiano, tono informale' },
            { key: 'privacy',     label: 'Note sulla privacy',        placeholder: 'es. non leggere messaggi ad alta voce se ci sono ospiti' },
            { key: 'note',        label: 'Altre note importanti',     placeholder: 'es. il campanello è rotto dal 2024, intercome non funziona' },
        ]
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
            container.innerHTML = `<p class="text-xs text-slate-500 col-span-2 py-3 text-center">Nessun fatto memorizzato. Compila una categoria qui sopra o aggiungi un fatto libero.</p>`;
        } else {
            const catColors = { casa:'indigo', famiglia:'violet', abitudini:'sky', salute:'rose', casa_tecnica:'amber', veicoli:'green', digitale:'purple', note_libere:'slate', generale:'slate' };
            container.innerHTML = items.map(k => {
                const cat = k.category || 'generale';
                const col = catColors[cat] || 'slate';
                return `
                <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 flex justify-between items-start gap-3 group hover:border-slate-700 transition">
                    <div class="flex-1 min-w-0">
                        <span class="px-2 py-0.5 rounded bg-${col}-950/60 border border-${col}-800 text-[10px] text-${col}-300 font-mono uppercase">${cat}</span>
                        <p class="text-xs text-slate-200 mt-1.5 leading-relaxed">${k.text}</p>
                    </div>
                    <button onclick="deleteKnowledge('${k.id}')" class="text-slate-600 hover:text-rose-400 transition p-1 opacity-0 group-hover:opacity-100 shrink-0" title="Elimina fatto">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>
                </div>`;
            }).join('');
        }
        safeCreateIcons();
        renderKnowledgeTemplates(items);
    } catch(e) { console.error('loadKnowledge:', e); }
}

function renderKnowledgeTemplates(existingItems) {
    const container = document.getElementById('knowledge-templates-section');
    if (!container) return;

    // Mappa delle chiavi compilate
    const savedMap = {};
    existingItems.forEach(k => {
        if (k._key) savedMap[k._key] = k.text.replace(/^[^:]+:\s*/, '');
    });

    container.innerHTML = KNOWLEDGE_TEMPLATES.map(section => {
        const filledCount = section.fields.filter(f => savedMap[`${section.id}.${f.key}`]).length;
        const totalCount = section.fields.length;
        const isComplete = filledCount === totalCount;

        let badgeHtml = '';
        if (filledCount === 0) {
            badgeHtml = `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-400 border border-slate-700">Da compilare</span>`;
        } else if (isComplete) {
            badgeHtml = `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-800 flex items-center gap-1">✓ ${filledCount}/${totalCount}</span>`;
        } else {
            badgeHtml = `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-950/60 text-indigo-300 border border-indigo-800">${filledCount}/${totalCount} compilati</span>`;
        }

        // Genera chip di anteprima dei valori inseriti
        const filledChips = section.fields
            .filter(f => savedMap[`${section.id}.${f.key}`])
            .map(f => `<span class="px-2 py-0.5 rounded-md bg-slate-950 border border-slate-800 text-[10px] text-slate-300 truncate max-w-[140px]" title="${f.label}: ${savedMap[`${section.id}.${f.key}`]}">${f.label}: ${savedMap[`${section.id}.${f.key}`]}</span>`)
            .slice(0, 3)
            .join('');

        return `
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
                    ${badgeHtml}
                </div>
                <div class="flex flex-wrap gap-1 min-h-[22px] pt-1">
                    ${filledChips || '<span class="text-[10px] text-slate-600 italic">Nessun dato inserito.</span>'}
                    ${filledCount > 3 ? `<span class="text-[10px] text-slate-500 font-semibold self-center">+${filledCount - 3} altri</span>` : ''}
                </div>
            </div>
            <div class="pt-2 border-t border-slate-800/80 flex justify-end">
                <button onclick="openKnowledgeCategoryModal('${section.id}')" class="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 border border-indigo-600/40 text-indigo-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition">
                    <i data-lucide="edit-3" class="w-3.5 h-3.5"></i> ${filledCount > 0 ? 'Modifica Dati' : 'Compila Categoria'}
                </button>
            </div>
        </div>
        `;
    }).join('');
    safeCreateIcons();
}

function openKnowledgeCategoryModal(sectionId) {
    const section = KNOWLEDGE_TEMPLATES.find(s => s.id === sectionId);
    if (!section) return;

    const existingMap = {};
    _allKnowledgeItems.forEach(k => {
        if (k._key && k._key.startsWith(sectionId + '.')) {
            const fieldKey = k._key.split('.')[1];
            existingMap[fieldKey] = k.text.replace(/^[^:]+:\s*/, '');
        }
    });

    showModal(`
        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                <span class="text-xl">${section.icon}</span> ${section.label}
            </h3>
            <button onclick="closeModal()" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>
        <p class="text-xs text-slate-400 mt-2">Compila o modifica i dettagli per Shinra. Lascia vuoti i campi che non vuoi memorizzare.</p>
        <div class="space-y-3 mt-4 max-h-[60vh] overflow-y-auto pr-1">
            ${section.fields.map(f => {
                const val = existingMap[f.key] || '';
                return `
                <div>
                    <label class="text-[11px] font-semibold text-slate-300 block mb-1">${f.label}</label>
                    <input type="text" id="modal-kt-${section.id}-${f.key}"
                        value="${val.replace(/"/g, '&quot;')}"
                        placeholder="${f.placeholder}"
                        class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
                </div>
                `;
            }).join('')}
        </div>
        <div class="flex justify-end gap-2 pt-4 border-t border-slate-800 mt-4">
            <button onclick="closeModal()" class="px-3.5 py-2 rounded-xl bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 transition">Annulla</button>
            <button onclick="saveKnowledgeCategory('${section.id}')" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5 transition shadow-md shadow-indigo-600/30">
                <i data-lucide="check" class="w-3.5 h-3.5"></i> Salva Informazioni
            </button>
        </div>
    `, false);
}

async function saveKnowledgeCategory(sectionId) {
    const section = KNOWLEDGE_TEMPLATES.find(s => s.id === sectionId);
    if (!section) return;

    for (const f of section.fields) {
        const inp = document.getElementById(`modal-kt-${section.id}-${f.key}`);
        const val = inp ? inp.value.trim() : '';
        if (val) {
            const text = `${f.label}: ${val}`;
            await fetch('/api/knowledge', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ text, category: section.id, enabled: true, _key: `${section.id}.${f.key}` })
            });
        }
    }
    closeModal();
    await loadKnowledge();
}

function openAddKnowledgeModal() {
    showModal(`
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

// ==================== SHINRA ISTRUISCI / LEARNING INTERVIEW ENGINE ====================
let currentLearningSession = null;
let learningRecognition = null;
let isLearningListening = false;
let currentProposedRoutine = null;
let lastLearningQuestion = "";

async function startLearningModal() {
    const modal = document.getElementById('learning-interview-modal');
    if (!modal) return;
    modal.style.display = 'flex';

    // Reset UI
    document.getElementById('learning-facts-container').classList.add('hidden');
    document.getElementById('learning-facts-list').innerHTML = '';
    document.getElementById('learning-routine-box').classList.add('hidden');
    document.getElementById('learning-answer-input').value = '';
    document.getElementById('learning-question-text').innerText = 'Inizializzazione intervista in corso...';
    document.getElementById('learning-topic-title').innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i> Avvio...`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/start', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ user_id: activeUserId || 'alessio' })
        });
        if (!res.ok) throw new Error('Errore avvio sessione');
        const data = await res.json();
        currentLearningSession = data;
        renderLearningStep(data);
    } catch (err) {
        console.error('startLearningModal:', err);
        document.getElementById('learning-question-text').innerText = 'Impossibile avviare la sessione di apprendimento. Verifica la connessione.';
    }
}

function renderLearningStep(data) {
    currentLearningSession = data;
    const modal = document.getElementById('learning-interview-modal');
    if (!modal) return;

    const stepBadge = document.getElementById('learning-step-badge');
    const progBar = document.getElementById('learning-progress-bar');
    const topicTitle = document.getElementById('learning-topic-title');
    const qText = document.getElementById('learning-question-text');
    const hintText = document.getElementById('learning-hint-text');
    const answerInput = document.getElementById('learning-answer-input');
    const routineBox = document.getElementById('learning-routine-box');
    const factsContainer = document.getElementById('learning-facts-container');
    const factsList = document.getElementById('learning-facts-list');
    const submitBtn = document.getElementById('learning-submit-btn');

    if (data.is_complete) {
        stepBadge.innerText = 'Completata! 🎉';
        progBar.style.width = '100%';
        topicTitle.innerHTML = `<i data-lucide="check-circle" class="w-3.5 h-3.5 text-emerald-400"></i> Apprendimento Concluso`;
        qText.innerText = data.message;
        hintText.innerText = 'Tutti i fatti e le preferenze sono stati registrati nella tua Conoscenza Casa.';
        answerInput.parentElement.classList.add('hidden');
        submitBtn.parentElement.innerHTML = `
            <button type="button" onclick="closeLearningModal()" class="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-indigo-600 hover:from-emerald-400 text-white rounded-xl text-xs font-bold transition shadow-lg">
                Chiudi e Visualizza Conoscenza
            </button>
        `;
        speakText(data.message);
        safeCreateIcons();
        loadKnowledge();
        return;
    }

    const step = data.step;
    const currentIdx = (data.step_index || 0) + 1;
    const total = data.total_steps || 6;
    const pct = Math.round((currentIdx / total) * 100);

    stepBadge.innerText = `Fase ${currentIdx} di ${total}`;
    progBar.style.width = `${pct}%`;
    topicTitle.innerHTML = `<i data-lucide="help-circle" class="w-3.5 h-3.5"></i> ${step.title || 'Domanda'}`;
    qText.innerText = step.question || data.message;
    lastLearningQuestion = step.question || data.message;
    hintText.innerText = step.hint ? `💡 ${step.hint}` : '';

    // Routine Proposal
    if (data.proposed_routine && data.proposed_routine.name) {
        currentProposedRoutine = data.proposed_routine;
        document.getElementById('learning-routine-desc').innerText = `Ho notato una possibile routine "${data.proposed_routine.name}": ${data.proposed_routine.description || 'Automazione personalizzata'}.`;
        routineBox.classList.remove('hidden');
    } else {
        routineBox.classList.add('hidden');
        currentProposedRoutine = null;
    }

    // Facts list
    if (data.new_facts && data.new_facts.length > 0) {
        factsContainer.classList.remove('hidden');
        data.new_facts.forEach(f => {
            const badge = document.createElement('span');
            badge.className = 'px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-700/60 text-emerald-300 text-[11px]';
            badge.innerText = `✓ ${f.text}`;
            factsList.appendChild(badge);
        });
    }

    answerInput.value = '';
    answerInput.parentElement.classList.remove('hidden');
    answerInput.focus();

    // Speak question
    speakText(step.question || data.message);
    safeCreateIcons();
}

function playAudioOrSpeak(text) {
    if (text && typeof speakText === 'function') {
        speakText(text);
    }
}

function replayLearningQuestionAudio() {
    if (lastLearningQuestion) {
        speakText(lastLearningQuestion);
    }
}

async function submitLearningAnswer() {
    const input = document.getElementById('learning-answer-input');
    const text = input ? input.value.trim() : '';
    if (!text) {
        alert('Inserisci o detta una risposta prima di proseguire.');
        return;
    }

    const submitBtn = document.getElementById('learning-submit-btn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> <span>Salvataggio...</span>`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/answer', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                user_id: activeUserId || 'alessio',
                answer: text
            })
        });
        if (!res.ok) throw new Error('Errore durante il salvataggio');
        const data = await res.json();
        renderLearningStep(data);
        loadKnowledge();
    } catch (err) {
        console.error('submitLearningAnswer:', err);
        alert('Errore durante l\'elaborazione della risposta: ' + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
        safeCreateIcons();
    }
}

async function acceptProposedRoutine() {
    if (!currentProposedRoutine) return;
    const btn = document.getElementById('learning-routine-confirm-btn');
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i> Creazione in corso...`;
    safeCreateIcons();

    try {
        const res = await fetch('/api/learning/confirm-routine', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ routine: currentProposedRoutine })
        });
        const data = await res.json();
        if (data.success) {
            btn.className = 'px-3 py-1.5 bg-slate-800 text-emerald-400 rounded-xl text-xs font-bold transition flex items-center gap-1.5 border border-emerald-500/40';
            btn.innerHTML = `<i data-lucide="check-check" class="w-3.5 h-3.5"></i> Routine Creata con Successo!`;
            safeCreateIcons();
            if (typeof loadModes === 'function') loadModes();
        } else {
            alert('Errore creazione routine: ' + (data.error || 'Errore sconosciuto'));
            btn.disabled = false;
        }
    } catch (err) {
        console.error('acceptProposedRoutine:', err);
        btn.disabled = false;
    }
}

async function toggleLearningMic() {
    const micBtn = document.getElementById('learning-mic-btn');
    const statusLabel = document.getElementById('learning-mic-status');
    const input = document.getElementById('learning-answer-input');

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
        alert('Riconoscimento vocale non supportato dal browser. Puoi digitare la risposta nella casella di testo.');
        return;
    }

    if (isLearningListening && learningRecognition) {
        try { learningRecognition.stop(); } catch(e) {}
        isLearningListening = false;
        if (statusLabel) statusLabel.classList.add('hidden');
        if (micBtn) {
            micBtn.classList.remove('bg-rose-600', 'text-white');
            micBtn.classList.add('bg-slate-800', 'text-slate-300');
        }
        return;
    }

    // Su iOS Safari: sblocca la sessione microfono se necessario
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(t => t.stop());
        } catch (micErr) {
            console.warn('Permesso microfono non concesso da iOS:', micErr);
            alert("Accesso al microfono non consentito da iOS. Vai in Impostazioni iPhone ➔ Safari ➔ Microfono e seleziona 'Consenti'.");
            return;
        }
    }

    try {
        learningRecognition = new SpeechRec();
        learningRecognition.lang = 'it-IT';
        learningRecognition.continuous = false;
        learningRecognition.interimResults = true;

        let finalTranscript = '';
        const initialText = input ? input.value.trim() : '';

        learningRecognition.onstart = () => {
            isLearningListening = true;
            if (statusLabel) {
                statusLabel.innerText = '🎙️ In ascolto... parla pure!';
                statusLabel.classList.remove('hidden');
            }
            if (micBtn) {
                micBtn.classList.add('bg-rose-600', 'text-white');
                micBtn.classList.remove('bg-slate-800', 'text-slate-300');
            }
        };

        learningRecognition.onresult = (event) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const piece = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += piece;
                } else {
                    interim += piece;
                }
            }
            const spoken = (finalTranscript || interim).trim();
            if (input && spoken) {
                input.value = initialText ? `${initialText} ${spoken}` : spoken;
            }
        };

        learningRecognition.onerror = (event) => {
            console.warn('Learning speech error:', event.error);
            isLearningListening = false;
            if (statusLabel) statusLabel.classList.add('hidden');
            if (micBtn) {
                micBtn.classList.remove('bg-rose-600', 'text-white');
                micBtn.classList.add('bg-slate-800', 'text-slate-300');
            }
            if (event.error === 'not-allowed') {
                alert("Permesso microfono non autorizzato su iOS. Controlla le impostazioni di Safari.");
            }
        };

        learningRecognition.onend = () => {
            isLearningListening = false;
            if (statusLabel) statusLabel.classList.add('hidden');
            if (micBtn) {
                micBtn.classList.remove('bg-rose-600', 'text-white');
                micBtn.classList.add('bg-slate-800', 'text-slate-300');
            }
        };

        learningRecognition.start();
    } catch (err) {
        console.error('Errore avvio learningRecognition:', err);
        isLearningListening = false;
        if (statusLabel) statusLabel.classList.add('hidden');
        if (micBtn) {
            micBtn.classList.remove('bg-rose-600', 'text-white');
            micBtn.classList.add('bg-slate-800', 'text-slate-300');
        }
    }
}

async function closeLearningModal() {
    if (isLearningListening && learningRecognition) {
        learningRecognition.stop();
    }
    const modal = document.getElementById('learning-interview-modal');
    if (modal) modal.style.display = 'none';

    try {
        await fetch('/api/learning/stop', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ user_id: activeUserId || 'alessio' })
        });
    } catch (e) {}

    await loadKnowledge();
}


async function saveNewKnowledge() {
    const text = document.getElementById('new-k-text').value.trim();
    const category = document.getElementById('new-k-cat').value || 'generale';
    if (!text) return;
    await fetch('/api/knowledge', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ text, category, enabled: true })
    });
    closeModal();
    loadKnowledge();
}

async function deleteKnowledge(id) {
    if (!confirm('Rimuovere questo fatto?')) return;
    await fetch(`/api/knowledge/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
    loadKnowledge();
}

// ==================== SOURCES CATALOG & BULK CONTROLS ====================
const SOURCES_CATALOG = [
    { category: '📰 Notizie Italia', items: [
        { id: 'corriere', name: 'Corriere della Sera', cat: 'italia', url: 'https://www.corriere.it/rss/homepage.xml' },
        { id: 'repubblica', name: 'La Repubblica', cat: 'italia', url: 'https://www.repubblica.it/rss/homepage/rss2.0.xml' },
        { id: 'skytg24', name: 'Sky TG24', cat: 'italia', url: 'https://tg24.sky.it/feed/rss' },
        { id: 'lastampa', name: 'La Stampa', cat: 'italia', url: 'https://www.lastampa.it/rss.xml' },
        { id: 'ilmessaggero', name: 'Il Messaggero', cat: 'italia', url: 'https://www.ilmessaggero.it/rss/home.xml' },
    ]},
    { category: '💹 Economia & Finanza', items: [
        { id: 'sole24ore', name: 'Il Sole 24 Ore', cat: 'economia', url: 'https://www.ilsole24ore.com/rss/home.xml' },
        { id: 'milanofinanza', name: 'Milano Finanza', cat: 'economia', url: 'https://www.milanofinanza.it/rss' },
        { id: 'reuters_biz', name: 'Reuters Business', cat: 'economia', url: 'https://feeds.reuters.com/reuters/businessNews' },
    ]},
    { category: '🖥️ Tecnologia & AI', items: [
        { id: 'wired_it', name: 'Wired Italia', cat: 'tecnologia', url: 'https://www.wired.it/feed/rss' },
        { id: 'tomshw', name: "Tom's Hardware Italia", cat: 'tecnologia', url: 'https://www.tomshw.it/feed' },
        { id: 'hwupgrade', name: 'Hardware Upgrade', cat: 'tecnologia', url: 'https://www.hwupgrade.it/rss/news.xml' },
        { id: 'techcrunch', name: 'TechCrunch', cat: 'tecnologia', url: 'https://techcrunch.com/feed/' },
        { id: 'theverge', name: 'The Verge', cat: 'tecnologia', url: 'https://www.theverge.com/rss/index.xml' },
        { id: 'hn', name: 'Hacker News Top', cat: 'tecnologia', url: 'https://hnrss.org/frontpage' },
    ]},
    { category: '🌍 Notizie Internazionali', items: [
        { id: 'bbc_world', name: 'BBC World News', cat: 'mondo', url: 'http://feeds.bbci.co.uk/news/world/rss.xml' },
        { id: 'guardian', name: 'The Guardian', cat: 'mondo', url: 'https://www.theguardian.com/world/rss' },
        { id: 'reuters_top', name: 'Reuters Top News', cat: 'mondo', url: 'https://feeds.reuters.com/reuters/topNews' },
    ]},
    { category: '🔬 Scienza & Spazio', items: [
        { id: 'nasa', name: 'NASA Breaking News', cat: 'scienza', url: 'https://www.nasa.gov/rss/dyn/breaking_news.rss' },
        { id: 'lescienze', name: 'Le Scienze', cat: 'scienza', url: 'https://www.lescienze.it/rss/rss.xml' },
        { id: 'natgeo', name: 'National Geographic IT', cat: 'scienza', url: 'https://www.nationalgeographic.it/feed' },
        { id: 'sciencedaily', name: 'Science Daily', cat: 'scienza', url: 'https://www.sciencedaily.com/rss/top.xml' },
    ]},
    { category: '🏠 Smart Home & Domotica', items: [
        { id: 'smarthome_it', name: 'Domotica Plus', cat: 'domotica', url: 'https://www.domoticaplus.it/feed/' },
        { id: 'ha_blog', name: 'Home Assistant Blog', cat: 'domotica', url: 'https://www.home-assistant.io/atom.xml' },
    ]},
];

async function bulkToggleSources(enable) {
    try {
        const res = await fetch('/api/sources/bulk-toggle', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ enabled: enable })
        });
        if (res.ok) {
            await loadSources();
        }
    } catch (e) { console.error('bulkToggleSources error:', e); }
}

async function loadSources() {
    try {
        const res = await fetch('/api/sources', { headers: getAuthHeaders() });
        const items = await res.json();
        const container = document.getElementById('sources-list');

        if (!items.length) {
            container.innerHTML = `<p class="text-xs text-slate-500 col-span-2 py-3 text-center">Nessuna fonte attiva. Aggiungine dal catalogo qui sotto o clicca "Attiva Tutte".</p>`;
        } else {
            const activeCount = items.filter(s => s.enabled !== false).length;
            container.innerHTML = items.map(s => {
                const isEnabled = s.enabled !== false;
                return `
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
                        <button onclick="toggleSingleSource('${s.id}', ${!isEnabled})" class="text-slate-500 hover:text-indigo-400 p-1 transition" title="${isEnabled ? 'Disattiva' : 'Attiva'}">
                            <i data-lucide="${isEnabled ? 'toggle-right' : 'toggle-left'}" class="w-4 h-4 ${isEnabled ? 'text-indigo-400' : 'text-slate-600'}"></i>
                        </button>
                        <button onclick="deleteSource('${s.id}')" class="text-slate-600 hover:text-rose-400 p-1 opacity-0 group-hover:opacity-100 transition" title="Elimina fonte">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </div>`;
            }).join('');
        }
        safeCreateIcons();

        // Rende il catalogo con stato e fisarmonica
        const activeUrls = new Set(items.filter(s => s.enabled !== false).map(s => s.url));
        renderSourcesCatalog(activeUrls);
    } catch(e) { console.error('loadSources:', e); }
}

async function toggleSingleSource(sourceId, enable) {
    const res = await fetch('/api/sources', { headers: getAuthHeaders() });
    const items = await res.json();
    const source = items.find(s => s.id === sourceId);
    if (source) {
        source.enabled = enable;
        await fetch('/api/sources', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify(source)
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

    container.innerHTML = SOURCES_CATALOG.map((group, idx) => {
        const activeCount = group.items.filter(s => activeUrls.has(s.url)).length;
        const total = group.items.length;
        if (_sourcesAccordionState[idx] === undefined) _sourcesAccordionState[idx] = (idx === 0);
        const isOpen = Boolean(_sourcesAccordionState[idx]);

        return `
        <div class="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-sm">
            <button type="button" onclick="toggleSourceCategory(${idx})" class="w-full bg-slate-800/40 hover:bg-slate-800/70 px-4 py-3 text-xs font-semibold text-slate-200 flex items-center justify-between transition">
                <div class="flex items-center gap-2">
                    <span>${group.category}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] ${activeCount > 0 ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800' : 'bg-slate-800 text-slate-400'}">${activeCount}/${total} attive</span>
                </div>
                <i data-lucide="chevron-down" id="src-cat-chevron-${idx}" class="w-4 h-4 text-slate-400 transition-transform duration-200" style="transform: ${isOpen ? 'rotate(180deg)' : 'rotate(0deg)'}"></i>
            </button>
            <div id="src-cat-content-${idx}" class="${isOpen ? '' : 'hidden'} divide-y divide-slate-800/60">
                ${group.items.map(src => {
                    const added = activeUrls.has(src.url);
                    return `
                    <div class="flex items-center justify-between px-4 py-2.5 hover:bg-slate-800/20 transition">
                        <div class="flex-1 min-w-0">
                            <span class="text-xs font-medium text-slate-200">${src.name}</span>
                            <span class="text-[11px] text-slate-500 ml-2 font-mono hidden sm:inline">${src.url.replace('https://','').split('/')[0]}</span>
                        </div>
                        ${added
                            ? `<span class="text-[11px] text-emerald-400 font-semibold px-2.5 py-1 bg-emerald-950/40 border border-emerald-800 rounded-full flex items-center gap-1">✓ Attiva</span>`
                            : `<button onclick="addCatalogSource('${src.id}','${src.name.replace(/'/g,"\\'")}','${src.cat}','${src.url}')"
                                class="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-indigo-600/20 border border-indigo-600/40 text-indigo-300 hover:bg-indigo-600 hover:text-white transition">
                                + Aggiungi
                               </button>`
                        }
                    </div>`;
                }).join('')}
            </div>
        </div>`;
    }).join('');
    safeCreateIcons();
}

async function addCatalogSource(id, name, category, url) {
    await fetch('/api/sources', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ id, name, category, url, enabled: true })
    });
    loadSources();
}

function openAddSourceModal() {
    showModal(`
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
        body: JSON.stringify({ name, category, url, enabled: true })
    });
    closeModal();
    loadSources();
}

async function deleteSource(id) {
    if (!confirm('Rimuovere questa fonte?')) return;
    await fetch(`/api/sources/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadSources();
}

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

    for (const [domain, entities] of Object.entries(data.groups)) {
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

// ==================== CHIME AUDIO & TIMER ENGINE ====================
function playChimeAlert() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const now = ctx.currentTime;

        const osc1 = ctx.createOscillator();
        const gain1 = ctx.createGain();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(587.33, now); // D5
        gain1.gain.setValueAtTime(0.3, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc1.connect(gain1);
        gain1.connect(ctx.destination);
        osc1.start(now);
        osc1.stop(now + 0.4);

        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(880, now + 0.12); // A5
        gain2.gain.setValueAtTime(0.35, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.7);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.7);
    } catch (e) { console.warn('Audio Context non supportato:', e); }
}

let _activeTimers = [];
let _timerInterval = null;

async function loadTimers() {
    try {
        const res = await fetch('/api/timers', { headers: getAuthHeaders() });
        _activeTimers = await res.json();
        renderTimers();
    } catch (e) { console.error('Errore loadTimers:', e); }
}

function renderTimers() {
    const container = document.getElementById('active-timers-list');
    if (!container) return;
    if (!_activeTimers || _activeTimers.length === 0) {
        container.innerHTML = '<div class="text-[11px] text-slate-500 text-center py-2">Nessun timer attivo. Prova a dire "Timer pasta 9 minuti".</div>';
        return;
    }

    container.innerHTML = _activeTimers.map(t => {
        const rem = t.remaining_seconds || 0;
        const m = Math.floor(rem / 60);
        const s = rem % 60;
        const timeStr = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        const pct = t.duration_seconds > 0 ? Math.min(100, Math.max(0, ((t.duration_seconds - rem) / t.duration_seconds) * 100)) : 0;
        const isFinished = rem <= 0;

        return `
            <div class="p-2.5 rounded-xl bg-slate-950/80 border ${isFinished ? 'border-amber-500/80 bg-amber-950/30 animate-pulse' : 'border-slate-800'} flex items-center justify-between">
                <div class="flex items-center gap-2.5">
                    <div class="w-7 h-7 rounded-lg ${isFinished ? 'bg-amber-500 text-slate-950' : 'bg-amber-600/30 text-amber-300'} flex items-center justify-center font-bold text-xs">
                        ⏳
                    </div>
                    <div>
                        <h4 class="font-bold text-xs text-slate-200">${t.label || 'Timer'}</h4>
                        <div class="flex items-center gap-2 mt-0.5">
                            <span class="font-mono text-xs font-bold ${isFinished ? 'text-amber-400' : 'text-slate-300'}">${timeStr}</span>
                            <div class="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div class="h-full bg-amber-500 transition-all duration-1000" style="width: ${pct}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
                <button onclick="deleteTimer('${t.id}')" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Cancella timer">
                    <i data-lucide="x" class="w-4 h-4"></i>
                </button>
            </div>
        `;
    }).join('');
    safeCreateIcons();
}

async function deleteTimer(id) {
    await fetch(`/api/timers/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    _activeTimers = _activeTimers.filter(t => t.id !== id);
    renderTimers();
}

function openAddTimerModal() {
    showModal(`
        <h3 class="font-bold text-sm text-slate-100 mb-3 flex items-center gap-2">
            <i data-lucide="timer" class="w-4 h-4 text-amber-400"></i> Imposta Nuovo Timer
        </h3>
        <label class="text-slate-400 text-xs block mb-1">Nome o Etichetta (es. Pasta, Tè, Forno):</label>
        <input type="text" id="new-timer-label" value="Timer" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-3 focus:outline-none focus:border-amber-500">

        <label class="text-slate-400 text-xs block mb-1">Durata (Minuti):</label>
        <input type="number" id="new-timer-min" min="1" max="180" value="5" class="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100 mb-4 focus:outline-none focus:border-amber-500">

        <div class="flex justify-end gap-2">
            <button onclick="closeModal()" class="px-3 py-1.5 rounded-lg bg-slate-800 text-xs text-slate-300">Annulla</button>
            <button onclick="saveNewTimerManual()" class="px-4 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-xs text-white font-semibold">Avvia Timer</button>
        </div>
    `);
    setTimeout(() => document.getElementById('new-timer-label')?.focus(), 100);
}

async function saveNewTimerManual() {
    const label = document.getElementById('new-timer-label').value.trim() || 'Timer';
    const mins = parseInt(document.getElementById('new-timer-min').value) || 1;
    const secs = mins * 60;
    const res = await fetch('/api/timers', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ label, duration_seconds: secs, user_id: _currentUserId })
    });
    if (res.ok) {
        closeModal();
        loadTimers();
    }
}

// Il conto alla rovescia qui e' solo estetico: fa scorrere i secondi
// sullo schermo. Chi decide che un timer e' scaduto e' il server, che
// lo annuncia su /ws/eventi — cosi' suona anche a scheda chiusa e
// anche sull'Echo. Se il collegamento agli eventi non c'e' (rete giu',
// versione vecchia del server) il ticker torna a suonare da solo:
// meglio un avviso locale che nessun avviso.
function startTimerTick() {
    if (_timerInterval) clearInterval(_timerInterval);
    _timerInterval = setInterval(() => {
        let cambiato = false;
        for (const t of _activeTimers) {
            if (t.remaining_seconds > 0) {
                t.remaining_seconds -= 1;
                cambiato = true;
                if (t.remaining_seconds === 0 && !t._notified && !_eventiCollegati) {
                    t._notified = true;
                    playChimeAlert();
                    speakText(`Attenzione, il timer per ${t.label} è terminato!`);
                }
            }
        }
        if (cambiato || _activeTimers.length > 0) {
            renderTimers();
        }
    }, 1000);
}

// ============ PROMEMORIA ============
let _promemoria = [];

async function loadReminders() {
    try {
        const res = await fetch('/api/reminders', { headers: getAuthHeaders() });
        if (!res.ok) return;
        _promemoria = (await res.json()).filter(r => !r.completed);
        renderReminders();
    } catch (e) { console.error('Errore loadReminders:', e); }
}

function _quandoLeggibile(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso || '';
    const oggi = new Date();
    const stessoGiorno = d.toDateString() === oggi.toDateString();
    const ora = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    return stessoGiorno ? `oggi alle ${ora}` : `${d.toLocaleDateString('it-IT', { day: '2-digit', month: 'short' })} alle ${ora}`;
}

function renderReminders() {
    const container = document.getElementById('lista-promemoria');
    if (!container) return;
    if (!_promemoria || _promemoria.length === 0) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = _promemoria.map(r => `
        <div class="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
                <div class="w-7 h-7 rounded-lg bg-sky-600/30 text-sky-300 flex items-center justify-center font-bold text-xs">🔔</div>
                <div>
                    <h4 class="font-bold text-xs text-slate-200">${_testoSicuro(r.text)}</h4>
                    <span class="text-[11px] text-slate-400">${_quandoLeggibile(r.remind_at)}</span>
                </div>
            </div>
            <button onclick="deleteReminder('${r.id}')" class="text-slate-500 hover:text-rose-400 p-1 transition" title="Cancella promemoria">
                <i data-lucide="x" class="w-4 h-4"></i>
            </button>
        </div>
    `).join('');
    safeCreateIcons();
}

// Il testo di un promemoria arriva da cio' che l'utente ha detto: non
// finisce mai nell'HTML senza essere neutralizzato.
function _testoSicuro(testo) {
    const d = document.createElement('div');
    d.textContent = testo || '';
    return d.innerHTML;
}

async function deleteReminder(id) {
    await fetch(`/api/reminders/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    _promemoria = _promemoria.filter(r => r.id !== id);
    renderReminders();
}

// ============ COSA SCATTERA' FRA POCO (issue #123) ============
// Al posto del nome del modello e della frase di Alexa — due cose che
// non cambiano da un'ora all'altra — la colonna della console dice
// cosa sta per fare la casa. Il prossimo scatto lo sa gia' il server:
// `/api/regole` lo calcola per ogni regola e lo chiama `prossimo`.
async function caricaProssimiScatti() {
    const contenitore = document.getElementById('prossimi-scatti');
    if (!contenitore) return;
    try {
        const risposta = await fetch('/api/regole', { headers: getAuthHeaders() });
        if (!risposta.ok) return;
        const dati = await risposta.json();
        disegnaProssimiScatti(dati.regole || []);
    } catch (e) {
        contenitore.innerHTML = '<div class="text-[11px] text-slate-500 text-center py-2">Non riesco a leggere il calendario della casa.</div>';
    }
}

function disegnaProssimiScatti(regole) {
    const contenitore = document.getElementById('prossimi-scatti');
    if (!contenitore) return;

    // Una regola zittita non scattera'; una su evento non ha un orario.
    // Qui si guarda solo cio' che ha una data e sta per arrivare.
    const attese = (regole || [])
        .filter(r => r.attiva && r.prossimo && !isNaN(new Date(r.prossimo)))
        .sort((a, b) => new Date(a.prossimo) - new Date(b.prossimo))
        .slice(0, 4);

    // L'etichetta sta dentro cio' che si disegna, non sopra il
    // pannello: un titolo fisso in piu' era esattamente il peso che
    // questa colonna doveva smettere di avere.
    const etichetta = '<p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Fra poco, da sola</p>';

    if (!attese.length) {
        contenitore.innerHTML = etichetta + `
            <div class="text-[11px] text-slate-500 py-1 leading-relaxed">
                Niente in programma: nelle prossime ore la casa aspetta te.
                <button type="button" onclick="switchTab('automazioni')" class="text-indigo-400 hover:text-indigo-300 font-semibold underline decoration-dotted">Vedi le automazioni</button>
            </div>`;
        return;
    }

    contenitore.innerHTML = etichetta + attese.map(r => `
        <div class="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-between gap-2.5">
            <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-7 h-7 rounded-lg bg-emerald-600/25 text-emerald-300 flex items-center justify-center shrink-0">
                    <i data-lucide="zap" class="w-3.5 h-3.5"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-200 truncate">${_testoSicuro(r.nome || 'Automazione')}</h4>
                    <span class="text-[11px] text-emerald-400">${_quandoLeggibile(r.prossimo)}</span>
                </div>
            </div>
        </div>
    `).join('');
    safeCreateIcons();
}

// ============ EVENTI IN TEMPO REALE (/ws/eventi) ============
let _eventiSocket = null;
let _eventiCollegati = false;
let _attesaRiconnessione = 1000;

function _segnalaStatoEventi(collegato) {
    _eventiCollegati = collegato;
    const spia = document.getElementById('stato-eventi');
    if (spia) {
        spia.className = `w-2 h-2 rounded-full ${collegato ? 'bg-emerald-500' : 'bg-slate-600'}`;
        spia.title = collegato ? 'Eventi del server collegati' : 'Eventi del server non collegati: gli avvisi arrivano solo da questa scheda';
    }
}

function collegaEventi() {
    if (_eventiSocket && _eventiSocket.readyState <= 1) return;
    const protocollo = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
        _eventiSocket = new WebSocket(`${protocollo}//${location.host}/ws/eventi`);
    } catch (e) {
        console.warn('WebSocket eventi non disponibile:', e);
        return;
    }

    _eventiSocket.onopen = () => {
        _attesaRiconnessione = 1000;
        _segnalaStatoEventi(true);
    };

    _eventiSocket.onmessage = (msg) => {
        let evento;
        try { evento = JSON.parse(msg.data); } catch (e) { return; }
        gestisciEvento(evento);
    };

    _eventiSocket.onclose = () => {
        _segnalaStatoEventi(false);
        // Riconnessione con attesa crescente, al massimo mezzo minuto:
        // un server riavviato non deve subire una raffica di tentativi.
        setTimeout(collegaEventi, _attesaRiconnessione);
        _attesaRiconnessione = Math.min(_attesaRiconnessione * 2, 30000);
    };

    _eventiSocket.onerror = () => { try { _eventiSocket.close(); } catch (e) {} };
}

function gestisciEvento(evento) {
    if (evento.tipo === 'timer.scaduto') {
        const t = _activeTimers.find(x => x.id === evento.dati.id);
        if (t) { t.remaining_seconds = 0; t._notified = true; }
        playChimeAlert();
        speakText(evento.frase || 'Il timer è scaduto.');
        loadTimers();
    } else if (evento.tipo === 'promemoria.scaduto') {
        playChimeAlert();
        speakText(evento.frase || 'Hai un promemoria.');
        loadReminders();
    } else if (evento.tipo === 'ha.stato_cambiato') {
        aggiornaStatoCasa(evento.dati);
    } else if (evento.tipo.startsWith('persona.') || evento.tipo.startsWith('casa.')) {
        caricaPresenza();
    }
}

// ==================== CHI C'E' IN CASA ====================
// Riferimento: issue #22. La pastiglia mostra anche chi Home Assistant
// da' per uscito e a cui non stiamo ancora credendo: e' il ritardo
// contro i buchi del GPS, e vederlo spiega perche' la casa non ha
// ancora reagito.

async function caricaPresenza() {
    const pill = document.getElementById('presenza-pill');
    if (!pill) return;
    try {
        const res = await fetch('/api/presenza', { headers: getAuthHeaders() });
        if (!res.ok) return;
        const p = await res.json();

        if (!p.conosciuta) {
            // Nessuna persona configurata in Home Assistant: dire
            // «casa vuota» sarebbe una deduzione dal nulla.
            pill.style.display = 'none';
            return;
        }
        pill.style.display = 'flex';

        const punto = document.getElementById('presenza-punto');
        const testo = document.getElementById('presenza-testo');
        const quanti = (p.presenti || []).length;
        const attesa = (p.in_attesa || []).length;

        if (punto) punto.className = `w-2 h-2 rounded-full ${p.abitata ? 'bg-emerald-400' : 'bg-slate-500'}`;
        if (testo) {
            testo.textContent = quanti === 0 ? 'Casa vuota'
                : quanti === 1 ? '1 in casa'
                : `${quanti} in casa`;
        }
        pill.title = [
            (p.presenti || []).map(e => e.split('.').pop()).join(', ') || 'nessuno in casa',
            attesa ? `in attesa di conferma: ${(p.in_attesa || []).map(e => e.split('.').pop()).join(', ')}` : ''
        ].filter(Boolean).join(' — ');
    } catch (e) {
        console.warn('Presenza non disponibile:', e);
    }
}

// ==================== STATO DELLA CASA IN TEMPO REALE ====================
// Fino alla 0.2.0 lo stato dei dispositivi arrivava solo quando lo si
// chiedeva. Adesso Home Assistant lo manda quando cambia — anche
// quando a premere e' l'interruttore a muro, che e' il caso che una
// pagina che interroga a intervalli non vedrebbe mai in tempo.
// Riferimento: issue #19.

let _statiCasa = {};

function _chiaveStato(entityId) {
    // Gli identificativi contengono un punto: negli attributi `id` va
    // bene, ma romperebbe un selettore CSS. Qui non si usano
    // selettori, e getElementById non ha il problema — la chiave resta
    // comunque pulita, cosi' non diventa un problema domani.
    return (entityId || '').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function _testoStato(entityId) {
    const s = _statiCasa[entityId];
    return s ? s.stato : '';
}

function aggiornaStatoCasa(dati) {
    if (!dati || !dati.entity_id) return;
    _statiCasa[dati.entity_id] = dati;

    const el = document.getElementById(`stato-${_chiaveStato(dati.entity_id)}`);
    if (!el) return;

    el.textContent = dati.stato || '';
    const acceso = ['on', 'open', 'playing', 'home', 'unlocked'].includes((dati.stato || '').toLowerCase());
    el.className = `text-[10px] font-semibold ${acceso ? 'text-emerald-400' : 'text-slate-500'}`;

    // Un lampo breve: senza, un cambiamento che arriva mentre si
    // guarda altrove passa inosservato e sembra che non sia successo
    // niente.
    el.animate(
        [{ opacity: 0.35 }, { opacity: 1 }],
        { duration: 400, easing: 'ease-out' }
    );
}

// ==================== MODULAR ROUTINE BUILDER ====================
let _allModesCache = [];
let _modeAccordionState = {};

function toggleModeSteps(modeId) {
    _modeAccordionState[modeId] = !_modeAccordionState[modeId];
    const stepsEl = document.getElementById(`mode-steps-${modeId}`);
    const btnEl = document.getElementById(`mode-steps-toggle-${modeId}`);
    if (stepsEl) stepsEl.classList.toggle('hidden', !_modeAccordionState[modeId]);
    if (btnEl) btnEl.innerHTML = _modeAccordionState[modeId] ? 'Nascondi Moduli ▲' : 'Vedi Moduli ▼';
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
            container.innerHTML = '<div class="col-span-2 text-center py-8 text-slate-500 text-xs">Nessuna routine configurata. Clicca "+ Nuova Routine Modulare" per crearne una.</div>';
            return;
        }

        container.innerHTML = _allModesCache.map(m => {
            const triggers = (m.trigger_phrases || []).map(t => `<span class="px-2 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-[10px] text-slate-300 font-mono">"${t}"</span>`).join(' ');
            const actions = m.actions || [];
            const isOpen = Boolean(_modeAccordionState[m.id]);

            const stepsHtml = actions.map((act, idx) => {
                let icon = 'zap';
                let title = 'Azione';
                let desc = '';
                let badge = '';

                if (act.type === 'ha_device' || act.type === 'ha_service') {
                    icon = 'power';
                    title = act.entity_id || act.data?.entity_id || 'Dispositivo HA';
                    const cmd = act.action || act.service || 'turn_on';
                    desc = cmd === 'turn_on' ? 'Accendi' : cmd === 'turn_off' ? 'Spegni' : cmd;
                    badge = `<span class="text-[10px] text-indigo-400 bg-indigo-950/80 px-1.5 py-0.5 rounded border border-indigo-800">💡 HA</span>`;
                } else if (act.type === 'delay') {
                    icon = 'clock';
                    title = `Pausa ${act.seconds || act.delay_seconds || 1}s`;
                    desc = 'Attesa prima del prossimo step';
                    badge = `<span class="text-[10px] text-amber-400 bg-amber-950/80 px-1.5 py-0.5 rounded border border-amber-800">⏱️ Pausa</span>`;
                } else if (act.type === 'tts') {
                    icon = 'message-circle';
                    title = 'Annuncio Vocale';
                    desc = `"${act.message || ''}"`;
                    badge = `<span class="text-[10px] text-emerald-400 bg-emerald-950/80 px-1.5 py-0.5 rounded border border-emerald-800">🗣️ Parla</span>`;
                }

                return `
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
            }).join('');

            return `
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
                        <button onclick="triggerModularMode('${m.name}', '${m.id}')" id="btn-run-mode-${m.id}" class="px-3.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/40 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition">
                            <i data-lucide="play" class="w-3.5 h-3.5"></i> Esegui
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        safeCreateIcons();
    } catch (e) { console.error('loadModes error:', e); }
}

async function triggerModularMode(name, modeId) {
    const btn = document.getElementById(`btn-run-mode-${modeId}`);
    const card = document.getElementById(`mode-card-${modeId}`);
    if (btn) btn.innerHTML = '<span class="animate-spin">⏳</span> Esecuzione...';
    if (card) card.classList.add('border-indigo-500', 'ring-1', 'ring-indigo-500/50');

    try {
        const res = await fetch(`/api/modes/${encodeURIComponent(name)}/activate`, { headers: getAuthHeaders(), method: 'POST' });
        const data = await res.json();
        if (data.messaggio) speakText(data.messaggio);
    } catch (e) { console.error('Errore attivazione modalità:', e); }

    setTimeout(() => {
        if (btn) btn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5"></i> ▶️ Esegui Test';
        if (card) card.classList.remove('border-indigo-500', 'ring-1', 'ring-indigo-500/50');
        safeCreateIcons();
    }, 1200);
}

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

function updateNodeData(nodeId, field, val) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (node) {
        node.data[field] = val;
    }
}

function setQuickDelay(nodeId, secs) {
    updateNodeData(nodeId, 'seconds', secs);
    renderCanvasElements();
}

function startDragNode(nodeId, e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'BUTTON') return;
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const canvas = document.getElementById('flow-canvas');
    const rect = canvas.getBoundingClientRect();
    _canvasState.isDraggingNode = nodeId;
    _canvasState.dragOffset = {
        x: (e.clientX - rect.left) - node.x,
        y: (e.clientY - rect.top) - node.y
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
        const exists = _canvasState.edges.some(x =>
            x.from === _canvasState.connectingSourceId && x.to === targetNodeId && (x.ramo || null) === ramo
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
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    // Si riparte da zero al cambio di tipo: i campi di una condizione
    // non valgono per un'altra, e lasciarli in giro produce una
    // condizione che porta con sé dati che nessuno legge.
    const predefiniti = {
        presenza: { tipo: 'presenza', abitata: true },
        stato_entita: { tipo: 'stato_entita', entity_id: '', stato: '' },
        fra_le_ore: { tipo: 'fra_le_ore', dalle: '20:00', alle: '23:00' },
        giorni: { tipo: 'giorni', giorni: [] }
    };
    node.data.condizione = predefiniti[tipo] || { tipo: tipo };
    renderCanvasElements();
}

function setTipoInnesco(nodeId, tipo) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
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
        evento: { tipo: 'evento', evento: '' }
    };
    node.data.trigger = predefiniti[tipo] || { tipo: tipo };
    renderCanvasElements();
}

function setDatoInnesco(nodeId, campo, valore) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    node.data.trigger = node.data.trigger || { tipo: 'voce' };
    node.data.trigger[campo] = valore;
}

function alternaGiornoInnesco(nodeId, giorno) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const t = node.data.trigger = node.data.trigger || { tipo: 'orario' };
    const scelti = new Set(t.giorni || []);
    scelti.has(giorno) ? scelti.delete(giorno) : scelti.add(giorno);
    t.giorni = [...scelti].sort();
    renderCanvasElements();
}

function setDatoCondizione(nodeId, campo, valore) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    node.data.condizione = node.data.condizione || {};
    node.data.condizione[campo] = valore;
}

function alternaGiorno(nodeId, giorno) {
    const node = _canvasState.nodes.find(n => n.id === nodeId);
    if (!node) return;
    const c = node.data.condizione = node.data.condizione || { tipo: 'giorni' };
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
            message: ''
        }
    };
    // Una condizione nasce con qualcosa dentro: un nodo vuoto e' vero
    // per definizione, e chi lo trascina si accorge del ramo sbagliato
    // solo eseguendo.
    if (type === 'condizione') newNode.data.condizione = { tipo: 'presenza', abitata: true };
    if (type === 'notifica') { newNode.data.titolo = ''; newNode.data.testo = ''; }
    _canvasState.nodes.push(newNode);
    renderCanvasElements();
}

function deleteCanvasNode(nodeId) {
    _canvasState.nodes = _canvasState.nodes.filter(n => n.id !== nodeId);
    _canvasState.edges = _canvasState.edges.filter(e => e.from !== nodeId && e.to !== nodeId);
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
        const fromNode = _canvasState.nodes.find(n => n.id === edge.from);
        const toNode = _canvasState.nodes.find(n => n.id === edge.to);
        if (fromNode && toNode) {
            const x1 = fromNode.x + 240; // output pin (right side)
            const y1 = fromNode.y + 20;  // pin y position
            const x2 = toNode.x;         // input pin (left side)
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
        const srcNode = _canvasState.nodes.find(n => n.id === _canvasState.connectingSourceId);
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
            body: JSON.stringify({ nodes: _canvasState.nodes, edges: _canvasState.edges })
        });
        if (!res.ok) throw new Error('simulazione rifiutata');
        esito = await res.json();
    } catch (e) {
        if (btn) btn.innerHTML = testoPulsante;
        alert('Non riesco a simulare adesso: il server non ha risposto.');
        return;
    }

    spegniLaSimulazione();

    const decisioni = new Map((esito.decisioni || []).map(d => [d.node_id, d]));
    const visitati = esito.visitati || [];
    mostraLeDecisioni(esito.decisioni || []);

    for (const idNodo of visitati) {
        const el = document.getElementById(`c-node-${idNodo}`);
        if (el) el.classList.add('ring-2', 'ring-violet-400', 'border-violet-400', 'scale-[1.02]');

        const nodo = _canvasState.nodes.find(n => n.id === idNodo);
        if (nodo && nodo.type === 'delay') {
            await new Promise(r => setTimeout(r, Math.min((nodo.data.seconds || 3) * 1000, 3000)));
        } else if (nodo && nodo.type === 'tts') {
            playChimeAlert();
            if (nodo.data.message) speakText(nodo.data.message);
            await new Promise(r => setTimeout(r, 1000));
        } else {
            await new Promise(r => setTimeout(r, 600));
        }

        if (el) el.classList.remove('ring-2', 'ring-violet-400', 'border-violet-400', 'scale-[1.02]');

        // Si accende solo il cavo percorso: da una condizione esce il
        // ramo scelto e basta, ed e' tutta la differenza fra vedere
        // cosa succede e vedere cosa potrebbe succedere.
        const scelta = decisioni.get(idNodo);
        const uscenti = _canvasState.edges.filter(e =>
            e.from === idNodo &&
            visitati.includes(e.to) &&
            (!scelta || !e.ramo || e.ramo === scelta.ramo)
        );
        for (const arco of uscenti) {
            const cavo = document.getElementById(`wire-${arco.from}-${arco.to}`);
            if (cavo) cavo.classList.add('flow-wire-sim');
        }
        await new Promise(r => setTimeout(r, 400));
    }

    if (btn) btn.innerHTML = testoPulsante;
}

function spegniLaSimulazione() {
    document.querySelectorAll('.flow-wire-sim').forEach(el => el.classList.remove('flow-wire-sim'));
    document.querySelectorAll('.decisione-del-nodo').forEach(el => el.remove());
}

function mostraLeDecisioni(decisioni) {
    // Il ramo preso senza il perche' e' indistinguibile da un ramo
    // preso a caso: chi guarda vuole sapere che la condizione ha detto
    // no perche' in casa non c'e' nessuno, non solo che ha detto no.
    (decisioni || []).forEach(d => {
        const el = document.getElementById(`c-node-${d.node_id}`);
        if (!el) return;
        const etichetta = document.createElement('div');
        etichetta.className = 'decisione-del-nodo absolute -bottom-6 left-0 right-0 text-[10px] font-semibold text-center px-1 truncate '
            + (d.ramo === 'vero' ? 'text-emerald-400' : 'text-rose-400');
        etichetta.title = d.motivo || '';
        etichetta.innerText = d.ramo === 'vero' ? '→ ramo sì' : ('→ ramo no: ' + (d.motivo || 'la condizione non è soddisfatta'));
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
    _canvasState.nodes.forEach(n => {
        if (n.type !== 'trigger') {
            linearActions.push({
                type: n.type,
                entity_id: n.data.entity_id,
                action: n.data.action,
                seconds: n.data.seconds,
                message: n.data.message
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
        actions: linearActions
    };

    const res = await fetch('/api/modes', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(payload)
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
            'Non salvo questa routine:\n\n' +
            problemi.map(p => '• ' + p.messaggio).join('\n\n') ||
            (dettaglio.messaggio || 'Il grafo non è valido.')
        );
    } else {
        alert('Errore nel salvataggio della routine.');
    }
}

function illuminaNodiInErrore(problemi) {
    document.querySelectorAll('.flow-node').forEach(el => el.classList.remove('nodo-in-errore'));
    (problemi || []).forEach(p => (p.nodi || []).forEach(id => {
        const el = document.getElementById(`c-node-${id}`);
        if (el) el.classList.add('nodo-in-errore');
    }));
}

async function deleteMode(id) {
    if (!confirm('Eliminare questa routine?')) return;
    await fetch(`/api/modes/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadModes();
}

// ==================== AUTOMAZIONI (le regole della #27) ====================
//
// Il motore delle regole esisteva da due versioni senza nessuna
// schermata. Non era un dettaglio estetico: una casa che agisce da
// sola e non sa dire perché è una casa che si spegne, e finché le
// regole non si vedevano l'unico modo di chiedere «perché non è
// successo niente?» era leggere i log del server.

async function loadRegole() {
    const contenitore = document.getElementById('regole-lista');
    if (!contenitore) return;
    try {
        // Anche le routine, non solo le regole. Una routine a innesco
        // vocale non e' un'automazione — parte solo se la chiami — ma
        // e' la cosa che chi guarda questa schermata **ha gia'
        // disegnato**, e non vederla qui fa credere di non aver fatto
        // niente. E' la domanda da cui e' nata la issue #127.
        const [risposta, risposteModi] = await Promise.all([
            fetch('/api/regole', { headers: getAuthHeaders() }),
            fetch('/api/modes', { headers: getAuthHeaders() })
        ]);
        const dati = await risposta.json();
        const modi = risposteModi.ok ? await risposteModi.json() : [];
        renderRegole(dati.regole || [], Array.isArray(modi) ? modi : []);
        // Le stesse regole servono alla colonna della console: chi
        // zittisce una regola qui deve vederla sparire di la' subito,
        // non al prossimo giro del minuto.
        disegnaProssimiScatti(dati.regole || []);
    } catch (e) {
        contenitore.innerHTML = '<p class="text-xs text-rose-400 p-4">Non riesco a leggere le automazioni: il server non ha risposto.</p>';
    }
}

// Le routine adesso stanno nella stessa schermata, piu' in basso.
// «Vai alle routine» non e' piu' un cambio di scheda ma uno
// scorrimento: cambiare scheda verso se stessi non fa niente, ed e'
// esattamente cio' che sarebbe successo lasciando `switchTab('modes')`
// dopo aver unito le due schede (#128).
function vaiAlleRoutine() {
    switchTab('automazioni');
    const elenco = document.getElementById('modes-list');
    if (elenco && elenco.scrollIntoView) {
        elenco.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}


// ============ LA SCORCIATOIA (issue #126) ============
// `POST /api/regole` c'era dalla v0.3.0 e nessuno la chiamava da qui.
// Questa e' una porta in piu' sulla stessa stanza: un innesco, nessuna
// condizione, un'azione. L'editor a nodi resta intatto e resta la
// strada per rami, condizioni, ritardi e sequenze — quando serve di
// piu', questo modulo **porta li'** invece di crescere.

function _campiQuandoScorciatoia(tipo) {
    if (tipo === 'orario') {
        return `<input type="time" id="scorciatoia-ora" value="23:00" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">`;
    }
    if (tipo === 'alba' || tipo === 'tramonto') {
        return `
            <label class="text-[11px] text-slate-500 block">Minuti di scarto (negativi per anticipare)</label>
            <input type="number" id="scorciatoia-scarto" value="0" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">`;
    }
    if (tipo === 'stato') {
        return `
            <input type="text" id="scorciatoia-entita" placeholder="es. sensor.temperatura_salotto" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">
            <select id="scorciatoia-confronto" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200">
                <option value="attraversa_sotto">scende sotto</option>
                <option value="attraversa_sopra">sale sopra</option>
                <option value="diventa">diventa</option>
            </select>
            <input type="text" id="scorciatoia-valore" placeholder="es. 15" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">`;
    }
    return `<input type="text" id="scorciatoia-evento" placeholder="es. casa.vuota" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">`;
}

function _campiCosaScorciatoia(tipo) {
    if (tipo === 'modalita') {
        // Le routine gia' disegnate: la scorciatoia non le duplica, le
        // fa partire. E' l'aggancio fra le due meta' di questa scheda.
        const routine = (_allModesCache || []).map(m =>
            `<option value="${_testoSicuro(m.name || m.id)}">${_testoSicuro(m.name || m.id)}</option>`
        ).join('');
        if (!routine) {
            return `<p class="text-[11px] text-amber-400 leading-snug">Non hai ancora routine da far partire. Disegnane una qui sotto, oppure scegli un'altra azione.</p>`;
        }
        return `<select id="scorciatoia-modalita" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200">${routine}</select>`;
    }
    if (tipo === 'dispositivo') {
        return `
            <input type="text" id="scorciatoia-dispositivo" placeholder="es. light.salotto" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">
            <select id="scorciatoia-servizio" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200">
                <option value="turn_off">spegni</option>
                <option value="turn_on">accendi</option>
            </select>`;
    }
    return `<input type="text" id="scorciatoia-testo" placeholder="es. Ricordati di chiudere il gas" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-100">`;
}

function disegnaScorciatoia() {
    const quando = document.getElementById('scorciatoia-quando');
    const cosa = document.getElementById('scorciatoia-cosa');
    if (!quando || !cosa) return;

    document.getElementById('scorciatoia-quando-campi').innerHTML = _campiQuandoScorciatoia(quando.value);
    document.getElementById('scorciatoia-cosa-campi').innerHTML = _campiCosaScorciatoia(cosa.value);
    _mostraEsitoScorciatoia(null);
}

// L'innesco come lo vuole il server, dai campi che ci sono adesso.
function inniescoDallaScorciatoia() {
    const tipo = (document.getElementById('scorciatoia-quando') || {}).value || 'orario';
    const leggi = (id, ripiego) => {
        const campo = document.getElementById(id);
        return campo ? campo.value : ripiego;
    };

    if (tipo === 'orario') return { tipo: 'orario', ora: leggi('scorciatoia-ora', '23:00'), giorni: [] };
    if (tipo === 'alba' || tipo === 'tramonto') {
        return { tipo: tipo, scarto_minuti: parseInt(leggi('scorciatoia-scarto', '0'), 10) || 0 };
    }
    if (tipo === 'stato') {
        return {
            tipo: 'stato',
            entity_id: leggi('scorciatoia-entita', ''),
            confronto: leggi('scorciatoia-confronto', 'attraversa_sotto'),
            valore: leggi('scorciatoia-valore', '')
        };
    }
    return { tipo: 'evento', evento: leggi('scorciatoia-evento', '') };
}

function _azioneDallaScorciatoia() {
    const tipo = (document.getElementById('scorciatoia-cosa') || {}).value || 'modalita';
    const leggi = (id, ripiego) => {
        const campo = document.getElementById(id);
        return campo ? campo.value : ripiego;
    };

    if (tipo === 'modalita') return { tipo: 'modalita', modalita: leggi('scorciatoia-modalita', '') };
    if (tipo === 'dispositivo') {
        return {
            tipo: 'dispositivo',
            entity_id: leggi('scorciatoia-dispositivo', ''),
            servizio: leggi('scorciatoia-servizio', 'turn_off')
        };
    }
    return { tipo: 'avviso', testo: leggi('scorciatoia-testo', '') };
}

// Un nome scritto da noi e' meglio di «Nuova regola 3»: dice cosa fa,
// e chi la ritrova fra sei mesi non deve aprirla per ricordarselo.
function nomeDallaScorciatoia(innesco, azione) {
    const quando = {
        orario: `Alle ${innesco.ora || ''}`,
        alba: "All'alba",
        tramonto: 'Al tramonto',
        stato: `Quando ${innesco.entity_id || 'qualcosa'} cambia`,
        evento: `Su ${innesco.evento || 'un evento'}`
    }[innesco.tipo] || 'Automazione';

    const cosa = {
        modalita: `avvia «${azione.modalita || ''}»`,
        dispositivo: `${azione.servizio === 'turn_on' ? 'accendi' : 'spegni'} ${azione.entity_id || ''}`,
        avviso: 'mandami un avviso'
    }[azione.tipo] || 'fai qualcosa';

    return `${quando}, ${cosa}`.trim();
}

function _mostraEsitoScorciatoia(messaggio, andata) {
    const riquadro = document.getElementById('scorciatoia-esito');
    if (!riquadro) return;
    if (!messaggio) {
        riquadro.className = 'hidden p-2.5 rounded-lg';
        riquadro.innerHTML = '';
        return;
    }
    riquadro.className = andata
        ? 'p-2.5 rounded-lg bg-emerald-950/70 border border-emerald-800 text-emerald-300'
        : 'p-2.5 rounded-lg bg-rose-950 border border-rose-800 text-rose-300';
    riquadro.innerText = messaggio;
}

async function creaScorciatoia() {
    const innesco = inniescoDallaScorciatoia();
    const azione = _azioneDallaScorciatoia();
    const scritto = (document.getElementById('scorciatoia-nome') || {}).value || '';

    const bottone = document.getElementById('scorciatoia-crea');
    if (bottone) bottone.disabled = true;

    try {
        const risposta = await fetch('/api/regole', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                nome: scritto.trim() || nomeDallaScorciatoia(innesco, azione),
                trigger: innesco,
                condizioni: [],
                azioni: [azione]
            })
        });

        const dati = await risposta.json().catch(() => ({}));

        if (!risposta.ok) {
            // Il server sa gia' dire perche' no — «Trigger sconosciuto»,
            // «Un trigger su stato ha bisogno di un'entita'». Quella
            // frase vale piu' di qualunque controllo riscritto qui, e
            // si legge nella schermata invece di sparire in un avviso.
            _mostraEsitoScorciatoia(_testoDelDettaglio(dati.detail, risposta.status), false);
            return;
        }

        _mostraEsitoScorciatoia('Fatta. La trovi qui sotto, con il suo prossimo scatto.', true);
        const nome = document.getElementById('scorciatoia-nome');
        if (nome) nome.value = '';
        loadRegole();
    } catch (e) {
        _mostraEsitoScorciatoia('Il server non ha risposto: l\'automazione non e\' stata creata.', false);
    } finally {
        if (bottone) bottone.disabled = false;
    }
}

// «Serve qualcosa di piu' complicato?» — l'editor si apre con
// l'innesco gia' messo. Ricominciare da capo sarebbe il modo piu'
// sicuro di far tornare tutti a disegnare da zero ogni volta.
function apriEditorDallaScorciatoia() {
    const innesco = inniescoDallaScorciatoia();
    openModularModeBuilder();

    const nodo = (_canvasState.nodes || []).find(n => n.type === 'trigger');
    if (nodo) {
        nodo.data = nodo.data || {};
        nodo.data.trigger = innesco;
    }
    const scritto = (document.getElementById('scorciatoia-nome') || {}).value || '';
    if (scritto.trim()) _canvasState.name = scritto.trim();

    renderFlowCanvasModal();
}

function quandoScatta(regola) {
    // Tre stati diversi che una schermata ingenua confonde in uno.
    // «Nessun prossimo scatto» su una regola su evento è normale;
    // sulla stessa riga di una regola all'alba è il difetto che ha
    // tenuto ferme le regole del sole per due versioni.
    if (!regola.attiva) return { testo: 'messa a tacere', colore: 'text-slate-500' };
    if (regola.prossimo) {
        const quando = new Date(regola.prossimo);
        return {
            testo: 'prossima volta ' + quando.toLocaleString('it-IT', { weekday: 'short', hour: '2-digit', minute: '2-digit' }),
            colore: 'text-emerald-400'
        };
    }
    if (regola.aspetta_un_evento) return { testo: 'aspetta che succeda qualcosa', colore: 'text-sky-400' };
    return { testo: 'non programmata: non scatterà', colore: 'text-rose-400' };
}

// Le routine che hanno gia' generato un'automazione. Una regola nata
// da un disegno porta `origine: "grafo:<id della routine>"`, ed e'
// l'unico modo di sapere, da qui, quali routine partono da sole.
function routineSoloVocali(regole, modi) {
    const automatizzate = new Set(
        regole
            .map(r => String(r.origine || ''))
            .filter(o => o.startsWith('grafo:'))
            .map(o => o.slice('grafo:'.length))
    );
    return (modi || []).filter(m => !automatizzate.has(String(m.id)));
}

function renderRegole(regole, modi) {
    const contenitore = document.getElementById('regole-lista');
    if (!contenitore) return;

    const pezzi = [];

    if (!regole.length) {
        pezzi.push(`
            <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-8 text-center">
                <i data-lucide="zap-off" class="w-8 h-8 text-slate-600 mx-auto mb-3"></i>
                <p class="text-sm text-slate-300 font-semibold">La casa non fa ancora niente da sola.</p>
                <p class="text-xs text-slate-500 mt-2 max-w-md mx-auto">
                    Le automazioni nascono dagli inneschi delle routine: apri una routine
                    <span class="text-slate-300">qui sotto</span>, metti un innesco
                    «a un orario» o «al tramonto» sul primo nodo, e salva.
                </p>
                <button type="button" onclick="vaiAlleRoutine()" class="mt-4 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">
                    Vai alle routine
                </button>
            </div>`);
    }

    pezzi.push(regole.map(r => {
        const stato = quandoScatta(r);
        const dalGrafo = String(r.origine || '').startsWith('grafo:');
        const ultimo = r.ultimo_scatto ? new Date(r.ultimo_scatto).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : null;
        return `
            <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-3 ${r.attiva ? '' : 'opacity-60'}">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="font-semibold text-slate-100 text-sm truncate">${r.nome || 'Automazione'}</span>
                        ${dalGrafo ? '<span class="px-1.5 py-0.5 rounded bg-violet-600/20 text-violet-300 text-[10px] font-semibold border border-violet-500/30">dal disegno di una routine</span>' : ''}
                    </div>
                    <p class="text-xs text-slate-400 mt-0.5 truncate">${r.descrizione || ''}</p>
                    <div class="flex items-center gap-3 mt-1.5 flex-wrap text-[11px]">
                        <span class="${stato.colore} font-semibold">${stato.testo}</span>
                        ${ultimo ? `<span class="text-slate-500">ultima volta ${ultimo}${r.ultimo_esito ? ': ' + r.ultimo_esito : ''}</span>` : ''}
                        ${!ultimo && r.ultimo_esito ? `<span class="text-amber-400">${r.ultimo_esito}</span>` : ''}
                    </div>
                </div>
                <div class="flex items-center gap-2 shrink-0">
                    <button type="button" onclick="provaRegola('${r.id}')" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold" title="Esegue adesso, saltando l'innesco ma non le condizioni">
                        Prova
                    </button>
                    <button type="button" onclick="alternaRegola('${r.id}', ${!r.attiva})" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold ${r.attiva ? 'bg-amber-600/20 text-amber-300 hover:bg-amber-600/30' : 'bg-emerald-600/20 text-emerald-300 hover:bg-emerald-600/30'}">
                        ${r.attiva ? 'Zittisci' : 'Riattiva'}
                    </button>
                    ${dalGrafo
                        ? '<span class="text-[10px] text-slate-600 max-w-[7rem] leading-tight">Per toglierla, togli l\'innesco dalla routine</span>'
                        : `<button type="button" onclick="cancellaRegola('${r.id}')" class="p-1.5 text-slate-500 hover:text-rose-400" title="Elimina"><i data-lucide="trash-2" class="w-4 h-4"></i></button>`}
                </div>
            </div>`;
    }).join(''));

    // Le routine che partono solo se le chiami. Esistono, e chi le ha
    // disegnate se le ricorda: non vederle qui fa credere di non aver
    // fatto niente, ed e' esattamente cio' che e' successo in casa.
    const vocali = routineSoloVocali(regole, modi);
    if (vocali.length) {
        pezzi.push(`
            <div class="bg-slate-900/40 border border-slate-800 border-dashed rounded-2xl p-4 mt-2">
                <p class="text-xs font-semibold text-slate-300 flex items-center gap-2">
                    <i data-lucide="mic" class="w-3.5 h-3.5 text-slate-500"></i>
                    Queste partono solo se le chiami
                </p>
                <p class="text-[11px] text-slate-500 mt-1 mb-3">
                    Sono routine, non automazioni: aspettano la tua voce. Per farle
                    partire da sole, apri la routine e cambia l'innesco del primo blocco.
                </p>
                <div class="space-y-1.5">
                    ${vocali.map(m => `
                        <div class="flex items-center justify-between gap-3 px-3 py-2 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div class="min-w-0">
                                <span class="text-xs font-semibold text-slate-200">${m.name || m.id}</span>
                                ${(m.trigger_phrases || []).length
                                    ? `<span class="text-[10px] text-slate-500 font-mono ml-2 truncate">"${(m.trigger_phrases || [])[0]}"</span>`
                                    : '<span class="text-[10px] text-amber-400 ml-2">senza frasi: non la puoi nemmeno chiamare</span>'}
                            </div>
                            <button type="button" onclick="openModularModeBuilder('${m.id}')" class="shrink-0 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-semibold" title="Apre il disegno di questa routine">
                                Apri
                            </button>
                        </div>`).join('')}
                </div>
            </div>`);
    }

    contenitore.innerHTML = pezzi.join('');
    safeCreateIcons();
}

async function alternaRegola(id, attiva) {
    await fetch(`/api/regole/${id}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ attiva })
    });
    loadRegole();
}

async function provaRegola(id) {
    // «Prova» esegue saltando l'innesco **ma non le condizioni**: è
    // voluto, e serve a rispondere a «perché non scatta?». Una prova
    // che ignorasse anche le condizioni risponderebbe sempre di sì e
    // non direbbe niente.
    const res = await fetch(`/api/regole/${id}/prova`, { headers: getAuthHeaders(), method: 'POST' });
    const esito = await res.json().catch(() => ({}));
    if (esito.eseguita) {
        alert('Fatta adesso.');
    } else if (esito.motivo) {
        alert('Non è stata eseguita, e il motivo è questo:\n\n' + esito.motivo);
    } else {
        alert('Non è stata eseguita.');
    }
    loadRegole();
}

async function cancellaRegola(id) {
    if (!confirm('Eliminare questa automazione?')) return;
    await fetch(`/api/regole/${id}`, { headers: getAuthHeaders(), method: 'DELETE' });
    loadRegole();
}

// ==================== USERS CRUD & AVATARS ====================
let _selectedAvatarType = 'male_adult';

function selectUserAvatar(type) {
    _selectedAvatarType = type;
    const types = ['male_adult', 'female_adult', 'male_child', 'female_child', 'neutral', 'guest'];
    types.forEach(t => {
        const btn = document.getElementById(`av-btn-${t}`);
        if (btn) {
            btn.classList.toggle('ring-2', t === type);
            btn.classList.toggle('ring-indigo-500', t === type);
            btn.classList.toggle('bg-slate-800', t === type);
            btn.classList.toggle('scale-105', t === type);
        }
    });

    // Auto-align age group
    const ageSelect = document.getElementById('new-u-age');
    if (ageSelect) {
        if (type.includes('child')) ageSelect.value = 'child';
        else if (type === 'guest') ageSelect.value = 'adult';
    }
}

async function loadUsers() {
    // I permessi si rileggono a ogni apertura della scheda: un ruolo
    // cambiato mentre la pagina e' aperta deve valere subito, non al
    // prossimo ricaricamento del browser.
    await caricaPermessiCorrenti();
    const amministra = posso('utenti.gestisci');

    const btnNuovo = document.getElementById('btn-nuovo-utente');
    if (btnNuovo) btnNuovo.style.display = amministra ? 'flex' : 'none';

    try {
        const res = await fetch('/api/users', { headers: getAuthHeaders() });
        const items = await res.json();
        usersData = items;
        const container = document.getElementById('users-list');
        if (!container) return;

        container.innerHTML = items.map(u => {
            const av = getUserAvatarInfo(u);
            return `
            <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 hover:border-slate-700 transition group shadow-sm">
                <div class="flex justify-between items-start">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-2xl ${av.bg} border ${av.border} flex items-center justify-center text-xl shadow-inner shrink-0">
                            ${av.emoji}
                        </div>
                        <div>
                            <h4 class="font-bold text-xs text-slate-100 flex items-center gap-1.5">${u.name}</h4>
                            <div class="flex flex-wrap items-center gap-1 mt-0.5">
                                <span class="px-2 py-0.5 rounded-full ${av.bg} border ${av.border} text-[10px] ${av.text} font-semibold">${av.badge}</span>
                                <span class="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-[10px] text-slate-300 font-semibold" title="Cosa puo' comandare">${_testoSicuro(nomeDelRuolo(u.role))}</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-1.5">
                        ${amministra ? `
                        <button onclick="openEditUserModal('${u.id}')" class="px-2.5 py-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 border border-indigo-600/40 text-indigo-300 hover:text-white text-[11px] font-semibold flex items-center gap-1 transition" title="Modifica profilo e avatar">
                            <i data-lucide="edit-3" class="w-3 h-3"></i> Modifica
                        </button>` : ''}
                        ${amministra && u.id !== 'alessio' ? `
                        <button onclick="deleteUser('${u.id}')" class="text-slate-600 hover:text-rose-400 p-1 opacity-0 group-hover:opacity-100 transition" title="Elimina profilo">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>` : (u.id === 'alessio' ? `<span class="text-[10px] text-indigo-400/80 font-mono px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-900/50">Admin</span>` : '')}
                    </div>
                </div>
                <p class="text-[11px] text-slate-400 leading-relaxed">${u.notes || 'Nessuna nota o preferenza specifica.'}</p>
            </div>`;
        }).join('');
        safeCreateIcons();
    } catch (e) { console.error('loadUsers error:', e); }

    await loadRuoli();
    await loadDispositivi();
    await loadPasskey();
    // Dopo i profili, non prima: l'elenco delle voci disegna un menu
    // con i nomi di casa, e `usersData` dev'essere gia' pieno.
    await loadVoci();
}

function openAddUserModal() {
    openUserModal(null);
}

function openEditUserModal(userId) {
    openUserModal(userId);
}

function openUserModal(userId = null) {
    const user = userId ? usersData.find(u => u.id === userId) : null;
    const isEdit = Boolean(user);
    _selectedAvatarType = (user && user.avatar_type) ? user.avatar_type : 'male_adult';

    const defaultName = user ? user.name : '';
    const defaultAge = user ? (user.age_group || 'adult') : 'adult';
    const defaultNotes = user ? (user.notes || '') : '';
    // Il ruolo si sceglie. Prima veniva dedotto da avatar e fascia
    // d'eta', e un ragazzo finiva con il ruolo `adult`: cioe' con le
    // serrature. La deduzione resta solo come proposta iniziale per un
    // profilo nuovo, e si puo' cambiare.
    const ruoloProposto = _selectedAvatarType === 'guest' ? 'guest'
        : (defaultAge === 'child' ? 'child' : (defaultAge === 'teen' ? 'teen' : 'adult'));
    const ruoloAttuale = user ? (user.role || ruoloProposto) : ruoloProposto;
    const elencoRuoli = ruoliData.length ? ruoliData : [{ id: ruoloAttuale, nome: ruoloAttuale }];
    const opzioniRuolo = elencoRuoli.map(r =>
        `<option value="${_testoSicuro(r.id)}" ${r.id === ruoloAttuale ? 'selected' : ''}>${_testoSicuro(r.nome)}</option>`
    ).join('');

    showModal(`
        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                <i data-lucide="${isEdit ? 'user-cog' : 'user-plus'}" class="w-4 h-4 text-indigo-400"></i>
                ${isEdit ? `Modifica Profilo di ${user.name}` : 'Registra Membro della Famiglia'}
            </h3>
            <button onclick="closeModal()" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>

        <div class="space-y-4 pt-3">
            <div>
                <label class="text-[11px] font-semibold text-slate-400 block mb-1.5">1. Scegli l'Icona / Avatar:</label>
                <div class="grid grid-cols-3 gap-2">
                    <button type="button" id="av-btn-male_adult" onclick="selectUserAvatar('male_adult')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">👨</span>
                        <span class="text-[10px] font-bold text-indigo-300">Uomo</span>
                    </button>
                    <button type="button" id="av-btn-female_adult" onclick="selectUserAvatar('female_adult')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">👩</span>
                        <span class="text-[10px] font-bold text-rose-300">Donna</span>
                    </button>
                    <button type="button" id="av-btn-male_child" onclick="selectUserAvatar('male_child')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">👦</span>
                        <span class="text-[10px] font-bold text-cyan-300">Bambino</span>
                    </button>
                    <button type="button" id="av-btn-female_child" onclick="selectUserAvatar('female_child')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">👧</span>
                        <span class="text-[10px] font-bold text-pink-300">Bambina</span>
                    </button>
                    <button type="button" id="av-btn-neutral" onclick="selectUserAvatar('neutral')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">🧑</span>
                        <span class="text-[10px] font-bold text-amber-300">Neutro</span>
                    </button>
                    <button type="button" id="av-btn-guest" onclick="selectUserAvatar('guest')" class="p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-center transition flex flex-col items-center gap-1 hover:border-slate-700">
                        <span class="text-2xl">🤖</span>
                        <span class="text-[10px] font-bold text-slate-400">Ospite</span>
                    </button>
                </div>
            </div>

            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">2. Nome:</label>
                <input type="text" id="new-u-name" value="${defaultName.replace(/"/g, '&quot;')}" placeholder="es. Marco, Sofia, Luca" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
            </div>

            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">3. Fascia d'Età & Filtri:</label>
                <select id="new-u-age" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                    <option value="adult" ${defaultAge === 'adult' ? 'selected' : ''}>Adulto (Linguaggio Jarvis completo)</option>
                    <option value="teen" ${defaultAge === 'teen' ? 'selected' : ''}>Ragazzo (13-17 anni)</option>
                    <option value="child" ${defaultAge === 'child' ? 'selected' : ''}>Bambino / Junior (< 13 anni - Filtri protetti)</option>
                </select>
            </div>

            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">4. Ruolo (cosa puo' comandare):</label>
                <select id="new-u-role" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500">
                    ${opzioniRuolo}
                </select>
                <p class="text-[10px] text-slate-500 mt-1 leading-relaxed">
                    Il ruolo decide cosa questa persona puo' comandare in casa. La fascia d'eta' qui sopra cambia soltanto il tono delle risposte: sono due cose diverse, e prima venivano confuse.
                </p>
            </div>

            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">5. Note o Preferenze (opzionale):</label>
                <input type="text" id="new-u-notes" value="${defaultNotes.replace(/"/g, '&quot;')}" placeholder="es. Moglie, camera da letto, appassionata di giardinaggio" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
            </div>
        </div>

        <div class="flex justify-end gap-2 pt-4 border-t border-slate-800 mt-4">
            <button onclick="closeModal()" class="px-3.5 py-2 rounded-xl bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 transition">Annulla</button>
            <button onclick="saveUserForm('${userId || ''}')" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5 transition shadow-md shadow-indigo-600/30">
                <i data-lucide="check" class="w-3.5 h-3.5"></i> ${isEdit ? 'Salva Modifiche' : 'Crea Profilo'}
            </button>
        </div>
    `, false);

    selectUserAvatar(_selectedAvatarType);
}

async function saveUserForm(existingUserId = '') {
    const name = document.getElementById('new-u-name').value.trim();
    const age_group = document.getElementById('new-u-age').value;
    const notes = document.getElementById('new-u-notes').value.trim();
    if (!name) return;

    const id = existingUserId || name.toLowerCase().replace(/\s+/g, '_');
    let gender = 'neutral';
    if (_selectedAvatarType.startsWith('male')) gender = 'male';
    else if (_selectedAvatarType.startsWith('female')) gender = 'female';

    const userToUpdate = existingUserId ? usersData.find(u => u.id === existingUserId) : null;
    const preferred_news_categories = userToUpdate ? (userToUpdate.preferred_news_categories || ["generale"]) : ["generale"];
    const campoRuolo = document.getElementById('new-u-role');
    const role = campoRuolo ? campoRuolo.value : (userToUpdate ? userToUpdate.role : 'guest');

    const res = await fetch('/api/users', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            id,
            name,
            role,
            age_group,
            gender,
            avatar_type: _selectedAvatarType,
            preferred_news_categories,
            notes
        })
    });
    // Declassare l'ultimo amministratore e' l'errore che chiude fuori
    // di casa: il server lo rifiuta e dice perche'. Ignorarlo, come si
    // faceva prima, faceva sembrare il salvataggio riuscito.
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }

    closeModal();
    await loadUsers();
    await loadUsersDropdown();
}

async function deleteUser(id) {
    if (!confirm('Rimuovere questo profilo famiglia?\n\nAnche i suoi dispositivi fidati verranno revocati.')) return;
    const res = await fetch(`/api/users/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }
    await loadUsers();
    await loadUsersDropdown();
}


// ==================== RUOLI, PERMESSI E DISPOSITIVI ====================
// Questa schermata non decide niente: il server rifiuta comunque, rotta
// per rotta. Qui si nasconde soltanto cio' che non porterebbe da nessuna
// parte — un pulsante che risponde sempre 403 non protegge, sembra un
// guasto. Riferimento: issue #46 e #47, ADR 0004.

let ruoliData = [];
let permessiCatalogo = [];
let _permessiCorrenti = [];

function posso(permesso) {
    return _permessiCorrenti.includes(permesso);
}

async function caricaPermessiCorrenti() {
    try {
        const res = await fetch('/api/auth/status', { headers: getAuthHeaders() });
        if (!res.ok) { _permessiCorrenti = []; return; }
        _permessiCorrenti = (await res.json()).permessi || [];
    } catch (e) {
        console.warn('Permessi non leggibili:', e);
        _permessiCorrenti = [];
    }
}

// Un rifiuto si spiega. Le rotte dei ruoli rispondono con il motivo
// («il ruolo e' assegnato a Thomas: cambia prima il suo»), e buttarlo
// via per mostrare «errore» lascerebbe l'utente senza la sola cosa
// che gli serve sapere.
async function _dettaglioErrore(res) {
    try {
        const corpo = await res.json();
        return _testoDelDettaglio(corpo.detail || corpo.message, res.status);
    } catch (e) {
        return `Errore ${res.status}`;
    }
}

// Non tutti i rifiuti sono una frase. Quando e' la validazione a dire
// di no, FastAPI risponde con l'elenco dei campi che non tornano, e
// ogni voce e' un oggetto: `{loc, msg}`. Passarlo ad alert() com'e'
// stampa «[object Object]», che non dice ne' cosa e' successo ne' dove
// guardare — ed e' quello che la casa ha visto per giorni ogni volta
// che si premeva il microfono.
function _testoDelDettaglio(dettaglio, stato) {
    if (typeof dettaglio === 'string' && dettaglio) return dettaglio;
    if (Array.isArray(dettaglio)) {
        const righe = dettaglio.map(voce => {
            const dove = Array.isArray(voce && voce.loc) ? voce.loc.join(' > ') : '';
            const cosa = (voce && (voce.msg || voce.message)) || JSON.stringify(voce);
            return dove ? `${dove}: ${cosa}` : cosa;
        }).filter(Boolean);
        if (righe.length) return `Errore ${stato}\n\n` + righe.join('\n');
    }
    if (dettaglio && typeof dettaglio === 'object') {
        return `Errore ${stato}\n\n` + JSON.stringify(dettaglio);
    }
    return `Errore ${stato}`;
}

function nomeDelRuolo(idRuolo) {
    const r = ruoliData.find(x => x.id === idRuolo);
    return r ? r.nome : (idRuolo || 'senza ruolo');
}

async function loadRuoli() {
    // I ruoli servono anche al modale del profilo, quindi si leggono
    // sempre; e' la sezione che si mostra solo a chi puo' modificarli.
    try {
        const [rRuoli, rPermessi] = await Promise.all([
            fetch('/api/ruoli', { headers: getAuthHeaders() }),
            fetch('/api/permessi', { headers: getAuthHeaders() })
        ]);
        if (rRuoli.ok) ruoliData = await rRuoli.json();
        if (rPermessi.ok) permessiCatalogo = await rPermessi.json();
    } catch (e) {
        console.error('loadRuoli error:', e);
    }

    const sezione = document.getElementById('sezione-ruoli');
    if (sezione) sezione.style.display = posso('utenti.gestisci') ? 'block' : 'none';
    if (!posso('utenti.gestisci')) return;

    const container = document.getElementById('ruoli-lista');
    if (!container) return;

    container.innerHTML = ruoliData.map(r => {
        const scelti = r.permessi || [];
        const etichette = permessiCatalogo.length
            ? permessiCatalogo.filter(p => scelti.includes(p.id)).map(p => {
                const rischioso = p.id === 'sicurezza.comanda';
                const colore = rischioso
                    ? 'bg-rose-950/60 border-rose-900/60 text-rose-300'
                    : 'bg-slate-800 border-slate-700 text-slate-300';
                return `<span class="px-2 py-0.5 rounded-full border text-[10px] ${colore}">${_testoSicuro(p.descrizione)}</span>`;
            }).join('')
            : '';
        const quanti = usersData.filter(u => u.role === r.id).length;
        const idSicuro = encodeURIComponent(r.id);
        return `
        <div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3 hover:border-slate-700 transition">
            <div class="flex justify-between items-start gap-3">
                <div>
                    <h4 class="font-bold text-xs text-slate-100 flex items-center gap-2">
                        ${_testoSicuro(r.nome)}
                        ${r.predefinito ? '<span class="px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-900/50 text-[9px] text-indigo-300 font-mono">predefinito</span>' : ''}
                    </h4>
                    <p class="text-[11px] text-slate-400 leading-relaxed mt-0.5">${_testoSicuro(r.descrizione) || 'Nessuna descrizione.'}</p>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                    <button onclick="apriModaleRuolo('${idSicuro}')" class="px-2.5 py-1 rounded-xl bg-indigo-600/20 hover:bg-indigo-600 border border-indigo-600/40 text-indigo-300 hover:text-white text-[11px] font-semibold flex items-center gap-1 transition" title="Modifica i permessi">
                        <i data-lucide="edit-3" class="w-3 h-3"></i> Permessi
                    </button>
                    ${r.predefinito ? '' : `
                    <button onclick="cancellaRuolo('${idSicuro}')" class="text-slate-600 hover:text-rose-400 p-1 transition" title="Cancella il ruolo">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                    </button>`}
                </div>
            </div>
            <div class="flex flex-wrap gap-1.5">${etichette || `<span class="text-[10px] text-slate-500 italic">Nessun permesso: puo&#39; solo chiedere.</span>`}</div>
            <p class="text-[10px] text-slate-500 border-t border-slate-800 pt-2">
                ${quanti === 0 ? 'Nessun profilo lo usa.' : (quanti === 1 ? '1 profilo lo usa.' : `${quanti} profili lo usano.`)}
            </p>
        </div>`;
    }).join('');
    safeCreateIcons();
}

function apriModaleRuolo(idRuolo) {
    const identificativo = idRuolo ? decodeURIComponent(idRuolo) : null;
    const ruolo = identificativo ? ruoliData.find(r => r.id === identificativo) : null;
    const scelti = ruolo ? (ruolo.permessi || []) : [];
    const modifica = Boolean(ruolo);

    const caselle = permessiCatalogo.map(p => {
        const rischioso = p.id === 'sicurezza.comanda';
        return `
        <label class="flex items-start gap-2.5 p-2.5 rounded-xl bg-slate-950 border ${rischioso ? 'border-rose-900/50' : 'border-slate-800'} hover:border-slate-700 cursor-pointer transition">
            <input type="checkbox" class="permesso-casella mt-0.5 accent-indigo-500" value="${_testoSicuro(p.id)}" ${scelti.includes(p.id) ? 'checked' : ''}>
            <span class="leading-tight">
                <span class="block text-[11px] font-semibold ${rischioso ? 'text-rose-300' : 'text-slate-200'}">${_testoSicuro(p.descrizione)}</span>
                <span class="block text-[10px] text-slate-500 font-mono">${_testoSicuro(p.id)}</span>
            </span>
        </label>`;
    }).join('');

    showModal(`
        <div class="flex items-center justify-between pb-3 border-b border-slate-800">
            <h3 class="font-bold text-sm text-slate-100 flex items-center gap-2">
                <i data-lucide="shield-check" class="w-4 h-4 text-indigo-400"></i>
                ${modifica ? `Permessi di ${_testoSicuro(ruolo.nome)}` : 'Nuovo Ruolo'}
            </h3>
            <button onclick="closeModal()" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>

        <div class="space-y-4 pt-3">
            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">Nome del ruolo:</label>
                <input type="text" id="ruolo-nome" value="${_testoSicuro(ruolo ? ruolo.nome : '')}" placeholder="es. Collaboratrice domestica, Nonno, Ospite fine settimana" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1">Descrizione (opzionale):</label>
                <input type="text" id="ruolo-descrizione" value="${_testoSicuro(ruolo ? ruolo.descrizione : '')}" placeholder="A cosa serve questo ruolo" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="text-[11px] font-semibold text-slate-300 block mb-1.5">Cosa puo' fare:</label>
                <div class="grid grid-cols-1 gap-1.5 max-h-72 overflow-y-auto pr-1">${caselle || '<p class="text-[11px] text-slate-500">Catalogo dei permessi non disponibile.</p>'}</div>
            </div>
        </div>

        <div class="flex justify-end gap-2 pt-4 border-t border-slate-800 mt-4">
            <button onclick="closeModal()" class="px-3.5 py-2 rounded-xl bg-slate-800 text-xs text-slate-300 hover:bg-slate-700 transition">Annulla</button>
            <button onclick="salvaRuolo('${identificativo ? encodeURIComponent(identificativo) : ''}')" class="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-semibold flex items-center gap-1.5 transition shadow-md shadow-indigo-600/30">
                <i data-lucide="check" class="w-3.5 h-3.5"></i> ${modifica ? 'Salva Permessi' : 'Crea Ruolo'}
            </button>
        </div>
    `, false);
}

async function salvaRuolo(idRuolo) {
    const identificativo = idRuolo ? decodeURIComponent(idRuolo) : '';
    const nome = document.getElementById('ruolo-nome').value.trim();
    if (!nome) { alert('Il ruolo deve avere un nome.'); return; }

    const scelti = Array.from(document.querySelectorAll('.permesso-casella'))
        .filter(c => c.checked)
        .map(c => c.value);

    const res = await fetch('/api/ruoli', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
            id: identificativo,
            nome,
            descrizione: document.getElementById('ruolo-descrizione').value.trim(),
            permessi: scelti
        })
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }

    closeModal();
    await loadUsers();
}

async function cancellaRuolo(idRuolo) {
    const identificativo = decodeURIComponent(idRuolo);
    if (!confirm(`Cancellare il ruolo «${nomeDelRuolo(identificativo)}»?`)) return;

    const res = await fetch(`/api/ruoli/${encodeURIComponent(identificativo)}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }
    await loadUsers();
}

// ---------------------------------------------------- dispositivi fidati

function _quando(iso) {
    if (!iso) return 'mai';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return 'mai';
    return d.toLocaleString('it-IT', {
        day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    });
}

async function loadDispositivi() {
    const container = document.getElementById('dispositivi-lista');
    if (!container) return;

    let elenco = [];
    try {
        const res = await fetch('/api/dispositivi', { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(await _dettaglioErrore(res));
        elenco = await res.json();
    } catch (e) {
        console.error('loadDispositivi error:', e);
        container.innerHTML = `<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-rose-300">Impossibile leggere i dispositivi fidati.</div>`;
        return;
    }

    const ambito = document.getElementById('dispositivi-ambito');
    if (ambito) {
        ambito.textContent = posso('utenti.gestisci')
            ? 'Vedi quelli di tutta la casa.'
            : 'Vedi i tuoi.';
    }

    const revocaTutti = document.getElementById('btn-revoca-tutti');
    if (revocaTutti) revocaTutti.style.display = elenco.length > 1 ? 'flex' : 'none';

    if (!elenco.length) {
        container.innerHTML = `<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            Nessun dispositivo ricordato. Ne compare uno qui quando al momento del PIN si sceglie «ricorda questo dispositivo».
        </div>`;
        return;
    }

    const nomeDi = id => {
        const u = usersData.find(x => x.id === id);
        return u ? u.name : id;
    };

    container.innerHTML = elenco.map(d => `
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border ${d.questo ? 'border-indigo-600/50' : 'border-slate-800'} flex items-center justify-between gap-3 group">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <i data-lucide="smartphone" class="w-4 h-4 text-slate-400"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-100 flex items-center gap-1.5 truncate">
                        ${_testoSicuro(d.nome)}
                        ${d.questo ? '<span class="px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-900/50 text-[9px] text-indigo-300 font-semibold shrink-0">questo dispositivo</span>' : ''}
                    </h4>
                    <p class="text-[10px] text-slate-500 truncate">
                        ${_testoSicuro(nomeDi(d.user_id))} · ultimo accesso ${_quando(d.ultimo_uso)}${d.ultimo_indirizzo ? ` · ${_testoSicuro(d.ultimo_indirizzo)}` : ''}
                    </p>
                </div>
            </div>
            <button onclick="revocaDispositivo('${encodeURIComponent(d.id)}', '${_testoSicuro(d.nome).replace(/'/g, "\\'")}', ${d.questo ? 'true' : 'false'})" class="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-rose-600 border border-slate-700 hover:border-rose-500 text-[11px] text-slate-300 hover:text-white font-semibold shrink-0 transition">
                Revoca
            </button>
        </div>`).join('');
    safeCreateIcons();
}

async function revocaDispositivo(idDispositivo, nome, eQuesto) {
    const avvertenza = eQuesto
        ? '\n\nE\' il dispositivo da cui stai guardando: dovrai ridigitare il PIN.'
        : '';
    if (!confirm(`Revocare «${nome}»? Al prossimo accesso chiedera' di nuovo il PIN.${avvertenza}`)) return;

    const res = await fetch(`/api/dispositivi/${idDispositivo}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }
    await loadDispositivi();
}

async function revocaTuttiDispositivi() {
    if (!confirm('Revocare tutti i dispositivi fidati?\n\nQuello da cui stai guardando resta valido: serve a questo, quando si perde un telefono.')) return;

    const res = await fetch('/api/dispositivi/revoca-tutti', {
        method: 'POST',
        headers: getAuthHeaders()
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }

    const esito = await res.json();
    alert(esito.revocati === 1 ? 'Un dispositivo revocato.' : `${esito.revocati} dispositivi revocati.`);
    await loadDispositivi();
}

// ==================== PASSKEY (issue #48) ====================
//
// Le proprie, non quelle di casa: una passkey e' personale come un
// dispositivo fidato. WebAuthn scambia byte e JSON scambia stringhe,
// quindi tutto passa da base64url — con i trattini al posto di piu' e
// barra, e senza riempimento. Sbagliare dialetto di base64 e' il modo
// piu' comune di far fallire una passkey senza capire perche'.

function _daBase64url(testo) {
    const normale = testo.replace(/-/g, '+').replace(/_/g, '/');
    const grezzo = atob(normale + '='.repeat((4 - normale.length % 4) % 4));
    return Uint8Array.from(grezzo, c => c.charCodeAt(0));
}

function _aBase64url(buffer) {
    let grezzo = '';
    for (const b of new Uint8Array(buffer)) grezzo += String.fromCharCode(b);
    return btoa(grezzo).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function loadPasskey() {
    const container = document.getElementById('passkey-lista');
    if (!container) return;

    let stato = { disponibile: false, spiegazione: '' };
    try {
        const res = await fetch('/api/auth/passkey/stato', { headers: getAuthHeaders() });
        if (res.ok) stato = await res.json();
    } catch (e) { console.error('stato passkey:', e); }

    const puo = stato.disponibile && !!window.PublicKeyCredential;
    const bottone = document.getElementById('btn-aggiungi-passkey');
    if (bottone) bottone.style.display = puo ? 'flex' : 'none';

    const nota = document.getElementById('passkey-nota');
    // La spiegazione del server dice *perche'* non si puo' e cosa
    // fare: un pulsante assente senza motivo sembra una funzione
    // rotta, non una funzione non disponibile qui.
    if (nota) nota.textContent = puo ? '' : (stato.spiegazione || 'Non disponibili su questo dispositivo.');

    let elenco = [];
    try {
        const res = await fetch('/api/auth/passkey', { headers: getAuthHeaders() });
        if (res.ok) elenco = await res.json();
    } catch (e) { console.error('loadPasskey:', e); }

    if (!elenco.length) {
        container.innerHTML = `<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            Nessuna passkey. Il PIN continua a funzionare: le passkey lo affiancano, non lo sostituiscono.
        </div>`;
        return;
    }

    container.innerHTML = elenco.map(p => `
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border border-slate-800 flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <i data-lucide="fingerprint" class="w-4 h-4 text-slate-400"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-100 truncate">${_testoSicuro(p.nome)}</h4>
                    <p class="text-[10px] text-slate-500 truncate">
                        aggiunta ${_quando(p.creata_il)} · ultimo accesso ${_quando(p.ultimo_uso)}${p.tipo_dispositivo === 'multi_device' ? ' · sincronizzata' : ''}
                    </p>
                </div>
            </div>
            <button onclick="revocaPasskey('${encodeURIComponent(p.id)}', '${_testoSicuro(p.nome).replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-rose-600 border border-slate-700 hover:border-rose-500 text-[11px] text-slate-300 hover:text-white font-semibold shrink-0 transition">
                Revoca
            </button>
        </div>`).join('');
    safeCreateIcons();
}

function _nomeDispositivo() {
    const ua = navigator.userAgent || '';
    if (/iPhone/i.test(ua)) return 'iPhone';
    if (/iPad/i.test(ua)) return 'iPad';
    if (/Android/i.test(ua)) return /Mobile/i.test(ua) ? 'Telefono Android' : 'Tablet Android';
    if (/Macintosh/i.test(ua)) return 'Mac';
    if (/Windows/i.test(ua)) return 'Computer Windows';
    if (/Linux/i.test(ua)) return 'Computer Linux';
    return 'Dispositivo';
}

async function aggiungiPasskey() {
    try {
        const avvio = await fetch('/api/auth/passkey/registrazione/inizio', {
            method: 'POST', headers: getAuthHeaders()
        });
        if (!avvio.ok) { alert(await _dettaglioErrore(avvio)); return; }
        const { sfida_id, opzioni } = await avvio.json();

        opzioni.challenge = _daBase64url(opzioni.challenge);
        opzioni.user.id = _daBase64url(opzioni.user.id);
        for (const c of (opzioni.excludeCredentials || [])) c.id = _daBase64url(c.id);

        const credenziale = await navigator.credentials.create({ publicKey: opzioni });
        if (!credenziale) return;

        const fine = await fetch('/api/auth/passkey/registrazione/fine', {
            method: 'POST',
            headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sfida_id: sfida_id,
                nome: _nomeDispositivo(),
                credenziale: {
                    id: credenziale.id,
                    rawId: _aBase64url(credenziale.rawId),
                    type: credenziale.type,
                    response: {
                        clientDataJSON: _aBase64url(credenziale.response.clientDataJSON),
                        attestationObject: _aBase64url(credenziale.response.attestationObject)
                    }
                }
            })
        });
        if (!fine.ok) { alert(await _dettaglioErrore(fine)); return; }
    } catch (e) {
        // Chi annulla il riconoscimento non ha sbagliato niente.
        if (e && (e.name === 'NotAllowedError' || e.name === 'AbortError')) return;
        if (e && e.name === 'InvalidStateError') {
            alert('Questo dispositivo ha gia\' una passkey per il tuo profilo.');
            return;
        }
        alert('Non sono riuscito ad aggiungere la passkey: ' + ((e && e.message) || e));
        return;
    }
    await loadPasskey();
}

async function revocaPasskey(identificativo, nome) {
    if (!confirm(`Revocare «${nome}»?\n\nQuel dispositivo tornera' a chiedere il PIN.`)) return;

    const res = await fetch(`/api/auth/passkey/${identificativo}`, {
        method: 'DELETE', headers: getAuthHeaders()
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }
    await loadPasskey();
}

// ==================== VOCI RICONOSCIUTE (issue #48) ====================
//
// Una voce non associata non e' un dettaglio estetico: comanda con i
// permessi di un ospite. Questo elenco esiste perche' associarla non
// richieda di copiare a mano un identificativo opaco letto in un log.

async function loadVoci() {
    const container = document.getElementById('voci-lista');
    if (!container) return;

    let elenco = [];
    try {
        const res = await fetch('/api/voci', { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(await _dettaglioErrore(res));
        elenco = await res.json();
    } catch (e) {
        console.error('loadVoci error:', e);
        container.innerHTML = `<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-rose-300">Impossibile leggere le voci sentite.</div>`;
        return;
    }

    if (!elenco.length) {
        container.innerHTML = `<div class="p-4 rounded-2xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            Nessuna voce sentita. Ne compare una qui quando qualcuno parla a un Echo e i profili vocali di Alexa sono configurati.
        </div>`;
        return;
    }

    const puoAssociare = posso('utenti.gestisci');
    const opzioni = utente => usersData.map(u =>
        `<option value="${_testoSicuro(u.id)}"${u.id === utente ? ' selected' : ''}>${_testoSicuro(u.name)}</option>`
    ).join('');

    container.innerHTML = elenco.map(v => {
        const noto = !!v.user_id;
        return `
        <div class="p-3.5 rounded-2xl bg-slate-900/60 border ${noto ? 'border-slate-800' : 'border-amber-700/50'} flex items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
                <div class="w-9 h-9 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0">
                    <i data-lucide="${noto ? 'user-check' : 'user-x'}" class="w-4 h-4 ${noto ? 'text-slate-400' : 'text-amber-400'}"></i>
                </div>
                <div class="min-w-0">
                    <h4 class="font-bold text-xs text-slate-100 truncate">
                        ${noto ? _testoSicuro(v.nome_profilo) : 'Voce non associata'}
                    </h4>
                    <p class="text-[10px] text-slate-500 truncate">
                        ${v.quante_volte} richieste · ultima ${_quando(v.ultima_volta)}${noto ? '' : ' · comanda come un ospite'}
                    </p>
                </div>
            </div>
            ${puoAssociare ? `
            <div class="flex items-center gap-1.5 shrink-0">
                <select onchange="associaVoce('${encodeURIComponent(v.person_id)}', this.value)" class="px-2 py-1 rounded-xl bg-slate-800 border border-slate-700 text-[11px] text-slate-200">
                    <option value=""${noto ? '' : ' selected'}>— nessuno —</option>
                    ${opzioni(v.user_id)}
                </select>
                <button onclick="dimenticaVoce('${encodeURIComponent(v.person_id)}')" class="px-2.5 py-1 rounded-xl bg-slate-800 hover:bg-rose-600 border border-slate-700 hover:border-rose-500 text-[11px] text-slate-300 hover:text-white font-semibold transition">
                    Dimentica
                </button>
            </div>` : ''}
        </div>`;
    }).join('');
    safeCreateIcons();
}

async function associaVoce(personId, userId) {
    const res = await fetch('/api/voci/associa', {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: decodeURIComponent(personId), user_id: userId || null })
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); }
    await loadVoci();
}

async function dimenticaVoce(personId) {
    // Dimenticare non e' revocare: se quella voce parla ancora, la riga
    // ricompare — sconosciuta, senza permessi.
    if (!confirm('Dimenticare questa voce?\n\nSe parla di nuovo ricompare qui, senza permessi.')) return;

    const res = await fetch(`/api/voci/${personId}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
    });
    if (!res.ok) { alert(await _dettaglioErrore(res)); return; }
    await loadVoci();
}

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
