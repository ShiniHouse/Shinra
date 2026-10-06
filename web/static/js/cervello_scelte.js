// Le scelte di chi guarda il grafo: cosa ricorda la scheda fra una visita e l'altra, e quando si accende la
// modalita' leggera (issue #187). `localStorage` non risponde sempre (finestra anonima, dati del sito bloccati): sono
// comodita', non dati. Senza, la scheda si apre con le impostazioni di fabbrica.
//
// `scelta` della modalita' leggera e' `null` se decide il numero dei nodi, `true`/`false` se ha scelto chi guarda:
// la sua parola vince sempre.

import { FORZE_PREDEFINITE } from './cervello_fisica.js';

const MEMORIA = 'shinra.cervello';

/** Quello che era stato salvato, o `null` se non c'e' niente (o non si legge). */
export function leggiMemoria() {
    try {
        const grezzo = window.localStorage.getItem(MEMORIA);
        if (!grezzo) return null;
        const salvato = JSON.parse(grezzo);
        return {
            nascosti: new Set(Array.isArray(salvato.nascosti) ? salvato.nascosti : []),
            forze: {
                distanza: Number(salvato.distanza) || FORZE_PREDEFINITE.distanza,
                attrazione: Number.isFinite(Number(salvato.attrazione))
                    ? Number(salvato.attrazione)
                    : FORZE_PREDEFINITE.attrazione,
            },
            // `null` = decide il numero dei nodi; `true`/`false` = ha scelto chi guarda.
            leggera: typeof salvato.leggera === 'boolean' ? salvato.leggera : null,
        };
    } catch {
        return null;
    }
}

export function scriviMemoria({ nascosti, forze, leggera }) {
    try {
        window.localStorage.setItem(MEMORIA, JSON.stringify({ nascosti: [...nascosti], leggera, ...forze }));
    } catch {
        /* senza memoria si vive */
    }
}

// Oltre questi nodi si accende da sola. Dalle misure: 600 nodi su una CPU sei volte piu' lenta di un portatile
// scendono a 25 fotogrammi al secondo, e 1000 a 12.
const SOGLIA_LEGGERA = 400;

export function inLeggera(scelta, quantiNodi) {
    return scelta === null ? quantiNodi > SOGLIA_LEGGERA : scelta;
}

export function notaLeggera(scelta, quantiNodi) {
    const attiva = inLeggera(scelta, quantiNodi);
    if (scelta === null) {
        return attiva
            ? `Accesa da sola: il grafo ha più di ${SOGLIA_LEGGERA} nodi.`
            : `Si accende da sola oltre ${SOGLIA_LEGGERA} nodi.`;
    }
    return attiva
        ? 'Scelta tua: il grafo si dispone una volta e sta fermo.'
        : "Scelta tua: l'animazione resta sempre accesa.";
}
