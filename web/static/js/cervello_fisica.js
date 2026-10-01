// Il layout del grafo del Cervello: un piccolo motore a forze (issue #186).
//
// Perche' non una libreria. La scheda e' vincolata a due cose: niente CDN — la
// casa non deve dipendere da internet per disegnarsi — e niente bundler (ADR
// 0006), quindi ogni libreria sarebbe un file di terzi copiato nel repository,
// da tenere aggiornato per un uso che qui occupa duecento righe. Quattro
// forze bastano per qualche centinaio di nodi:
//
//   - **repulsione**: due nodi si respingono, e a distanza si ignorano;
//   - **molle**: un collegamento tira i suoi estremi a una distanza di riposo;
//   - **ammasso**: ogni nodo e' attratto dal centro del *suo* cluster, ed e' cio'
//     che fa leggere il grafo come gruppi con un nome invece che come nebbia;
//   - **gravita'**: una spinta lieve verso il centro, perche' niente scappi.
//
// Questo modulo non tocca il DOM e non conosce il canvas: entrano nodi e
// collegamenti, escono posizioni. E' per questo che si prova con `node`.
//
// Deterministico apposta: le posizioni di partenza vengono dall'identificativo
// del nodo, non da `Math.random()`. Lo stesso grafo si dispone sempre allo
// stesso modo — una scheda che cambia faccia a ogni apertura non si impara — e
// un test puo' dire cosa succede.

export const FORZE_PREDEFINITE = {
    // La distanza di riposo di un collegamento, in pixel del grafo.
    distanza: 46,
    // Quanto i cluster tirano i loro nodi: 0 li scioglie, 1 li ammassa.
    attrazione: 0.5,
};

const RAGGIO_REPULSIONE = 220;
const FORZA_REPULSIONE = 520;
const ATTRITO = 0.82;
const DECADIMENTO = 0.985;
const SOGLIA_QUIETE = 0.012;

function _seme(testo) {
    // Un hash qualunque, purche' sempre lo stesso: FNV-1a su 32 bit.
    let h = 2166136261;
    for (let i = 0; i < testo.length; i++) {
        h ^= testo.charCodeAt(i);
        h = Math.imul(h, 16777619);
    }
    return ((h >>> 0) % 100000) / 100000;
}

/**
 * Prepara la simulazione. Le posizioni di partenza stanno attorno al centro del
 * cluster di ciascun nodo, e i centri su un'ellisse: cosi' il disegno nasce gia'
 * a gruppi e le forze devono solo rifinirlo.
 */
export function creaSimulazione(nodi, collegamenti, clusters, dimensioni = {}) {
    const larghezza = dimensioni.larghezza || 900;
    const altezza = dimensioni.altezza || 600;
    const centri = {};
    const quanti = Math.max(clusters.length, 1);
    clusters.forEach((c, i) => {
        const angolo = (2 * Math.PI * i) / quanti - Math.PI / 2;
        centri[c.id] = {
            x: larghezza / 2 + Math.cos(angolo) * larghezza * 0.36,
            y: altezza / 2 + Math.sin(angolo) * altezza * 0.36,
        };
    });

    const punti = nodi.map((nodo) => {
        const centro = centri[nodo.cluster] || { x: larghezza / 2, y: altezza / 2 };
        const raggio = 18 + _seme(nodo.id) * 70;
        const angolo = _seme(nodo.id + '#') * 2 * Math.PI;
        return {
            id: nodo.id,
            nodo,
            x: centro.x + Math.cos(angolo) * raggio,
            y: centro.y + Math.sin(angolo) * raggio,
            vx: 0,
            vy: 0,
            fisso: false,
        };
    });

    const perId = new Map(punti.map((p) => [p.id, p]));
    const molle = [];
    for (const c of collegamenti) {
        const a = perId.get(c.da);
        const b = perId.get(c.a);
        if (a && b) molle.push({ a, b, tipo: c.tipo });
    }
    return { punti, molle, centri, perId, larghezza, altezza, alfa: 1 };
}

/** Un passo di simulazione. Ritorna l'energia rimasta: sotto la soglia, il grafo e' fermo. */
export function passo(sim, forze = FORZE_PREDEFINITE) {
    const { punti, molle, centri } = sim;
    const alfa = sim.alfa;
    const n = punti.length;

    // Repulsione: ogni coppia, ma solo entro il raggio. Quadratica, e va bene
    // per qualche centinaio di nodi (il server ne manda al massimo 400).
    for (let i = 0; i < n; i++) {
        const a = punti[i];
        for (let j = i + 1; j < n; j++) {
            const b = punti[j];
            let dx = b.x - a.x;
            let dy = b.y - a.y;
            let d2 = dx * dx + dy * dy;
            if (d2 > RAGGIO_REPULSIONE * RAGGIO_REPULSIONE) continue;
            if (d2 < 0.01) {
                // Due nodi sullo stesso punto non hanno una direzione: se ne inventa una, ma sempre la stessa.
                dx = _seme(a.id + b.id) - 0.5;
                dy = _seme(b.id + a.id) - 0.5;
                d2 = dx * dx + dy * dy + 0.01;
            }
            const d = Math.sqrt(d2);
            const f = (FORZA_REPULSIONE * alfa) / d2;
            const fx = (dx / d) * f;
            const fy = (dy / d) * f;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
        }
    }

    // Molle: un collegamento tira (o spinge) verso la sua lunghezza di riposo.
    for (const m of molle) {
        const dx = m.b.x - m.a.x;
        const dy = m.b.y - m.a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const f = ((d - forze.distanza) / d) * 0.06 * alfa;
        m.a.vx += dx * f;
        m.a.vy += dy * f;
        m.b.vx -= dx * f;
        m.b.vy -= dy * f;
    }

    // Ammasso e gravita'.
    const cx = sim.larghezza / 2;
    const cy = sim.altezza / 2;
    for (const p of punti) {
        const centro = centri[p.nodo.cluster];
        if (centro) {
            p.vx += (centro.x - p.x) * 0.12 * forze.attrazione * alfa;
            p.vy += (centro.y - p.y) * 0.12 * forze.attrazione * alfa;
        }
        p.vx += (cx - p.x) * 0.004 * alfa;
        p.vy += (cy - p.y) * 0.004 * alfa;
    }

    // Integrazione. Un nodo fisso — quello che si sta trascinando — non si muove.
    for (const p of punti) {
        if (p.fisso) {
            p.vx = 0;
            p.vy = 0;
            continue;
        }
        p.vx *= ATTRITO;
        p.vy *= ATTRITO;
        p.x += p.vx;
        p.y += p.vy;
    }

    sim.alfa = Math.max(alfa * DECADIMENTO, 0);
    return sim.alfa;
}

export function quieta(sim) {
    return sim.alfa < SOGLIA_QUIETE;
}

/** Rimette energia nel sistema: dopo un trascinamento, o quando cambiano le forze. */
export function riscalda(sim, quanto = 0.6) {
    sim.alfa = Math.max(sim.alfa, quanto);
}

/** Corre fino alla quiete. Serve a chi chiede di non vedere il movimento: il grafo nasce gia' disposto. */
export function disponi(sim, forze = FORZE_PREDEFINITE, massimoPassi = 420) {
    for (let i = 0; i < massimoPassi && !quieta(sim); i++) passo(sim, forze);
    return sim;
}

/** Il centro dei nodi di un cluster e il suo punto piu' alto, per scrivere il nome sopra il gruppo. */
export function centroDi(sim, idCluster, nascosti = new Set()) {
    let somma = 0;
    let x = 0;
    let y = 0;
    let alto = Infinity;
    for (const p of sim.punti) {
        if (p.nodo.cluster !== idCluster || nascosti.has(idCluster)) continue;
        x += p.x;
        y += p.y;
        alto = Math.min(alto, p.y);
        somma++;
    }
    return somma ? { x: x / somma, y: y / somma, alto, quanti: somma } : null;
}

/**
 * Il nodo piu' vicino a `da` nella direzione data ('su', 'giu', 'sinistra', 'destra'),
 * per muoversi fra i nodi con le frecce. Ritorna `null` se in quella direzione non c'e' niente.
 *
 * Si sceglie nel cono di 45 gradi per lato: un nodo quasi dietro un altro non e'
 * «a destra» solo perche' e' un pelo piu' a destra.
 */
export function vicinoVerso(sim, da, direzione, visibili = () => true) {
    const versi = { su: [0, -1], giu: [0, 1], sinistra: [-1, 0], destra: [1, 0] };
    const verso = versi[direzione];
    if (!verso) return null;
    let migliore = null;
    let distanzaMigliore = Infinity;
    for (const p of sim.punti) {
        if (p === da || !visibili(p)) continue;
        const dx = p.x - da.x;
        const dy = p.y - da.y;
        const lungo = dx * verso[0] + dy * verso[1];
        const di_lato = Math.abs(dx * verso[1] + dy * verso[0]);
        if (lungo <= 0 || di_lato > lungo) continue;
        const d = Math.hypot(dx, dy);
        if (d < distanzaMigliore) {
            distanzaMigliore = d;
            migliore = p;
        }
    }
    return migliore;
}
