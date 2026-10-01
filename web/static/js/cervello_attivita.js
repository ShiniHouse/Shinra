// Il grafo vivo: cosa sta facendo Shinra, nodo per nodo (issue #189).
//
// Il server racconta il ciclo dell'agente con eventi `agente.*` (#188): una richiesta,
// la conoscenza consultata, la skill scelta, il dispositivo comandato, la risposta,
// un errore. Ognuno porta gli id dei nodi del grafo toccati, e niente del contenuto.
// Qui quegli eventi diventano due cose che dicono la stessa cosa:
//
//  - **Un'accensione sul disegno**: il nodo si illumina e svanisce, i collegamenti
//    verso di lui pure, e il percorso della richiesta — dal modello alla skill al
//    dispositivo — si vede come una linea tratteggiata. Un errore invece resta rosso
//    molto piu' a lungo: sparire in quattro secondi vorrebbe dire non essersi
//    accorti che qualcosa non ha funzionato.
//  - **Un registro in chiaro**, con le stesse informazioni, accanto al grafo: per chi
//    non vede bene, per chi legge con un lettore di schermo, e per chi non ha fatto
//    in tempo a guardare.
//
// Il percorso NON e' un collegamento del grafo: un cavo del grafo dice una cosa che il
// sistema sa (un alias che nomina un dispositivo), il percorso dice cosa e' successo
// adesso. Per questo ha un altro tratto — tratteggiato — e dura pochi secondi.
//
// **Fermo se non succede niente.** Senza eventi non c'e' un timer, un fotogramma, un
// calcolo: la scadenza e' un solo `setTimeout` per volta, armato solo se qualcosa e'
// acceso. **Con il movimento ridotto** il nodo non svanisce: e' acceso o spento, e cambia
// solo colore.

import { _html } from './sicurezza.js';
import { movimentoRidotto } from './cervello_stile.js';

const DURATA_MS = 4000;
const DURATA_ERRORE_MS = 20000;
const SOGLIA = 0.03;
const MASSIMO_VOCI = 50;
const VOCI_MOSTRATE = 12;
const MASSIMO_PERCORSI = 8;

const ACCESO = ['#fde047', '#a16207'];
const ERRORE = '#ef4444';

const _ora = () => performance.now();

class Attivita {
    constructor() {
        this.nodi = new Map();
        this.percorsi = new Map();
        this.voci = [];
        this._ascoltatori = new Set();
        this._timer = 0;
    }

    alCambiare(funzione) {
        this._ascoltatori.add(funzione);
        return () => this._ascoltatori.delete(funzione);
    }

    _avvisa() {
        for (const f of this._ascoltatori) {
            try {
                f();
            } catch (errore) {
                console.error('Attivita:', errore);
            }
        }
    }

    // Un evento `agente.*` arrivato dal canale. Ritorna la voce di registro, o null se non e' nostro.
    registra(evento, adesso = _ora()) {
        const tipo = evento && evento.tipo;
        if (typeof tipo !== 'string' || !tipo.startsWith('agente.')) return null;
        const dati = evento.dati || {};
        const nodi = Array.isArray(dati.nodi) ? dati.nodi.filter((n) => typeof n === 'string') : [];
        const errore = tipo === 'agente.errore';
        const richiesta = String(dati.richiesta || '');

        if (tipo === 'agente.richiesta' && !nodi.length) this.percorsi.delete(richiesta);
        for (const id of nodi) this.nodi.set(id, { da: adesso, errore });

        // Il percorso: le tappe di una richiesta, nell'ordine in cui sono arrivate. Una tappa
        // puo' toccare piu' nodi insieme (i fatti consultati): sono in parallelo, non in fila.
        if (nodi.length && !errore) {
            const percorso = this.percorsi.get(richiesta) || { da: adesso, fasi: [] };
            const ultima = percorso.fasi[percorso.fasi.length - 1];
            if (!ultima || ultima.join() !== nodi.join()) percorso.fasi.push(nodi);
            percorso.da = adesso;
            this.percorsi.set(richiesta, percorso);
            while (this.percorsi.size > MASSIMO_PERCORSI)
                this.percorsi.delete(this.percorsi.keys().next().value);
        }

        const voce = {
            ora: new Date(),
            tipo,
            nodi,
            errore,
            richiesta,
            riuscito: dati.riuscito,
            motivo: dati.motivo || '',
            alModello: Boolean(dati.al_modello),
        };
        this.voci.unshift(voce);
        if (this.voci.length > MASSIMO_VOCI) this.voci.length = MASSIMO_VOCI;
        this._ricontrolla(adesso);
        return voce;
    }

    // Quanto e' acceso un nodo, da 0 a 1. `ridotto`: o tutto o niente.
    intensita(id, adesso = _ora(), ridotto = movimentoRidotto()) {
        const e = this.nodi.get(id);
        if (!e) return 0;
        const durata = e.errore ? DURATA_ERRORE_MS : DURATA_MS;
        const trascorso = adesso - e.da;
        if (trascorso >= durata) return 0;
        if (ridotto) return 1;
        // L'errore resta pieno per meta' del tempo, poi svanisce: si deve fare in tempo a leggerlo.
        const v = e.errore ? Math.min(1, 2 * (1 - trascorso / durata)) : 1 - trascorso / durata;
        return v < SOGLIA ? 0 : v;
    }

    errore(id, adesso = _ora()) {
        const e = this.nodi.get(id);
        return Boolean(e && e.errore && this.intensita(id, adesso) > 0);
    }

    accesa(adesso = _ora(), ridotto = movimentoRidotto()) {
        for (const id of this.nodi.keys()) if (this.intensita(id, adesso, ridotto) > 0) return true;
        return false;
    }

    // I tratti del percorso ancora visibili: [da, a, intensita del nodo di arrivo].
    segmenti(adesso = _ora(), ridotto = movimentoRidotto()) {
        const fuori = [];
        for (const { fasi } of this.percorsi.values()) {
            for (let i = 1; i < fasi.length; i++) {
                for (const b of fasi[i]) {
                    const v = this.intensita(b, adesso, ridotto);
                    if (v <= 0) continue;
                    for (const a of fasi[i - 1]) if (a !== b) fuori.push([a, b, v]);
                }
            }
        }
        return fuori;
    }

    // Toglie cio' che e' scaduto e arma l'unico timer che serve: quello della prossima scadenza.
    _ricontrolla(adesso = _ora()) {
        if (this._timer) clearTimeout(this._timer);
        this._timer = 0;
        let prossima = Infinity;
        for (const [id, e] of this.nodi) {
            const scade = e.da + (e.errore ? DURATA_ERRORE_MS : DURATA_MS);
            if (scade <= adesso) this.nodi.delete(id);
            else prossima = Math.min(prossima, scade);
        }
        for (const [chiave, p] of this.percorsi) {
            if (p.da + DURATA_ERRORE_MS <= adesso) this.percorsi.delete(chiave);
        }
        this._avvisa();
        if (Number.isFinite(prossima)) {
            this._timer = setTimeout(() => this._ricontrolla(), Math.max(prossima - adesso, 0) + 30);
        }
    }

    azzera() {
        if (this._timer) clearTimeout(this._timer);
        this._timer = 0;
        this.nodi.clear();
        this.percorsi.clear();
        this.voci.length = 0;
    }
}

export const attivita = new Attivita();

// ------------------------------------------------------------------ disegno

// Chiamata dal canvas dopo i nodi: aloni, collegamenti accesi e percorso.
export function disegnaAttivita(
    ctx,
    sim,
    quadro,
    { k, scuro, visibile, adesso = _ora(), ridotto = movimentoRidotto() },
) {
    // Quali nodi sono accesi, per chi non legge il canvas: un lettore di schermo e i test.
    const accesi = [...quadro.nodi.keys()].filter((id) => quadro.intensita(id, adesso, ridotto) > 0);
    ctx.canvas.dataset.nodiAccesi = accesi.join(' ');
    ctx.canvas.dataset.nodiInErrore = accesi.filter((id) => quadro.errore(id, adesso)).join(' ');
    if (!accesi.length) return;
    const acceso = ACCESO[scuro ? 0 : 1];
    const colore = (id) => (quadro.errore(id, adesso) ? ERRORE : acceso);
    const punto = (id) => {
        const p = sim.perId.get(id);
        return p && visibile(p) ? p : null;
    };

    // I collegamenti del grafo che toccano un nodo acceso.
    ctx.setLineDash([]);
    for (const m of sim.molle) {
        const v = Math.max(
            quadro.intensita(m.a.id, adesso, ridotto),
            quadro.intensita(m.b.id, adesso, ridotto),
        );
        if (v <= 0 || !visibile(m.a) || !visibile(m.b)) continue;
        ctx.globalAlpha = 0.85 * v;
        ctx.strokeStyle = quadro.errore(m.a.id, adesso) || quadro.errore(m.b.id, adesso) ? ERRORE : acceso;
        ctx.lineWidth = 2 / k;
        ctx.beginPath();
        ctx.moveTo(m.a.x, m.a.y);
        ctx.lineTo(m.b.x, m.b.y);
        ctx.stroke();
    }

    // Il percorso della richiesta: tratteggiato, con la punta verso dove va.
    for (const [da, a, v] of quadro.segmenti(adesso, ridotto)) {
        const p = punto(da);
        const q = punto(a);
        if (!p || !q) continue;
        ctx.globalAlpha = v;
        ctx.strokeStyle = colore(a);
        ctx.lineWidth = 2.5 / k;
        ctx.setLineDash([7 / k, 5 / k]);
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(q.x, q.y);
        ctx.stroke();
        ctx.setLineDash([]);
        const angolo = Math.atan2(q.y - p.y, q.x - p.x);
        const punta = 7 / k;
        const x = q.x - (Math.cos(angolo) * 10) / k;
        const y = q.y - (Math.sin(angolo) * 10) / k;
        ctx.fillStyle = colore(a);
        ctx.beginPath();
        ctx.moveTo(x + Math.cos(angolo) * punta, y + Math.sin(angolo) * punta);
        ctx.lineTo(x + Math.cos(angolo + 2.5) * punta, y + Math.sin(angolo + 2.5) * punta);
        ctx.lineTo(x + Math.cos(angolo - 2.5) * punta, y + Math.sin(angolo - 2.5) * punta);
        ctx.closePath();
        ctx.fill();
    }

    // Gli aloni dei nodi.
    for (const p of sim.punti) {
        const v = quadro.intensita(p.id, adesso, ridotto);
        if (v <= 0 || !visibile(p)) continue;
        const r = (p.nodo.tipo === 'fatto' ? 3.5 : 6) + 7 / k;
        ctx.globalAlpha = 0.3 * v;
        ctx.fillStyle = colore(p.id);
        ctx.beginPath();
        ctx.arc(p.x, p.y, r + 4 / k, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = v;
        ctx.strokeStyle = colore(p.id);
        ctx.lineWidth = 2.5 / k;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.stroke();
    }
    ctx.globalAlpha = 1;
}

// ------------------------------------------------------------------ registro

const CHIAVI = {
    'agente.richiesta': () => 'Richiesta ricevuta',
    'agente.conoscenza': (n) => `Conoscenza consultata: ${n}`,
    'agente.skill': (n) => `Strumento scelto: ${n}`,
    'agente.dispositivo': (n, v) =>
        `Dispositivo comandato: ${n}${v.riuscito === false ? ' (non riuscito)' : ''}`,
    'agente.risposta': (n) => (n ? `Risposta data da ${n}` : 'Risposta data'),
    'agente.errore': (n, v) => `Errore${v.motivo ? ` (${v.motivo})` : ''}${n ? `: ${n}` : ''}`,
};

// La frase di una voce. `nomeDi` traduce un id nel nome che si vede nel grafo.
function frase(voce, nomeDi = (id) => id) {
    if (voce.tipo === 'agente.richiesta' && voce.alModello) return 'Passata al modello';
    const come = CHIAVI[voce.tipo];
    if (!come) return voce.tipo;
    return come(voce.nodi.map(nomeDi).join(', '), voce);
}

const DUE = (n) => String(n).padStart(2, '0');

export function disegnaRegistro(el, voci, nomeDi) {
    if (!el) return;
    const mostrate = voci.slice(0, VOCI_MOSTRATE);
    if (!mostrate.length) {
        el.innerHTML = _html`<li class="text-slate-500">Quando Shinra lavora, qui compare cosa sta facendo.</li>`;
        return;
    }
    el.innerHTML = _html`${mostrate.map((v) => {
        const quando = `${DUE(v.ora.getHours())}:${DUE(v.ora.getMinutes())}:${DUE(v.ora.getSeconds())}`;
        return _html`<li class="${v.errore ? 'text-rose-300' : 'text-slate-300'}"><span class="text-slate-500 tabular-nums">${quando}</span> · ${frase(v, nomeDi)}</li>`;
    })}`;
}
