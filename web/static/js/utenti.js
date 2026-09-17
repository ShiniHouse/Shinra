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
