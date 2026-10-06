// Come ci si muove nel grafo: puntatore, rotella, tastiera (issue #186).
//
// Sta a parte perche' `Lavagna` (cervello_disegno.js) non superi le cinquecento righe: il disegno e lo
// stato stanno li', qui solo cosa fa ogni gesto. Le funzioni ricevono la lavagna e ne usano i metodi.

import { riscalda, vicinoVerso } from './cervello_fisica.js';
import { SOGLIA_CLIC } from './cervello_stile.js';

export function collega(lav) {
    const c = lav.canvas;
    lav._ascolta(c, 'pointerdown', (e) => {
        const { x, y } = lav._punto(e);
        const p = lav.nodoA(x, y);
        c.setPointerCapture?.(e.pointerId);
        lav._trascinando = {
            x,
            y,
            partitiDa: { x, y },
            nodo: p,
            vista: { ...lav.vista },
            mosso: false,
        };
        if (p) p.fisso = true;
    });
    lav._ascolta(c, 'pointermove', (e) => {
        const { x, y } = lav._punto(e);
        const t = lav._trascinando;
        if (!t) {
            const p = lav.nodoA(x, y);
            const id = p ? p.id : null;
            if (id !== lav.sopra) {
                lav.sopra = id;
                c.style.cursor = id ? 'pointer' : 'grab';
                lav.eventi.alSopra?.(p ? p.nodo : null, { x, y });
                lav.ridisegna();
            }
            return;
        }
        if (Math.hypot(x - t.partitiDa.x, y - t.partitiDa.y) > SOGLIA_CLIC) t.mosso = true;
        if (t.nodo && t.mosso) {
            t.nodo.x = (x - lav.vista.x) / lav.vista.k;
            t.nodo.y = (y - lav.vista.y) / lav.vista.k;
            if (!lav.fermo) riscalda(lav.sim, 0.3);
            lav.avvia();
        } else if (!t.nodo) {
            lav.vista.x = t.vista.x + (x - t.partitiDa.x);
            lav.vista.y = t.vista.y + (y - t.partitiDa.y);
            lav._vistaManuale = true;
        }
        lav.ridisegna();
    });
    const fine = () => {
        const t = lav._trascinando;
        lav._trascinando = null;
        if (!t) return;
        if (t.nodo) t.nodo.fisso = false;
        if (!t.mosso) lav.seleziona(t.nodo ? t.nodo.id : null);
    };
    lav._ascolta(c, 'pointerup', fine);
    lav._ascolta(c, 'pointercancel', fine);
    lav._ascolta(c, 'pointerleave', () => {
        if (lav.sopra) {
            lav.sopra = null;
            lav.eventi.alSopra?.(null);
            lav.ridisegna();
        }
    });
    lav._ascolta(c, 'dblclick', (e) => {
        const { x, y } = lav._punto(e);
        const p = lav.nodoA(x, y);
        if (p) lav.eventi.alApri?.(p.nodo);
    });
    lav._ascolta(
        c,
        'wheel',
        (e) => {
            e.preventDefault();
            const { x, y } = lav._punto(e);
            lav.zoom(Math.exp(-e.deltaY * 0.0015), x, y);
        },
        { passive: false },
    );
    lav._ascolta(c, 'keydown', (e) => tasto(lav, e));

    // Il tema cambia a pagina aperta: i colori si rileggono.
    const osservatore = new MutationObserver(() => lav.ridisegna());
    osservatore.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    lav._ascolti.push(() => osservatore.disconnect());
}

function tasto(lav, e) {
    if (!lav.sim) return;
    const direzioni = { ArrowUp: 'su', ArrowDown: 'giu', ArrowLeft: 'sinistra', ArrowRight: 'destra' };
    const corrente = lav.selezionato ? lav.sim.perId.get(lav.selezionato) : null;
    if (direzioni[e.key]) {
        e.preventDefault();
        const da = corrente || lav.sim.punti.find((p) => lav.visibile(p));
        if (!da) return;
        const prossimo = corrente ? vicinoVerso(lav.sim, da, direzioni[e.key], (p) => lav.visibile(p)) : da;
        if (prossimo) lav.seleziona(prossimo.id, { centra: true });
    } else if (e.key === 'Enter' && corrente) {
        e.preventDefault();
        lav.eventi.alApri?.(corrente.nodo);
    } else if (e.key === 'Escape') {
        lav.seleziona(null);
    } else if (e.key === '+' || e.key === '=') {
        lav.zoom(1.25);
    } else if (e.key === '-') {
        lav.zoom(0.8);
    } else if (e.key === 'Home' || e.key === '0') {
        lav.inquadra();
    }
}
