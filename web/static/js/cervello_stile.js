// Come si vede il grafo del Cervello: colori, dimensioni e limiti (issue #186).
//
// Stanno qui e non dentro il disegno perche' sono cio' che si cambia piu' spesso — un colore,
// la grandezza di un tipo di nodo — e non devono richiedere di rileggere trecento righe di
// canvas. E il disegno resta sotto le cinquecento righe che il frontend si e' dato.

// [tema scuro, tema chiaro]: sul chiaro i colori accesi sparirebbero.
export const COLORI = {
    stanze: ['#fbbf24', '#b45309'],
    routine: ['#a78bfa', '#6d28d9'],
    regole: ['#f472b6', '#be185d'],
    dispositivi: ['#38bdf8', '#0369a1'],
    alias: ['#67e8f9', '#0e7490'],
    strumenti: ['#34d399', '#047857'],
    agenti: ['#fb923c', '#c2410c'],
    conoscenza: ['#bef264', '#4d7c0f'],
};
export const PREDEFINITO = ['#94a3b8', '#475569'];

export const RAGGI = {
    stanza: 9,
    routine: 8,
    regola: 7,
    dispositivo: 6,
    alias: 4,
    strumento: 4,
    dominio: 7,
    agente: 9,
    argomento: 7,
    fatto: 3.5,
};

export const STATO = { fermo: '#f59e0b', non_raggiungibile: '#ef4444' };
export const ZOOM_MIN = 0.2;
export const ZOOM_MAX = 4;
export const SOGLIA_CLIC = 4;

export function movimentoRidotto() {
    try {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
        return false;
    }
}
