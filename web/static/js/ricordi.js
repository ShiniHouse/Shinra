// ==================== I RICORDI (#250) ====================
// Cosa sa Shinra, di casa e di me: leggere, correggere sul posto, fissare, archiviare, eliminare. Ognuno vede **solo i propri**
// ricordi privati (ADR 0009): la regola la fa rispettare il server, questa pagina mostra cio' che il server le manda.
// Ogni testo passa da `_html`: un ricordo con dentro del markup resta testo, in elenco e in modifica.
import { Gesti } from './gesti.js';
import { _html } from './sicurezza.js';
import { safeCreateIcons } from './avvio.js';
import { getAuthHeaders } from './accesso.js';

let ambitoRicordi = 'casa';
let inModifica = null;
let ricordiVisti = [];

const ORIGINI = {
    manuale: 'scritto a mano',
    intervista: "imparato in un'intervista",
    conversazione: 'detto in conversazione',
    sogno: 'notato di notte',
    importato: 'importato',
};

function _messaggio(testo, errore = false) {
    const el = document.getElementById('ricordi-esito');
    if (!el) return;
    el.textContent = testo;
    el.className = `text-xs ${errore ? 'text-rose-400' : 'text-emerald-400'}`;
}

async function _detail(res) {
    const dati = await res.json().catch(() => ({}));
    return typeof dati.detail === 'string' ? dati.detail : `Errore ${res.status}`;
}

function _usi(r) {
    if (!r.usi) return 'mai usato';
    const quando = r.ultimo_uso ? new Date(r.ultimo_uso) : null;
    const giorni =
        quando && !Number.isNaN(quando.getTime())
            ? Math.floor((Date.now() - quando.getTime()) / 86400000)
            : null;
    const volte = r.usi === 1 ? 'usato 1 volta' : `usato ${r.usi} volte`;
    if (giorni === null) return volte;
    return giorni <= 0
        ? `${volte}, l'ultima oggi`
        : `${volte}, l'ultima ${giorni === 1 ? 'ieri' : `${giorni} giorni fa`}`;
}

function _stato(r) {
    if (r.stato === 'proposto')
        return _html`<span class="px-1.5 py-0.5 rounded bg-amber-500 text-slate-900 text-[10px] font-bold uppercase">proposto</span>`;
    if (r.stato === 'archiviato' || !r.attivo)
        return _html`<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-bold uppercase">archiviato</span>`;
    return '';
}

function _carta(r) {
    const modifica = inModifica === r.id;
    const azioni = modifica
        ? _html`
            <button data-gesto="salvaRicordo" data-testo="${r.id}" class="px-2.5 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Salva</button>
            <button data-gesto="annullaModificaRicordo" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">Annulla</button>`
        : _html`
            <button data-gesto="modificaRicordo" data-testo="${r.id}" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-100" title="Correggi"><i data-lucide="pencil" class="w-4 h-4"></i></button>
            <button data-gesto="fissaRicordo" data-testo="${r.id}" class="p-1.5 rounded-lg ${r.fissato ? 'text-amber-400' : 'text-slate-400 hover:text-slate-100'}" title="${r.fissato ? "Non fissare piu'" : 'Fissa: entra sempre'}"><i data-lucide="pin" class="w-4 h-4"></i></button>
            <button data-gesto="archiviaRicordo" data-testo="${r.id}" class="p-1.5 rounded-lg text-slate-400 hover:text-slate-100" title="${r.stato === 'archiviato' ? 'Riattiva' : "Archivia: non lo uso piu'"}"><i data-lucide="archive" class="w-4 h-4"></i></button>
            <button data-gesto="eliminaRicordo" data-testo="${r.id}" class="p-1.5 rounded-lg text-slate-400 hover:text-rose-400" title="Elimina"><i data-lucide="trash-2" class="w-4 h-4"></i></button>`;
    const corpo = modifica
        ? _html`<input type="text" id="ricordo-testo-${r.id}" maxlength="500" class="w-full min-w-0 bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200">`
        : _html`<p class="text-sm text-slate-200 leading-relaxed break-words">${r.testo}</p>`;
    return _html`
        <div class="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2" data-ricordo="${r.id}">
            <div class="flex items-center gap-2 flex-wrap">
                <span class="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 font-mono uppercase">${r.categoria}</span>
                ${_stato(r)}
                ${r.fissato ? _html`<span class="text-[10px] text-amber-400 font-semibold">fissato</span>` : ''}
            </div>
            ${corpo}
            <p class="text-[11px] text-slate-500">${ORIGINI[r.origine] || r.origine} · ${_usi(r)}</p>
            <div class="flex items-center gap-1 justify-end">${azioni}</div>
        </div>`;
}

function _vuoto() {
    return ambitoRicordi === 'casa'
        ? 'Shinra non sa ancora niente della casa. Compila una categoria qui sopra o aggiungi un fatto libero.'
        : 'Shinra non ricorda ancora niente di te. Scrivi qui sotto una cosa che vuoi che sappia: la vedrai solo tu.';
}

function _disegna() {
    const lista = document.getElementById('ricordi-lista');
    if (!lista) return;
    for (const a of ['casa', 'mio']) {
        const b = document.getElementById(`ricordi-ambito-${a}`);
        if (b)
            b.className = `px-3 py-1.5 rounded-lg text-xs font-semibold ${a === ambitoRicordi ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:text-white'}`;
    }
    const mio = document.getElementById('ricordi-mio');
    if (mio) mio.classList.toggle('hidden', ambitoRicordi !== 'mio');
    if (!ricordiVisti.length) {
        lista.innerHTML = _html`<p class="text-xs text-slate-500 py-3 text-center">${_vuoto()}</p>`;
    } else {
        lista.innerHTML = _html`${ricordiVisti.map(_carta)}`;
    }
    if (inModifica) {
        const campo = document.getElementById(`ricordo-testo-${inModifica}`);
        const r = ricordiVisti.find((x) => x.id === inModifica);
        // Il valore si assegna al campo, non si scrive nel markup: un testo con apici o markup resta testo.
        if (campo && r) {
            campo.value = r.testo;
            campo.focus();
        }
    }
    safeCreateIcons();
}

export async function caricaRicordi() {
    try {
        const res = await fetch(`/api/ricordi?ambito=${ambitoRicordi}`, { headers: getAuthHeaders() });
        if (!res.ok) {
            _messaggio(await _detail(res), true);
            return;
        }
        ricordiVisti = (await res.json()).ricordi;
        _disegna();
    } catch (err) {
        _messaggio(`Non riesco a leggere i ricordi: ${err.message}`, true);
    }
}

function scegliAmbitoRicordi(quale) {
    ambitoRicordi = quale === 'mio' ? 'mio' : 'casa';
    inModifica = null;
    _messaggio('');
    caricaRicordi();
}

function modificaRicordo(id) {
    inModifica = id;
    _disegna();
}

async function esportaRicordi() {
    const res = await fetch(`/api/ricordi/esporta?ambito=${ambitoRicordi}`, { headers: getAuthHeaders() });
    if (!res.ok) return _messaggio(await _detail(res), true);
    const file = new Blob([await res.text()], { type: 'text/markdown;charset=utf-8' });
    const indirizzo = URL.createObjectURL(file);
    const a = document.createElement('a');
    a.href = indirizzo;
    a.download = `memorie-${ambitoRicordi}.md`;
    a.click();
    URL.revokeObjectURL(indirizzo);
    _messaggio('Esportati. Il file contiene dati personali: tienilo al sicuro.');
}

// Il file letto resta qui finche' la persona non conferma o annulla: l'anteprima non scrive niente.
let fileDaImportare = null;

function _riga(testo, etichetta) {
    return _html`<li class="break-words"><span class="text-[10px] uppercase text-slate-500">${etichetta}</span> ${testo}</li>`;
}

function _anteprima(a) {
    const nuovi = a.nuovi.map((n) =>
        _riga(n.sospetto ? `${n.testo} (da confermare: sembra un ordine)` : n.testo, 'nuovo'),
    );
    const cambiati = a.modificati.map((m) =>
        _riga(
            `${m.prima.testo} → ${m.dopo.testo}${m.sospetto ? ' (da confermare: sembra un ordine)' : ''}`,
            'cambia',
        ),
    );
    const tolti = a.tolti.map((t) => _riga(t.testo, 'manca'));
    const vuota = !nuovi.length && !cambiati.length && !tolti.length;
    return _html`
        <p class="text-slate-200 text-sm font-semibold">Cosa cambierebbe</p>
        ${vuota ? _html`<p class="text-xs text-slate-400">Niente: il file e' uguale ai ricordi che hai.</p>` : ''}
        <ul class="space-y-1 text-xs text-slate-300">${nuovi}${cambiati}${tolti}</ul>
        ${
            tolti.length
                ? _html`<label class="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" id="ricordi-togli"> Archivia anche quelli che non sono nel file (non li cancello: li riattivi dopo)</label>`
                : ''
        }
        <div class="flex gap-2">
            ${vuota ? '' : _html`<button type="button" data-gesto="applicaImportazioneRicordi" class="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold">Applica</button>`}
            <button type="button" data-gesto="annullaImportazioneRicordi" class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold">Annulla</button>
        </div>`;
}

function _chiudiAnteprima() {
    fileDaImportare = null;
    const riquadro = document.getElementById('ricordi-anteprima');
    if (riquadro) {
        riquadro.classList.add('hidden');
        riquadro.innerHTML = '';
    }
    const campo = document.getElementById('ricordi-file');
    if (campo) campo.value = '';
}

async function leggiFileRicordi(evento) {
    const file = evento.target.files?.[0];
    if (!file) return;
    fileDaImportare = await file.text();
    const res = await fetch('/api/ricordi/importa/anteprima', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ ambito: ambitoRicordi, contenuto: fileDaImportare }),
    });
    if (!res.ok) {
        _chiudiAnteprima();
        return _messaggio(await _detail(res), true);
    }
    const riquadro = document.getElementById('ricordi-anteprima');
    riquadro.innerHTML = _anteprima(await res.json());
    riquadro.classList.remove('hidden');
    _messaggio('');
}

async function applicaImportazioneRicordi() {
    if (fileDaImportare === null) return;
    const res = await fetch('/api/ricordi/importa', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
            ambito: ambitoRicordi,
            contenuto: fileDaImportare,
            conferma: true,
            togli: Boolean(document.getElementById('ricordi-togli')?.checked),
        }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    const f = await res.json();
    _chiudiAnteprima();
    const attesa = f.da_confermare ? ` ${f.da_confermare} aspettano la tua conferma (sembrano ordini).` : '';
    _messaggio(`Fatto: ${f.nuovi} nuovi, ${f.modificati} corretti, ${f.archiviati} archiviati.${attesa}`);
    await caricaRicordi();
}

function annullaImportazioneRicordi() {
    _chiudiAnteprima();
    _messaggio('Annullato: non ho scritto niente.');
}

function annullaModificaRicordo() {
    inModifica = null;
    _disegna();
}

async function _cambia(id, campi, conferma) {
    const res = await fetch(`/api/ricordi/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(campi),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    inModifica = null;
    _messaggio(conferma);
    await caricaRicordi();
}

async function salvaRicordo(id) {
    const testo = (document.getElementById(`ricordo-testo-${id}`)?.value || '').trim();
    if (!testo) return _messaggio("Il ricordo non puo' essere vuoto.", true);
    await _cambia(id, { text: testo }, 'Ricordo corretto.');
}

async function fissaRicordo(id) {
    const r = ricordiVisti.find((x) => x.id === id);
    if (!r) return;
    await _cambia(
        id,
        { importanza: r.fissato ? 3 : 5 },
        r.fissato ? "Non e' piu' fissato." : "Fissato: entrera' sempre nelle risposte.",
    );
}

async function archiviaRicordo(id) {
    const r = ricordiVisti.find((x) => x.id === id);
    if (!r) return;
    const archiviato = r.stato === 'archiviato';
    await _cambia(
        id,
        { stato: archiviato ? 'attivo' : 'archiviato' },
        archiviato ? 'Riattivato.' : "Archiviato: Shinra non lo usa piu'.",
    );
}

async function eliminaRicordo(id) {
    if (!confirm("Eliminare questo ricordo? Non si puo' annullare.")) return;
    const res = await fetch(`/api/ricordi/${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    _messaggio('Ricordo eliminato.');
    await caricaRicordi();
}

async function aggiungiRicordo() {
    const campo = document.getElementById('ricordi-nuovo');
    const testo = (campo?.value || '').trim();
    if (!testo) return _messaggio('Scrivi cosa vuoi che Shinra ricordi.', true);
    const res = await fetch('/api/ricordi', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ testo, ambito: 'mio' }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    if (campo) campo.value = '';
    _messaggio('Ricordato: lo vedi solo tu.');
    await caricaRicordi();
}

async function dimenticaTuttoDiMe() {
    if (
        !confirm(
            "Cancellare TUTTI i ricordi privati che Shinra ha di te? Quelli della casa restano. Non si puo' annullare.",
        )
    )
        return;
    const res = await fetch('/api/ricordi/dimentica-tutto-di-me', {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ conferma: true }),
    });
    if (!res.ok) return _messaggio(await _detail(res), true);
    const { cancellati } = await res.json();
    _messaggio(
        cancellati === 1 ? 'Ho dimenticato 1 ricordo di te.' : `Ho dimenticato ${cancellati} ricordi di te.`,
    );
    await caricaRicordi();
}

Gesti.registra({
    scegliAmbitoRicordi,
    modificaRicordo,
    annullaModificaRicordo,
    salvaRicordo,
    fissaRicordo,
    archiviaRicordo,
    eliminaRicordo,
    aggiungiRicordo,
    dimenticaTuttoDiMe,
    esportaRicordi,
    leggiFileRicordi,
    applicaImportazioneRicordi,
    annullaImportazioneRicordi,
});
