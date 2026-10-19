// ==================== IL SOGNO (#263) ====================
// Cosa Shinra ha notato di notte e propone: le abitudini, contate dal codice nel registro, con le prove. Nessuna proposta
// cambia qualcosa in casa da sola: «Si'» crea al piu' una regola SPENTA, che si accende da Routine. Le vedi solo tu.
// Ogni testo passa da `_html`: un nome di dispositivo con dentro del markup resta testo.
import { Gesti } from './gesti.js';
import { _args, _html } from './sicurezza.js';
import { getAuthHeaders } from './accesso.js';
import { caricaRicordi } from './ricordi.js';

let proposteViste = [];

const VERBI = { turn_on: 'accendi', turn_off: 'spegni', toggle: 'commuta' };

function _messaggio(testo, errore = false) {
    const el = document.getElementById('sogno-esito');
    if (!el) return;
    el.textContent = testo;
    el.className = `text-xs ${errore ? 'text-rose-400' : 'text-emerald-400'}`;
}

async function _detail(res) {
    const dati = await res.json().catch(() => ({}));
    return typeof dati.detail === 'string' ? dati.detail : `Errore ${res.status}`;
}

function _giorno(iso) {
    const d = new Date(`${iso}T12:00:00`);
    return Number.isNaN(d.getTime())
        ? iso
        : d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
}

function _frase(p) {
    const d = p.dati || {};
    const verbo = VERBI[d.verbo] || d.verbo || 'usi';
    return `Alle ${d.orario} ${verbo} spesso ${d.bersaglio}: lo hai fatto ${(d.giorni || []).length} giorni negli ultimi quattordici.`;
}

function _coppia(p) {
    const doppio = p.tipo === 'ricordo_doppio';
    const intro = doppio
        ? 'Questi due ricordi dicono quasi la stessa cosa. Quale tengo?'
        : "Questi due ricordi sembrano in contraddizione (cambia un numero). Quale e' giusto?";
    const scelte = (p.dati?.ricordi || []).map(
        (r) => _html`
            <div class="p-2 rounded-lg bg-slate-950/40 border border-slate-800 space-y-1.5">
                <p class="text-sm text-slate-200 break-words">${r.testo}</p>
                <button data-gesto="tieniRicordoDellaProposta" data-args="${_args(p.id, r.id)}" class="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Tieni questo</button>
            </div>`,
    );
    return _html`
        <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 md:col-span-2" data-proposta="${p.id}">
            <p class="text-sm text-slate-300">${intro}</p>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-2">${scelte}</div>
            <p class="text-[11px] text-slate-500">L'altro non lo cancello: lo archivio, e lo puoi riattivare dai ricordi.</p>
            <div class="flex justify-end">
                <button data-gesto="scartaProposta" data-testo="${p.id}" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">Lasciali cosi'</button>
            </div>
        </div>`;
}

function _carta(p) {
    if (p.tipo === 'ricordo_doppio' || p.tipo === 'ricordo_contraddittorio') return _coppia(p);
    const prove = (p.dati?.giorni || []).map(_giorno).join(', ');
    return _html`
        <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2" data-proposta="${p.id}">
            <p class="text-sm text-slate-200 leading-relaxed break-words">${_frase(p)}</p>
            <p class="text-[11px] text-slate-500">Visto il: ${prove}</p>
            <div class="flex items-center gap-2 justify-end">
                <button data-gesto="scartaProposta" data-testo="${p.id}" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">No, grazie</button>
                <button data-gesto="accettaProposta" data-testo="${p.id}" class="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Prepara la regola</button>
            </div>
        </div>`;
}

function _disegna() {
    const lista = document.getElementById('sogno-lista');
    if (!lista) return;
    if (!proposteViste.length) {
        lista.innerHTML = _html`<p class="text-xs text-slate-500 py-3 text-center">Stanotte non ho notato niente che valga la pena di proporti.</p>`;
        return;
    }
    lista.innerHTML = _html`${proposteViste.map(_carta)}`;
}

export async function caricaSogno() {
    try {
        const res = await fetch('/api/sogno/proposte', { headers: getAuthHeaders() });
        if (!res.ok) {
            _messaggio(await _detail(res), true);
            return;
        }
        proposteViste = (await res.json()).proposte;
        _disegna();
    } catch (err) {
        _messaggio(`Non riesco a leggere le proposte: ${err.message}`, true);
    }
}

async function _rispondi(id, accetta) {
    const base = `/api/sogno/proposte/${encodeURIComponent(id)}`;
    const res = await fetch(accetta ? `${base}/accetta` : `${base}/scarta`, {
        method: 'POST',
        headers: getAuthHeaders(),
    });
    if (!res.ok) {
        _messaggio(await _detail(res), true);
        return null;
    }
    return res.json();
}

async function scartaProposta(id) {
    if (!(await _rispondi(id, false))) return;
    _messaggio("Va bene: non te lo riproporro'.");
    await caricaSogno();
}

async function accettaProposta(id) {
    const esito = await _rispondi(id, true);
    if (!esito) return;
    _messaggio(
        esito.regola
            ? "Ho preparato la regola, ma e' SPENTA: la trovi in Routine, dove la accendi quando vuoi."
            : "L'ho segnata. Questa non so scriverla come regola: la tengo solo come nota.",
    );
    await caricaSogno();
}

async function tieniRicordoDellaProposta(idProposta, idRicordo) {
    const res = await fetch(`/api/sogno/proposte/${encodeURIComponent(idProposta)}/accetta`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ tieni: idRicordo }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    _messaggio("Fatto: ne tengo uno e l'altro e' archiviato.");
    await caricaSogno();
    caricaRicordi();
}

Gesti.registra({
    scartaProposta,
    accettaProposta,
    tieniRicordoDellaProposta,
});
