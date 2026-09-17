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
    } catch {
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
