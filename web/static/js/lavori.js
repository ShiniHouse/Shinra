// I lavori in background («ci penso», #431): cosa sta facendo Shinra per me, a che punto e', e come fermarlo.
//
// Sta nella scheda del Cervello, accanto a «Cosa sta facendo Shinra»: e' la stessa domanda, per le cose che prendono tempo. Il pannello compare
// solo se c'e' qualcosa da dire (un lavoro in corso o finito da poco) e sparisce da solo.
//
// Chiede `/api/lavori` quando si apre la scheda, quando arriva `lavoro.finito`, dopo una risposta «ci sto lavorando» e, finche' c'e' un lavoro in
// corso e la scheda e' in vista, ogni quattro secondi. Fermo se non c'e' niente in corso: nessun giro a vuoto.
//
// Tutto cio' che si legge e' testo: una richiesta con markup resta una stringa (`_html`).
import { Gesti } from './gesti.js';
import { _args, _html } from './sicurezza.js';
import { getAuthHeaders } from './accesso.js';

const OGNI_MS = 4000;
const DA_MOSTRARE = 5;
const ATTIVI = new Set(['in_coda', 'in_corso']);
const ETICHETTE = {
    in_coda: 'in coda',
    in_corso: 'ci sto lavorando',
    fatto: 'finito',
    fallito: 'non riuscito',
    annullato: 'annullato',
    interrotto: 'interrotto',
};

let lvAttivi = false;
let lvTimer = 0;

function lvInVista() {
    return !document.hidden && document.getElementById('tab-cervello')?.getClientRects().length > 0;
}

function lvRiga(l) {
    const attivo = ATTIVI.has(l.stato);
    const richiesta = String(l.richiesta || '').slice(0, 90);
    const avanzamento = Math.max(0, Math.min(100, Number(l.avanzamento) || 0));
    const dettaglio = attivo
        ? l.fase || ''
        : l.stato === 'fallito' || l.stato === 'interrotto'
          ? l.motivo || ''
          : '';
    return _html`<li class="py-2 space-y-1" data-lavoro="${l.id}" data-stato="${l.stato}">
        <div class="flex items-start justify-between gap-2">
            <span class="text-slate-200 break-words min-w-0">${richiesta}</span>
            ${attivo ? _html`<button type="button" data-gesto="annullaLavoro" data-args="${_args(l.id)}" class="shrink-0 text-[11px] text-rose-300 hover:text-rose-200 underline decoration-dotted">Annulla</button>` : ''}
        </div>
        <div class="flex items-center justify-between text-[11px] text-slate-500">
            <span>${ETICHETTE[l.stato] || l.stato}${dettaglio ? ` · ${dettaglio}` : ''}</span>
            ${attivo ? _html`<span class="font-mono">${avanzamento}%</span>` : ''}
        </div>
        ${attivo ? _html`<div class="h-1 bg-slate-800 rounded"><div class="h-1 bg-cyan-400 rounded" style="width:${avanzamento}%"></div></div>` : ''}
    </li>`;
}

function lvMostra(lavori) {
    const sezione = document.getElementById('cervello-lavori');
    const elenco = document.getElementById('cervello-lavori-elenco');
    if (!sezione || !elenco) return;
    // Un lavoro finito resta in vista finche' c'e' posto: i piu' recenti (il server li da' dal piu' nuovo), quelli in corso sempre.
    const recenti = lavori.filter((l) => ATTIVI.has(l.stato) || lavori.indexOf(l) < DA_MOSTRARE).slice(0, 20);
    lvAttivi = lavori.some((l) => ATTIVI.has(l.stato));
    sezione.hidden = recenti.length === 0;
    elenco.innerHTML = recenti.map(lvRiga).join('');
}

export async function aggiornaLavori() {
    if (!document.getElementById('cervello-lavori')) return;
    try {
        const res = await fetch('/api/lavori', { headers: getAuthHeaders() });
        if (!res.ok) return;
        lvMostra((await res.json()).lavori || []);
    } catch {
        // Niente di rotto da mostrare: il pannello resta com'e', e al prossimo giro riprova.
    }
}

async function annullaLavoro(id) {
    try {
        await fetch(`/api/lavori/${encodeURIComponent(id)}/annulla`, {
            method: 'POST',
            headers: getAuthHeaders(),
        });
    } finally {
        await aggiornaLavori();
    }
}

// Si guarda (senza rete) ogni secondo se c'e' un lavoro in corso e la scheda e' in vista; la richiesta parte ogni quattro secondi.
function lvCiclo() {
    if (!lvAttivi || !lvInVista()) return;
    if (Date.now() - lvTimer < OGNI_MS) return;
    lvTimer = Date.now();
    aggiornaLavori();
}
setInterval(lvCiclo, 1000);

Gesti.registra({
    annullaLavoro,
});
