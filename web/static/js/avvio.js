function safeCreateIcons() {
    try {
        if (typeof lucide !== 'undefined' && lucide.createIcons) {
            lucide.createIcons();
        }
    } catch (e) {
        console.warn('Lucide icon render:', e);
    }
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
    ['aurora', 'sandstone', 'stealth'].forEach((p) => {
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
    const hour = now.getHours() + now.getMinutes() / 60;
    // Giorno Solare: dalle 07:00 alle 19:30, Notte: dalle 19:30 alle 07:00
    return hour >= 7.0 && hour < 19.5 ? 'light' : 'dark';
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
        const isDay = effectiveTheme === 'light';
        icon.innerHTML = _html`<i data-lucide="${isDay ? 'sun-medium' : 'moon'}" class="w-3.5 h-3.5 ${isDay ? 'text-amber-500' : 'text-indigo-400'}"></i>`;
        label.innerHTML = _html`Auto <span class="text-[10px] opacity-75 font-normal">(${isDay ? 'Giorno' : 'Notte'})</span>`;
        if (btn)
            btn.title = `Modalità Automatica attiva (${isDay ? 'Luce Solare fino alle 19:30' : 'Modalità Notturna fino alle 07:00'}). Clicca per forzare Giorno.`;
    } else if (currentThemeSetting === 'light') {
        icon.innerHTML = _html`<i data-lucide="sun" class="w-3.5 h-3.5 text-amber-500"></i>`;
        label.innerText = 'Giorno';
        if (btn) btn.title = 'Modalità Giorno forzata. Clicca per passare a Notte.';
    } else {
        icon.innerHTML = _html`<i data-lucide="moon" class="w-3.5 h-3.5 text-indigo-400"></i>`;
        label.innerText = 'Notte';
        if (btn) btn.title = 'Modalità Notte forzata. Clicca per tornare in Auto.';
    }
    safeCreateIcons();
}

// I gesti che il markup di quest'area puo' chiedere (#34). L'elenco e'
// la stessa forma che avra' la lista di `export` il giorno dei moduli.
Gesti.registra({
    cycleTheme,
    setPalette,
});
