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
        barra.className =
            'fixed top-0 left-0 right-0 z-[1000] px-4 py-2.5 bg-rose-600 text-white text-xs font-semibold flex items-center justify-center gap-3 shadow-lg';
        document.body.appendChild(barra);
    }
    // Il secondo periodo e' il punto di tutta la correzione: dice che
    // le schermate vuote potrebbero non esserlo.
    const messaggio =
        stato === 403
            ? "Non hai il permesso di vedere questa parte. Quello che manca non e' assente: e' riservato."
            : "La sessione e' scaduta. Le schermate che vedi vuote potrebbero non esserlo: rientra per saperlo.";
    barra.innerHTML = `<span>${messaggio}</span>`;
    if (stato !== 403) {
        const entra = document.createElement('button');
        entra.type = 'button';
        entra.className = 'px-2.5 py-1 rounded-lg bg-white/20 hover:bg-white/30 transition font-bold';
        entra.textContent = 'Rientra';
        entra.onclick = () => {
            nascondiRifiuto();
            lockSession();
        };
        barra.appendChild(entra);
    }
    const chiudi = document.createElement('button');
    chiudi.type = 'button';
    chiudi.className = 'px-2 py-1 rounded-lg hover:bg-white/20 transition';
    chiudi.textContent = '✕';
    chiudi.title = "Nascondi l'avviso";
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
            headers: getAuthHeaders(),
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
        const profili = (await res.json()).filter((p) => p.ha_pin);

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
        box.innerHTML = profili
            .map(
                (p) => `
            <button type="button" onclick="scegliProfiloAccesso('${p.id}', '${(p.name || '').replace(/'/g, "\\'")}')"
                class="p-3 rounded-2xl bg-slate-950 border border-slate-800 hover:border-indigo-500 hover:bg-slate-900 transition text-left flex items-center gap-2.5">
                <span class="w-8 h-8 rounded-xl bg-indigo-600/25 text-indigo-300 flex items-center justify-center font-bold text-sm shrink-0">
                    ${(p.name || '?').charAt(0).toUpperCase()}
                </span>
                <span class="text-sm font-semibold text-slate-200 truncate">${p.name || p.id}</span>
            </button>`,
            )
            .join('');
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
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin, user_id: _profiloDaAccedere }),
        });

        if (res.ok) {
            const data = await res.json();
            sessionStorage.setItem('shinra_auth_token', data.token);
            // L'utente attivo non e' piu' una scelta da menu: e' chi
            // ha appena dimostrato di essere se stesso con il PIN.
            if (data.utente && data.utente.id) {
                activeUserId = data.utente.id;
                try {
                    localStorage.setItem('shinra_active_user', data.utente.id);
                } catch {}
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
    } catch {
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
            headers: getAuthHeaders(),
        });
    } catch {}
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

    inactivityTimer = setTimeout(
        async () => {
            const isAuthEnabled = document.getElementById('cfg-sec-auth-enabled')?.checked;
            const token = sessionStorage.getItem('shinra_auth_token');
            if (isAuthEnabled || token) {
                console.log(
                    `[Shinra Security] Auto-lock attivato dopo ${inactivityTimeoutMinutes} min di inattività.`,
                );
                await lockSession();
            }
        },
        inactivityTimeoutMinutes * 60 * 1000,
    );
}

['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'click'].forEach((evt) => {
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
    const userName =
        typeof activeUserId !== 'undefined' && activeUserId
            ? activeUserId.charAt(0).toUpperCase() + activeUserId.slice(1)
            : 'Alessio';

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
