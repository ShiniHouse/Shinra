// La scheda «Il Cervello»: cosa sa e cosa fa la casa, come grafo (issue #186).
//
// Questo modulo e' il pezzo che sa di pagina: prende i _dati da `/api/cervello`,
// li affida al motore (`cervello_fisica.js`) e al canvas (`cervello_disegno.js`),
// e disegna intorno il resto — i contatori, lo stato dei sistemi, i filtri, la
// ricerca, il dettaglio di un nodo, l'elenco in chiaro.
//
// Due scelte sul comportamento:
//
//  - **Un clic seleziona, il doppio clic (o Invio) apre.** Aprire al primo clic
//    portava fuori dalla scheda ogni volta che si voleva solo guardare chi e'
//    collegato a cosa; la selezione mostra il dettaglio, con un pulsante «Apri».
//  - **Tutto si legge anche senza il canvas.** Sotto il grafo c'e' lo stesso
//    contenuto come elenco di pulsanti, uno per nodo: serve a chi usa la
//    tastiera o un lettore di schermo, e a chi vuole solo cercare un nome.
//
// I _dati arrivano dal server gia' decisi — quali nodi, quale stato, cosa nascondere
// a chi non ha il permesso. Qui non si calcola niente di cio' che ha un significato
// per la casa: si disegna.

import { Gesti } from './gesti.js';
import { _args, _html } from './sicurezza.js';
import { getAuthHeaders } from './accesso.js';
import { safeCreateIcons } from './avvio.js';
import { FORZE_PREDEFINITE, creaSimulazione } from './cervello_fisica.js';
import { Lavagna } from './cervello_disegno.js';
import { attivita, disegnaRegistro } from './cervello_attivita.js';

const MEMORIA = 'shinra.cervello';
const AGGIORNA_OGNI_MS = 30000;

const TIPI = {
    stanza: 'Stanza',
    dispositivo: 'Dispositivo',
    alias: 'Alias',
    routine: 'Routine',
    regola: 'Regola',
    argomento: 'Argomento',
    fatto: 'Voce di conoscenza',
    strumento: 'Strumento',
    dominio: 'Dominio degli strumenti',
    agente: 'Agente',
};

const STATI = {
    attivo: ['Attivo', 'text-emerald-400'],
    fermo: ['Fermo', 'text-amber-400'],
    non_raggiungibile: ['Non raggiungibile', 'text-rose-400'],
};

// Dove porta «Apri» per ogni tipo di nodo. Gli altri (strumenti, agenti) non hanno
// una scheda propria: mostrano il dettaglio e basta.
const APRI = {
    routine: (n) => Gesti.fai('openModularModeBuilder', n.id.slice('routine:'.length)),
    regola: () => Gesti.fai('switchTab', 'automazioni'),
    dispositivo: () => Gesti.fai('switchTab', 'aliases'),
    alias: () => Gesti.fai('switchTab', 'aliases'),
    stanza: () => Gesti.fai('switchTab', 'aliases'),
    argomento: () => Gesti.fai('switchTab', 'knowledge'),
    fatto: () => Gesti.fai('switchTab', 'knowledge'),
};

let lavagna = null;
let _dati = null;
let _orologio = 0;
let _osservatore = null;
let _tipiNascosti = new Set();
let _forzeScelte = { ...FORZE_PREDEFINITE };
let _nodoScelto = null;

const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ memoria
//
// `localStorage` non risponde sempre (finestra anonima, _dati bloccati): sono
// comodita', non _dati. Senza, la scheda si apre con le impostazioni di fabbrica.

function _leggiMemoria() {
    try {
        const grezzo = window.localStorage.getItem(MEMORIA);
        if (!grezzo) return;
        const salvato = JSON.parse(grezzo);
        _tipiNascosti = new Set(Array.isArray(salvato.nascosti) ? salvato.nascosti : []);
        _forzeScelte = {
            distanza: Number(salvato.distanza) || FORZE_PREDEFINITE.distanza,
            attrazione: Number.isFinite(Number(salvato.attrazione))
                ? Number(salvato.attrazione)
                : FORZE_PREDEFINITE.attrazione,
        };
    } catch {
        /* senza memoria si vive */
    }
}

function _scriviMemoria() {
    try {
        window.localStorage.setItem(
            MEMORIA,
            JSON.stringify({ nascosti: [..._tipiNascosti], ..._forzeScelte }),
        );
    } catch {
        /* idem */
    }
}

// ------------------------------------------------------------------ caricamento

export async function loadCervello({ silenzioso = false } = {}) {
    _leggiMemoria();
    _preparaLavagna();
    if (!silenzioso) _mostra('cervello-caricamento');
    try {
        const risposta = await fetch('/api/cervello', { headers: getAuthHeaders() });
        if (!risposta.ok) {
            const permesso = risposta.status === 401 || risposta.status === 403;
            _errore(
                permesso
                    ? 'Non hai il permesso di vedere il Cervello.'
                    : `Il server ha risposto ${risposta.status}.`,
            );
            return;
        }
        _dati = await risposta.json();
    } catch (errore) {
        console.error('loadCervello:', errore);
        _errore('Non riesco a raggiungere il server.');
        return;
    }
    _disegna();
    _programmaAggiornamento();
}

export function fermaCervello() {
    if (_orologio) window.clearInterval(_orologio);
    _orologio = 0;
}

function _programmaAggiornamento() {
    fermaCervello();
    // La scheda si rinnova da sola: un tablet appeso al muro non ha nessuno che prema «Aggiorna».
    _orologio = window.setInterval(() => {
        if (document.hidden || !$('tab-cervello') || $('tab-cervello').style.display === 'none') return;
        loadCervello({ silenzioso: true });
    }, AGGIORNA_OGNI_MS);
}

// ------------------------------------------------------------------ lavagna

function _preparaLavagna() {
    if (lavagna) return;
    const canvas = $('cervello-canvas');
    if (!canvas) return;
    lavagna = new Lavagna(canvas, {
        alSelezionare: _seleziona,
        alApri: _apri,
        alSopra: _suggerimento,
        attivita,
    });
    // Un evento dell'agente accende il grafo e scrive nel registro; a grafo spento non fa niente.
    attivita.alCambiare(() => {
        _registro();
        lavagna?.avvia();
    });
    const contenitore = $('cervello-contenitore');
    _osservatore = new ResizeObserver(() => _adatta());
    _osservatore.observe(contenitore);
    document.addEventListener('fullscreenchange', _alSchermoIntero);
    _adatta();
}

function _adatta() {
    const c = $('cervello-contenitore');
    if (!c || !lavagna) return;
    const { clientWidth, clientHeight } = c;
    if (clientWidth > 0 && clientHeight > 0) lavagna.adatta(clientWidth, clientHeight);
}

function _disegna() {
    const nodi = _dati.nodi || [];
    _contatori();
    _registro();
    _sistemi();
    _legenda();
    _elenco();
    _dettaglio(null);
    for (const [id, v] of [
        ['cervello-forza-distanza', _forzeScelte.distanza],
        ['cervello-forza-attrazione', _forzeScelte.attrazione],
    ]) {
        const campo = $(id);
        if (campo) campo.value = String(v);
    }
    _mostra(nodi.length ? null : 'cervello-vuoto');
    if (!nodi.length || !lavagna) {
        lavagna?.imposta(creaSimulazione([], [], []), [], []);
        return;
    }
    const { clientWidth: w, clientHeight: h } = $('cervello-contenitore');
    const nuova = creaSimulazione(nodi, _dati.collegamenti || [], _dati.clusters || [], {
        larghezza: w || 900,
        altezza: h || 600,
    });
    // Continuita': un aggiornamento non deve rimescolare il grafo. I nodi che c'erano
    // ripartono da dov'erano, con poca energia; solo i nuovi trovano il loro posto.
    const vecchia = lavagna.sim;
    let conservati = 0;
    if (vecchia) {
        for (const p of nuova.punti) {
            const prima = vecchia.perId.get(p.id);
            if (prima) {
                p.x = prima.x;
                p.y = prima.y;
                conservati++;
            }
        }
    }
    if (conservati > nuova.punti.length / 2) nuova.alfa = 0.25;
    lavagna.forze = { ..._forzeScelte };
    lavagna.nascosti = new Set(_tipiNascosti);
    lavagna.imposta(nuova, _dati.clusters || [], _dati.sistemi || []);
    if (_nodoScelto && nuova.perId.has(_nodoScelto)) lavagna.seleziona(_nodoScelto);
    $('cervello-canvas').setAttribute(
        'aria-label',
        `Grafo della casa: ${nodi.length} nodi e ${(_dati.collegamenti || []).length} collegamenti. ` +
            "Con le frecce ti sposti da un nodo all'altro, Invio apre, Esc deseleziona, più e meno ingrandiscono.",
    );
}

// ------------------------------------------------------------------ pannelli

function _mostra(quale) {
    for (const id of ['cervello-caricamento', 'cervello-vuoto', 'cervello-errore']) {
        const el = $(id);
        if (el) el.classList.toggle('hidden', id !== quale);
    }
}

function _errore(testo) {
    _mostra('cervello-errore');
    const el = $('cervello-errore-testo');
    if (el) el.textContent = testo;
}

function _nomeDelNodo(id) {
    return lavagna?.sim?.perId.get(id)?.nodo.nome || id.slice(id.indexOf(':') + 1);
}

function _registro() {
    disegnaRegistro($('cervello-registro'), attivita.voci, _nomeDelNodo);
}

function _contatori() {
    const c = _dati.contatori || {};
    const imposta = (id, valore) => {
        const el = $(id);
        if (el) el.textContent = String(valore);
    };
    imposta('cv-nodi', c.nodi ?? 0);
    imposta('cv-collegamenti', c.collegamenti ?? 0);
    imposta('cv-sistemi', `${c.sistemi_attivi ?? 0}/${c.sistemi ?? 0}`);
    imposta('cv-agenti', c.agenti_pronti ?? 0);
}

function _sistemi() {
    const el = $('cervello-sistemi');
    if (!el) return;
    const sistemi = _dati.sistemi || [];
    if (!sistemi.length) {
        el.innerHTML = _html`<li class="py-1.5 text-slate-500">Nessun sistema da mostrare.</li>`;
        return;
    }
    el.innerHTML = _html`${sistemi.map((s) => {
        const [etichetta, classe] = STATI[s.stato] || STATI.non_raggiungibile;
        return _html`<li class="flex items-start justify-between gap-2 py-1.5" title="${s.motivo || ''}">
            <span class="text-slate-200">${s.nome}</span>
            <span class="text-right ${classe}">${etichetta}${s.motivo ? _html`<span class="block text-[10px] font-normal text-slate-500">${s.motivo}</span>` : ''}</span>
        </li>`;
    })}`;
}

function _legenda() {
    const el = $('cervello-legenda');
    if (!el) return;
    const gruppi = _dati.clusters || [];
    if (!gruppi.length) {
        el.innerHTML = _html`<p class="text-slate-500">Quando la casa avrà qualcosa da mostrare, qui scegli cosa vedere.</p>`;
        return;
    }
    el.innerHTML = _html`${gruppi.map((c) => {
        const visibile = !_tipiNascosti.has(c.id);
        return _html`<label class="flex items-center justify-between gap-2 py-1 cursor-pointer">
            <span class="flex items-center gap-2 text-slate-200">
                <input type="checkbox" ${visibile ? 'checked' : ''} data-al-cambio="cervelloMostraTipo" data-args="${_args(c.id)}" data-argomento="spunta">
                ${c.nome}
            </span>
            <span class="text-slate-500">${c.nodi}${c.nascosti ? ` (+${c.nascosti})` : ''}</span>
        </label>`;
    })}`;
}

function _elenco() {
    const el = $('cervello-elenco');
    if (!el) return;
    const per = new Map();
    for (const n of _dati.nodi || []) {
        if (!per.has(n.cluster)) per.set(n.cluster, []);
        per.get(n.cluster).push(n);
    }
    const gruppi = _dati.clusters || [];
    if (!gruppi.length) {
        el.innerHTML = _html`<p class="text-slate-500">Nessun nodo: la casa non ha ancora niente da elencare.</p>`;
        return;
    }
    el.innerHTML = _html`${gruppi.map(
        (c) => _html`<div class="mb-3">
            <h4 class="text-[11px] uppercase tracking-wider text-slate-500 mb-1">${c.nome}</h4>
            <div class="flex flex-wrap gap-1.5">${(per.get(c.id) || []).map(
                (n) =>
                    _html`<button type="button" data-gesto="cervelloSeleziona" data-args="${_args(n.id)}" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px]">${n.nome}</button>`,
            )}</div>
        </div>`,
    )}`;
}

function _dettaglio(nodo) {
    const el = $('cervello-dettaglio');
    if (!el) return;
    if (!nodo) {
        el.innerHTML = _html`<p class="text-slate-500">Scegli un nodo: qui compare cosa e' e a cosa e' collegato.</p>`;
        return;
    }
    const vicini = [];
    for (const m of lavagna?.sim?.molle || []) {
        if (m.a.id === nodo.id) vicini.push(m.b.nodo);
        else if (m.b.id === nodo.id) vicini.push(m.a.nodo);
    }
    const stato = STATI[nodo.stato];
    el.innerHTML = _html`
        <p class="text-sm font-semibold text-slate-100">${nodo.nome}</p>
        <p class="text-slate-400">${TIPI[nodo.tipo] || nodo.tipo}${stato ? _html` · <span class="${stato[1]}">${stato[0]}</span>` : ''}</p>
        ${APRI[nodo.tipo] ? _html`<button type="button" data-gesto="cervelloApri" data-args="${_args(nodo.id)}" class="mt-2 px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Apri</button>` : ''}
        <h4 class="mt-3 text-[11px] uppercase tracking-wider text-slate-500">Collegato a (${vicini.length})</h4>
        <div class="flex flex-wrap gap-1.5 mt-1">${vicini
            .slice(0, 24)
            .map(
                (v) =>
                    _html`<button type="button" data-gesto="cervelloSeleziona" data-args="${_args(v.id)}" class="px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px]">${v.nome}</button>`,
            )}</div>`;
}

function _seleziona(nodo) {
    _nodoScelto = nodo ? nodo.id : null;
    _dettaglio(nodo);
    const annuncio = $('cervello-annuncio');
    if (annuncio)
        annuncio.textContent = nodo
            ? `${TIPI[nodo.tipo] || nodo.tipo}: ${nodo.nome}`
            : 'Nessun nodo selezionato';
}

function _suggerimento(nodo, punto) {
    const el = $('cervello-suggerimento');
    if (!el) return;
    if (!nodo) {
        el.classList.add('hidden');
        return;
    }
    el.textContent = `${nodo.nome} · ${TIPI[nodo.tipo] || nodo.tipo}`;
    el.style.left = `${(punto?.x ?? 0) + 12}px`;
    el.style.top = `${(punto?.y ?? 0) + 12}px`;
    el.classList.remove('hidden');
}

function _apri(nodo) {
    const azione = APRI[nodo.tipo];
    if (azione) azione(nodo);
}

// ------------------------------------------------------------------ gesti

function cervelloAggiorna() {
    loadCervello();
}

function cervelloCerca(testo) {
    lavagna?.impostaCerca(testo);
}

function cervelloMostraTipo(cluster, visibile) {
    if (visibile) _tipiNascosti.delete(cluster);
    else _tipiNascosti.add(cluster);
    _scriviMemoria();
    lavagna?.impostaNascosti(new Set(_tipiNascosti));
    lavagna?.inquadra();
}

function cervelloForza(nome, valore) {
    const numero = Number(valore);
    if (!Number.isFinite(numero)) return;
    _forzeScelte = { ..._forzeScelte, [nome]: numero };
    _scriviMemoria();
    lavagna?.impostaForze({ [nome]: numero });
}

function cervelloRipristina() {
    _forzeScelte = { ...FORZE_PREDEFINITE };
    _tipiNascosti = new Set();
    _scriviMemoria();
    for (const [id, v] of [
        ['cervello-forza-distanza', _forzeScelte.distanza],
        ['cervello-forza-attrazione', _forzeScelte.attrazione],
    ]) {
        const campo = $(id);
        if (campo) campo.value = String(v);
    }
    if (_dati) _legenda();
    lavagna?.impostaNascosti(new Set());
    lavagna?.impostaForze(_forzeScelte);
    lavagna?.inquadra();
}

function cervelloSeleziona(id) {
    lavagna?.seleziona(id, { centra: true });
}

function cervelloApri(id) {
    const p = lavagna?.sim?.perId.get(id);
    if (p) _apri(p.nodo);
}

function cervelloZoom(fattore) {
    lavagna?.zoom(Number(fattore) || 1);
}

function cervelloInquadra() {
    lavagna?.inquadra();
}

function cervelloSchermoIntero() {
    const scheda = $('tab-cervello');
    if (!scheda) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else scheda.requestFullscreen?.().catch((e) => console.warn('cervelloSchermoIntero:', e));
}

function _alSchermoIntero() {
    const scheda = $('tab-cervello');
    const intero = Boolean(document.fullscreenElement);
    if (!scheda) return;
    // In fullscreen un elemento ha lo sfondo del sistema: la scheda si da' il suo, e libera il pannello laterale.
    scheda.classList.toggle('bg-slate-950', intero);
    scheda.classList.toggle('p-4', intero);
    $('cervello-pannello')?.classList.toggle('hidden', intero);
    $('cervello-elenco-box')?.classList.toggle('hidden', intero);
    $('cervello-area')?.classList.toggle('lg:grid-cols-[1fr_20rem]', !intero);
    for (const id of ['cv-nodi', 'cv-collegamenti', 'cv-sistemi', 'cv-agenti']) {
        $(id)?.classList.toggle('text-4xl', intero);
    }
    const contenitore = $('cervello-contenitore');
    contenitore?.classList.toggle('h-[65vh]', !intero);
    contenitore?.classList.toggle('h-[calc(100vh-9rem)]', intero);
    _adatta();
    lavagna?.inquadra();
    safeCreateIcons();
}

Gesti.registra({
    cervelloAggiorna,
    cervelloApri,
    cervelloCerca,
    cervelloForza,
    cervelloInquadra,
    cervelloMostraTipo,
    cervelloRipristina,
    cervelloSchermoIntero,
    cervelloSeleziona,
    cervelloZoom,
});
