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
            fetch('/api/modes', { headers: getAuthHeaders() }),
        ]);
        const dati = await risposta.json();
        const modi = risposteModi.ok ? await risposteModi.json() : [];
        renderRegole(dati.regole || [], Array.isArray(modi) ? modi : []);
        // Le stesse regole servono alla colonna della console: chi
        // zittisce una regola qui deve vederla sparire di la' subito,
        // non al prossimo giro del minuto.
        disegnaProssimiScatti(dati.regole || []);
    } catch {
        contenitore.innerHTML =
            '<p class="text-xs text-rose-400 p-4">Non riesco a leggere le automazioni: il server non ha risposto.</p>';
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
        const routine = (_allModesCache || [])
            .map(
                (m) =>
                    `<option value="${_testoSicuro(m.name || m.id)}">${_testoSicuro(m.name || m.id)}</option>`,
            )
            .join('');
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
            valore: leggi('scorciatoia-valore', ''),
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
            servizio: leggi('scorciatoia-servizio', 'turn_off'),
        };
    }
    return { tipo: 'avviso', testo: leggi('scorciatoia-testo', '') };
}

// Un nome scritto da noi e' meglio di «Nuova regola 3»: dice cosa fa,
// e chi la ritrova fra sei mesi non deve aprirla per ricordarselo.
function nomeDallaScorciatoia(innesco, azione) {
    const quando =
        {
            orario: `Alle ${innesco.ora || ''}`,
            alba: "All'alba",
            tramonto: 'Al tramonto',
            stato: `Quando ${innesco.entity_id || 'qualcosa'} cambia`,
            evento: `Su ${innesco.evento || 'un evento'}`,
        }[innesco.tipo] || 'Automazione';

    const cosa =
        {
            modalita: `avvia «${azione.modalita || ''}»`,
            dispositivo: `${azione.servizio === 'turn_on' ? 'accendi' : 'spegni'} ${azione.entity_id || ''}`,
            avviso: 'mandami un avviso',
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
                azioni: [azione],
            }),
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
    } catch {
        _mostraEsitoScorciatoia("Il server non ha risposto: l'automazione non e' stata creata.", false);
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

    const nodo = (_canvasState.nodes || []).find((n) => n.type === 'trigger');
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
            testo:
                'prossima volta ' +
                quando.toLocaleString('it-IT', { weekday: 'short', hour: '2-digit', minute: '2-digit' }),
            colore: 'text-emerald-400',
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
            .map((r) => String(r.origine || ''))
            .filter((o) => o.startsWith('grafo:'))
            .map((o) => o.slice('grafo:'.length)),
    );
    return (modi || []).filter((m) => !automatizzate.has(String(m.id)));
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

    pezzi.push(
        regole
            .map((r) => {
                const stato = quandoScatta(r);
                const dalGrafo = String(r.origine || '').startsWith('grafo:');
                const ultimo = r.ultimo_scatto
                    ? new Date(r.ultimo_scatto).toLocaleString('it-IT', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                      })
                    : null;
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
                    ${
                        dalGrafo
                            ? '<span class="text-[10px] text-slate-600 max-w-[7rem] leading-tight">Per toglierla, togli l\'innesco dalla routine</span>'
                            : `<button type="button" onclick="cancellaRegola('${r.id}')" class="p-1.5 text-slate-500 hover:text-rose-400" title="Elimina"><i data-lucide="trash-2" class="w-4 h-4"></i></button>`
                    }
                </div>
            </div>`;
            })
            .join(''),
    );

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
                    ${vocali
                        .map(
                            (m) => `
                        <div class="flex items-center justify-between gap-3 px-3 py-2 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div class="min-w-0">
                                <span class="text-xs font-semibold text-slate-200">${m.name || m.id}</span>
                                ${
                                    (m.trigger_phrases || []).length
                                        ? `<span class="text-[10px] text-slate-500 font-mono ml-2 truncate">"${(m.trigger_phrases || [])[0]}"</span>`
                                        : '<span class="text-[10px] text-amber-400 ml-2">senza frasi: non la puoi nemmeno chiamare</span>'
                                }
                            </div>
                            <button type="button" onclick="openModularModeBuilder('${m.id}')" class="shrink-0 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-semibold" title="Apre il disegno di questa routine">
                                Apri
                            </button>
                        </div>`,
                        )
                        .join('')}
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
        body: JSON.stringify({ attiva }),
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
