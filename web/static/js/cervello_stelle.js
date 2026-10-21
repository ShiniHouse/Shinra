// Il Cervello come una galassia (tavolozza Jarvis): i nodi sono stelle, i collegamenti fili di luce, gli impulsi corrono sui fili.
//
// Solo il disegno: la fisica, le selezioni, i clic e il registro sono quelli di sempre (`cervello_disegno.js`). Con un'altra
// tavolozza, o col tema chiaro, non si usa niente di questo e il grafo e' quello di prima.
//
// Costa poco e ferma quando deve:
//
//  - le stelle di fondo sono ferme, in coordinate di schermo e con un seme fisso: nessun fotogramma in piu';
//  - gli impulsi esistono **solo mentre un nodo e' acceso** (cioe' mentre Shinra lavora): il ciclo di disegno gira gia' per
//    quello e si ferma con lui; senza eventi non si anima niente;
//  - con il movimento ridotto non ci sono impulsi in corsa: restano i nodi accesi, fermi.

import { RAGGI } from './cervello_stile.js';

const stMassimoImpulsi = 40; // un grafo di centinaia di collegamenti non deve disegnare centinaia di puntini
const stSecondiPerCorsa = 1.1;
const stStelleDiFondo = 140;

export function eStellare() {
    const radice = document.documentElement;
    return radice.dataset.palette === 'jarvis' && !radice.classList.contains('light');
}

function stCasuale(seme) {
    let x = seme >>> 0;
    return () => {
        x = (x * 1664525 + 1013904223) >>> 0;
        return x / 4294967296;
    };
}

const stFondo = (() => {
    const r = stCasuale(20261021);
    return Array.from({ length: stStelleDiFondo }, () => ({
        x: r(),
        y: r(),
        luce: 0.15 + r() * 0.5,
        g: 0.4 + r() * 1.1,
    }));
})();

// Il cielo dietro al grafo, in pixel di schermo (prima della trasformazione della vista).
export function disegnaCielo(ctx, w, h) {
    const alone = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.6);
    alone.addColorStop(0, 'rgba(34, 211, 238, 0.08)');
    alone.addColorStop(1, 'rgba(34, 211, 238, 0)');
    ctx.fillStyle = alone;
    ctx.fillRect(0, 0, w, h);
    for (const s of stFondo) {
        ctx.fillStyle = `rgba(190, 225, 255, ${s.luce})`;
        ctx.fillRect(s.x * w, s.y * h, s.g, s.g);
    }
}

export function disegnaFili(ctx, { sim, attivo, cerca, k, visibile }) {
    for (const m of sim.molle) {
        if (!visibile(m.a) || !visibile(m.b)) continue;
        const evidenziato = attivo && (m.a.id === attivo || m.b.id === attivo);
        ctx.strokeStyle = evidenziato ? '#bdeefa' : '#4aa8c4';
        ctx.globalAlpha = evidenziato ? 0.85 : cerca ? 0.05 : 0.22;
        ctx.lineWidth = (evidenziato ? 1.5 : 0.7) / k;
        ctx.beginPath();
        ctx.moveTo(m.a.x, m.a.y);
        ctx.lineTo(m.b.x, m.b.y);
        ctx.stroke();
    }
    ctx.globalAlpha = 1;
}

// Una stella: un bagliore del colore del suo gruppo, e un nucleo bianco. Luce additiva: dove si sovrappongono si accendono.
export function disegnaStelle(ctx, { sim, k, visibile, corrisponde, colore, selezionata }) {
    ctx.globalCompositeOperation = 'lighter';
    for (const p of sim.punti) {
        if (!visibile(p)) continue;
        const r = RAGGI[p.nodo.tipo] || 5;
        const resta = corrisponde(p);
        const c = colore(p.nodo.cluster);
        const raggioBagliore = r * (selezionata(p) ? 6 : 4.2);
        const bagliore = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, raggioBagliore);
        bagliore.addColorStop(0, c);
        bagliore.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.globalAlpha = resta ? 0.5 : 0.07;
        ctx.fillStyle = bagliore;
        ctx.beginPath();
        ctx.arc(p.x, p.y, raggioBagliore, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = resta ? 1 : 0.15;
        ctx.fillStyle = c;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 0.7, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(p.x, p.y, Math.max(r * 0.28, 1 / k), 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
}

// Gli impulsi: un puntino di luce che corre da ogni nodo acceso lungo i suoi collegamenti, e lungo il percorso della richiesta.
// Mentre un nodo e' acceso ripete la corsa; quando si spegne, finisce con lui.
export function disegnaImpulsi(ctx, { sim, quadro, k, visibile, adesso, ridotto }) {
    if (ridotto) return;
    const t = adesso / 1000;
    let disegnati = 0;
    ctx.globalCompositeOperation = 'lighter';
    const impulso = (da, a, v, errore) => {
        if (disegnati >= stMassimoImpulsi) return;
        disegnati++;
        const q = (t / stSecondiPerCorsa + (da.x + da.y) * 0.013) % 1;
        const x = da.x + (a.x - da.x) * q;
        const y = da.y + (a.y - da.y) * q;
        const colore = errore ? '251, 113, 133' : '189, 238, 250';
        const alone = ctx.createRadialGradient(x, y, 0, x, y, 9 / k);
        alone.addColorStop(0, `rgba(${colore}, ${0.9 * v})`);
        alone.addColorStop(1, `rgba(${colore}, 0)`);
        ctx.fillStyle = alone;
        ctx.beginPath();
        ctx.arc(x, y, 9 / k, 0, Math.PI * 2);
        ctx.fill();
    };
    for (const m of sim.molle) {
        if (!visibile(m.a) || !visibile(m.b)) continue;
        const va = quadro.intensita(m.a.id, adesso, ridotto);
        const vb = quadro.intensita(m.b.id, adesso, ridotto);
        if (va <= 0 && vb <= 0) continue;
        // L'impulso parte dal nodo piu' acceso verso l'altro.
        if (va >= vb) impulso(m.a, m.b, va, quadro.errore(m.a.id, adesso));
        else impulso(m.b, m.a, vb, quadro.errore(m.b.id, adesso));
    }
    for (const [da, a, v] of quadro.segmenti(adesso, ridotto)) {
        const p = sim.perId.get(da);
        const q = sim.perId.get(a);
        if (p && q && visibile(p) && visibile(q)) impulso(p, q, v, quadro.errore(a, adesso));
    }
    ctx.globalCompositeOperation = 'source-over';
    ctx.globalAlpha = 1;
}
