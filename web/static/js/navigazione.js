let activeUserId = 'alessio';
let usersData = [];

// Store del display originale per ogni tab
const tabDisplayMap = {
    console: 'grid',
    knowledge: 'block',
    sources: 'block',
    aliases: 'block',
    automazioni: 'block',
    users: 'block',
    settings: 'block',
};

// Le destinazioni di prima che adesso sono la stessa schermata.
// Stanno qui e non nei punti che le chiamano: una scorciatoia scritta
// altrove nella pagina — o un collegamento che qualcuno si e' salvato
// — deve continuare a portare dove serve, non in una scheda che non
// esiste piu'. Riferimento: #128.
const SCHEDE_UNITE = {
    modes: 'automazioni',
    regole: 'automazioni',
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
    if (_menuConfigurazioneAperto) {
        chiudiMenuConfigurazione();
        return;
    }
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
    Object.keys(tabDisplayMap).forEach((id) => {
        const el = document.getElementById(`tab-${id}`);
        if (el) el.style.display = 'none';
    });

    // Resetta tutti i pulsanti desktop
    document.querySelectorAll('.tab-btn').forEach((el) => {
        el.classList.remove('bg-indigo-600/30', 'text-indigo-300', 'border-indigo-500/40', 'border');
        el.classList.add('text-slate-400');
    });

    // Mostra il tab selezionato
    const targetEl = document.getElementById(`tab-${tabId}`);
    if (targetEl) targetEl.style.display = tabDisplayMap[tabId] || 'block';

    // Attiva il pulsante selezionato. Le quattro schede dietro
    // «Configurazione» non hanno un pulsante proprio: si accende il
    // loro ingresso, che e' da dove ci si e' passati.
    const btn =
        document.getElementById(`tab-btn-${tabId}`) ||
        (SCHEDE_DI_CONFIGURAZIONE.includes(tabId) ? document.getElementById('tab-btn-configurazione') : null);
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
    if (tabId === 'automazioni') {
        loadRegole();
        loadModes();
        disegnaScorciatoia();
    }
    if (tabId === 'users') loadUsers();
    if (tabId === 'settings') {
        loadSettings();
        preparaSezioniImpostazioni();
    }
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
    } catch {
        /* senza memoria si vive */
    }
}

function _sezioneRicordata() {
    try {
        return window.localStorage.getItem(MEMORIA_SEZIONE);
    } catch {
        return null;
    }
}

function preparaSezioniImpostazioni() {
    const sezioni = document.querySelectorAll('.sezione-impostazioni');
    if (!sezioni.length) return;

    const ricordata = _sezioneRicordata();
    if (ricordata) {
        let trovata = false;
        sezioni.forEach((sezione) => {
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

    sezioni.forEach((sezione) => {
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
            sezioni.forEach((altra) => {
                if (altra !== sezione) altra.open = false;
            });
            _ricordaSezione(sezione.getAttribute('data-sezione'));
            safeCreateIcons();
        });
    });
}

// Inizializzazione del layout tab all'avvio
function initTabs() {
    Object.keys(tabDisplayMap).forEach((id) => {
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
        return {
            emoji: '🤖',
            label: 'Ospite',
            color: 'slate',
            badge: 'Ospite',
            border: 'border-slate-700',
            bg: 'bg-slate-800/80',
            text: 'text-slate-300',
        };
    }
    if (avatarType === 'female_child' || (age === 'child' && gender === 'female')) {
        return {
            emoji: '👧',
            label: 'Bimba',
            color: 'pink',
            badge: 'Junior 👧',
            border: 'border-pink-500/50',
            bg: 'bg-pink-500/20',
            text: 'text-pink-300',
        };
    }
    if (avatarType === 'male_child' || (age === 'child' && gender === 'male')) {
        return {
            emoji: '👦',
            label: 'Bimbo',
            color: 'cyan',
            badge: 'Junior 👦',
            border: 'border-cyan-500/50',
            bg: 'bg-cyan-500/20',
            text: 'text-cyan-300',
        };
    }
    if (avatarType === 'female_adult' || (age !== 'child' && gender === 'female')) {
        return {
            emoji: '👩',
            label: 'Donna',
            color: 'rose',
            badge: 'Famiglia',
            border: 'border-rose-500/50',
            bg: 'bg-rose-500/20',
            text: 'text-rose-300',
        };
    }
    if (avatarType === 'male_adult' || (age !== 'child' && gender === 'male')) {
        return {
            emoji: '👨',
            label: 'Uomo',
            color: 'indigo',
            badge: 'Famiglia',
            border: 'border-indigo-500/50',
            bg: 'bg-indigo-500/20',
            text: 'text-indigo-300',
        };
    }
    return {
        emoji: '🧑',
        label: 'Membro',
        color: 'amber',
        badge: 'Membro',
        border: 'border-amber-500/50',
        bg: 'bg-amber-500/20',
        text: 'text-amber-300',
    };
}

// Active User Management
async function loadUsersDropdown() {
    try {
        const res = await fetch('/api/users', { headers: getAuthHeaders() });
        usersData = await res.json();
        const select = document.getElementById('user-select');
        const mobileSelect = document.getElementById('mobile-user-select');
        const optionsHtml = usersData
            .map((u) => {
                const av = getUserAvatarInfo(u);
                return `<option value="${u.id}" ${u.id === activeUserId ? 'selected' : ''}>${av.emoji} ${u.name} (${u.role})</option>`;
            })
            .join('');

        if (select) select.innerHTML = optionsHtml;
        if (mobileSelect) mobileSelect.innerHTML = optionsHtml;
        updateActiveUserBanner();
    } catch (e) {
        console.error(e);
    }
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
    const user = usersData.find((u) => u.id === activeUserId) || {
        name: 'Utente',
        role: 'adult',
        age_group: 'adult',
    };
    const av = getUserAvatarInfo(user);
    const nameEl = document.getElementById('banner-user-name');
    const roleEl = document.getElementById('banner-user-role');
    if (nameEl) nameEl.innerHTML = `${av.emoji} ${user.name}`;
    if (roleEl) roleEl.innerText = `${user.role} • ${av.label}`;
}
