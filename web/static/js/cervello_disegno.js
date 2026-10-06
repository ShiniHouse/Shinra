// Il canvas del Cervello: disegna il grafo e ascolta mouse, dito e tastiera (issue #186).
//
// Non sa da dove vengono i dati e non apre niente: riceve una simulazione gia'
// disposta (`cervello_fisica.js`) e dice a chi lo usa cosa e' successo — un nodo
// selezionato, un nodo da aprire. Cosi' il disegno si puo' cambiare senza
// toccare cosa significa un clic.
//
// Tre cose che non si vedono e contano:
//
//  - **Il movimento si puo' non volere.** Chi chiede al sistema di ridurlo
//    (`prefers-reduced-motion`) riceve il grafo gia' disposto, fermo: nessuna
//    animazione di assestamento, e nessun fotogramma disegnato se niente cambia.
//  - **Disegna solo quando serve.** A grafo quieto e senza interazioni il ciclo
//    di disegno si ferma: un tablet appeso al muro non deve scaldarsi per
//    ridisegnare ogni sedicesimo di secondo la stessa immagine.
//  - **Tutto quello che si legge e' testo, mai markup.** Il canvas scrive con
//    `fillText`: un dispositivo chiamato `<img onerror=...>` e' una stringa
//    qualunque, e non c'e' nessun punto in cui diventi HTML.

import { FORZE_PREDEFINITE, centroDi, disponi, passo, quieta, riscalda } from './cervello_fisica.js';
import { COLORI, PREDEFINITO, RAGGI, STATO, ZOOM_MAX, ZOOM_MIN, movimentoRidotto } from './cervello_stile.js';
import { disegnaAttivita } from './cervello_attivita.js';
import { collega } from './cervello_interazione.js';

export class Lavagna {
    constructor(canvas, eventi = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.eventi = eventi;
        // Cosa sta facendo Shinra in questo momento (#189): se manca, il grafo e' quello di prima.
        this.attivita = eventi.attivita || null;
        this.sim = null;
        this.clusters = [];
        this.sistemi = [];
        this.vista = { x: 0, y: 0, k: 1 };
        this.dimensioni = { w: 900, h: 600, dpr: 1 };
        this.nascosti = new Set();
        this.cerca = '';
        this.selezionato = null;
        this.sopra = null;
        this.forze = { ...FORZE_PREDEFINITE };
        this.fermo = movimentoRidotto();
        this._frame = 0;
        this._passi = 0;
        // Se chi guarda ha mosso la vista (zoom, trascinamento) l'inquadratura
        // automatica smette: non si toglie la mappa di mano a chi la sta leggendo.
        this._vistaManuale = false;
        this._trascinando = null;
        this._ascolti = [];
        collega(this);
    }

    // ------------------------------------------------------------------ dati

    imposta(sim, clusters, sistemi) {
        this.sim = sim;
        this.clusters = clusters;
        this.sistemi = sistemi;
        // Se il nodo selezionato non c'e' piu' (un aggiornamento lo ha tolto) la selezione cade.
        if (this.selezionato && !sim.perId.has(this.selezionato)) this.selezionato = null;
        this._vistaManuale = false;
        this._passi = 0;
        if (this.fermo) disponi(sim, this.forze);
        this.inquadra();
        this.avvia();
    }

    adatta(w, h) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        this.dimensioni = { w, h, dpr };
        this.canvas.width = Math.round(w * dpr);
        this.canvas.height = Math.round(h * dpr);
        this.canvas.style.width = `${w}px`;
        this.canvas.style.height = `${h}px`;
        this.ridisegna();
    }

    visibile(p) {
        return !this.nascosti.has(p.nodo.cluster);
    }

    corrisponde(p) {
        if (!this.cerca) return true;
        return p.nodo.nome.toLowerCase().includes(this.cerca);
    }

    impostaNascosti(insieme) {
        this.nascosti = insieme;
        if (
            this.selezionato &&
            this.sim &&
            this.nascosti.has(this.sim.perId.get(this.selezionato)?.nodo.cluster)
        ) {
            this.seleziona(null);
        }
        this.ridisegna();
    }

    impostaCerca(testo) {
        this.cerca = (testo || '').trim().toLowerCase();
        this.ridisegna();
    }

    impostaForze(forze) {
        this.forze = { ...this.forze, ...forze };
        if (!this.sim) return;
        if (this.fermo) disponi(this.sim, this.forze);
        else riscalda(this.sim, 0.7);
        this.avvia();
    }

    // ------------------------------------------------------------- selezione

    seleziona(id, { centra = false } = {}) {
        this.selezionato = id;
        const p = id && this.sim ? this.sim.perId.get(id) : null;
        if (p && centra) {
            this.vista.x = this.dimensioni.w / 2 - p.x * this.vista.k;
            this.vista.y = this.dimensioni.h / 2 - p.y * this.vista.k;
        }
        this.eventi.alSelezionare?.(p ? p.nodo : null);
        this.ridisegna();
    }

    // Il nodo sotto un punto dello schermo, in pixel del canvas.
    nodoA(px, py) {
        if (!this.sim) return null;
        const x = (px - this.vista.x) / this.vista.k;
        const y = (py - this.vista.y) / this.vista.k;
        let trovato = null;
        let migliore = Infinity;
        for (const p of this.sim.punti) {
            if (!this.visibile(p)) continue;
            const raggio = (RAGGI[p.nodo.tipo] || 5) + 5 / this.vista.k;
            const d = Math.hypot(p.x - x, p.y - y);
            if (d <= raggio && d < migliore) {
                migliore = d;
                trovato = p;
            }
        }
        return trovato;
    }

    // ----------------------------------------------------------------- vista

    inquadra() {
        if (!this.sim) return;
        this._vistaManuale = false;
        let minX = Infinity;
        let minY = Infinity;
        let maxX = -Infinity;
        let maxY = -Infinity;
        for (const p of this.sim.punti) {
            if (!this.visibile(p)) continue;
            minX = Math.min(minX, p.x);
            maxX = Math.max(maxX, p.x);
            minY = Math.min(minY, p.y);
            maxY = Math.max(maxY, p.y);
        }
        if (!Number.isFinite(minX)) return;
        // I nomi dei cluster stanno sopra ai gruppi: in cima serve piu' spazio.
        minY -= 50;
        const margine = 60;
        const larghezza = Math.max(maxX - minX, 1) + margine * 2;
        const altezza = Math.max(maxY - minY, 1) + margine * 2;
        const k = Math.min(this.dimensioni.w / larghezza, this.dimensioni.h / altezza, 2);
        this.vista.k = Math.min(Math.max(k, ZOOM_MIN), ZOOM_MAX);
        this.vista.x = this.dimensioni.w / 2 - ((minX + maxX) / 2) * this.vista.k;
        this.vista.y = this.dimensioni.h / 2 - ((minY + maxY) / 2) * this.vista.k;
        this.ridisegna();
    }

    zoom(fattore, px = this.dimensioni.w / 2, py = this.dimensioni.h / 2) {
        const k = Math.min(Math.max(this.vista.k * fattore, ZOOM_MIN), ZOOM_MAX);
        const rapporto = k / this.vista.k;
        this.vista.x = px - (px - this.vista.x) * rapporto;
        this.vista.y = py - (py - this.vista.y) * rapporto;
        this.vista.k = k;
        this._vistaManuale = true;
        this.ridisegna();
    }

    // ------------------------------------------------------------- animazione

    // La scheda e' in primo piano? Un evento dell'agente che arriva a scheda chiusa non deve
    // far girare il disegno di una tela che nessuno vede (#187): quando la scheda si riapre
    // il grafo si ricarica e riparte da solo.
    _visibile() {
        return this.canvas.isConnected && this.canvas.offsetParent !== null;
    }

    avvia() {
        if (!this._visibile()) return;
        if (this.fermo) {
            this.canvas.dataset.animando = 'no';
            this.ridisegna();
            return;
        }
        if (this._frame) return;
        const ciclo = () => {
            this._frame = 0;
            if (!this.sim) return;
            if (!quieta(this.sim)) {
                // Piu' passi per fotogramma finche' il grafo e' lontano dalla quiete: si assesta in pochi secondi.
                const passi = this.sim.alfa > 0.3 ? 3 : 1;
                for (let i = 0; i < passi; i++) passo(this.sim, this.forze);
            }
            // Il grafo si allarga mentre si assesta: l'inquadratura lo segue, e si ferma con lui.
            this._passi++;
            if (!this._vistaManuale && (this._passi % 12 === 0 || quieta(this.sim))) this.inquadra();
            this.disegna();
            // Il ciclo gira finche' c'e' qualcosa che si muove o che e' acceso; poi si ferma del tutto.
            const continua = !quieta(this.sim) || this._trascinando || this.attivita?.accesa();
            if (continua) this._frame = requestAnimationFrame(ciclo);
            // Per chi guarda da fuori (i test): il ciclo di disegno e' fermo davvero?
            this.canvas.dataset.animando = continua ? 'si' : 'no';
        };
        this._frame = requestAnimationFrame(ciclo);
    }

    /**
     * La modalita' leggera (#187): il grafo si dispone in un colpo e poi sta fermo, come con il
     * movimento ridotto. Costa un calcolo solo, invece di decine di secondi di animazione a scatti
     * su un telefono; si puo' ancora selezionare, cercare e vedere accendersi i nodi.
     */
    impostaLeggera(leggera) {
        const fermo = Boolean(leggera) || movimentoRidotto();
        if (fermo === this.fermo) return;
        this.fermo = fermo;
        if (!this.sim) return;
        if (fermo) {
            if (this._frame) cancelAnimationFrame(this._frame);
            this._frame = 0;
            disponi(this.sim, this.forze);
            this.inquadra();
            this.canvas.dataset.animando = 'no';
            this.disegna();
        } else {
            riscalda(this.sim, 0.6);
            this.avvia();
        }
    }

    ridisegna() {
        if (this.fermo || !this._frame) this.disegna();
    }

    // ---------------------------------------------------------------- disegno

    _scuro() {
        return !document.documentElement.classList.contains('light');
    }

    _colore(cluster) {
        return (COLORI[cluster] || PREDEFINITO)[this._scuro() ? 0 : 1];
    }

    _statoDelCluster(id) {
        let peggiore = null;
        for (const s of this.sistemi) {
            if (s.cluster !== id) continue;
            if (s.stato === 'non_raggiungibile') return 'non_raggiungibile';
            if (s.stato === 'fermo') peggiore = 'fermo';
        }
        return peggiore;
    }

    disegna() {
        const { ctx, sim } = this;
        const { w, h, dpr } = this.dimensioni;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        if (!sim) return;

        // Quanti nodi si vedono davvero: lo legge chi non puo' leggere il canvas — un lettore
        // di schermo, e i test, che non sanno contare i cerchi di un'immagine.
        this.canvas.dataset.nodiVisibili = String(sim.punti.filter((p) => this.visibile(p)).length);

        const scuro = this._scuro();
        ctx.setTransform(
            dpr * this.vista.k,
            0,
            0,
            dpr * this.vista.k,
            dpr * this.vista.x,
            dpr * this.vista.y,
        );
        const k = this.vista.k;
        const attivo = this.sopra || this.selezionato;

        // Il nome di ogni cluster, scritto sopra al suo gruppo. Due gruppi vicini non devono
        // sovrapporre i nomi: ogni etichetta sale finche' non trova posto libero.
        const occupate = [];
        for (const c of this.clusters) {
            const centro = centroDi(sim, c.id, this.nascosti);
            if (!centro) continue;
            const stato = this._statoDelCluster(c.id);
            const testo = stato
                ? `${c.nome.toUpperCase()} · ${stato === 'fermo' ? 'FERMO' : 'NON RAGGIUNGIBILE'}`
                : c.nome.toUpperCase();
            ctx.font = `700 ${Math.min(Math.max(15 / k, 12), 40)}px system-ui, sans-serif`;
            ctx.textAlign = 'center';
            ctx.globalAlpha = stato ? 0.95 : 0.5;
            ctx.fillStyle = stato ? STATO[stato] : this._colore(c.id);
            const mezza = ctx.measureText(testo).width / 2;
            const altezza = Math.min(Math.max(15 / k, 12), 40) * 1.15;
            let y = centro.alto - 16 / k;
            for (let giro = 0; giro < 8; giro++) {
                const urta = occupate.some(
                    (o) => Math.abs(o.x - centro.x) < o.mezza + mezza && Math.abs(o.y - y) < altezza,
                );
                if (!urta) break;
                y -= altezza;
            }
            occupate.push({ x: centro.x, y, mezza });
            ctx.fillText(testo, centro.x, y);
        }
        ctx.globalAlpha = 1;

        // I collegamenti: sottili, e piu' marcati quelli del nodo in primo piano.
        for (const m of sim.molle) {
            if (!this.visibile(m.a) || !this.visibile(m.b)) continue;
            const evidenziato = attivo && (m.a.id === attivo || m.b.id === attivo);
            ctx.strokeStyle = scuro ? '#94a3b8' : '#475569';
            ctx.globalAlpha = evidenziato ? 0.9 : this.cerca ? 0.08 : 0.28;
            ctx.lineWidth = (evidenziato ? 1.8 : 0.9) / k;
            ctx.beginPath();
            ctx.moveTo(m.a.x, m.a.y);
            ctx.lineTo(m.b.x, m.b.y);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;

        // I nodi.
        for (const p of sim.punti) {
            if (!this.visibile(p)) continue;
            const r = RAGGI[p.nodo.tipo] || 5;
            const corrisponde = this.corrisponde(p);
            ctx.globalAlpha = corrisponde ? 1 : 0.18;
            ctx.fillStyle = this._colore(p.nodo.cluster);
            ctx.beginPath();
            ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
            ctx.fill();
            const stato = STATO[p.nodo.stato];
            if (stato) {
                ctx.strokeStyle = stato;
                ctx.lineWidth = 2 / k;
                ctx.stroke();
            }
            if (p.id === this.selezionato || p.id === this.sopra) {
                ctx.strokeStyle = scuro ? '#ffffff' : '#0f172a';
                ctx.lineWidth = 2.5 / k;
                ctx.beginPath();
                ctx.arc(p.x, p.y, r + 3 / k, 0, Math.PI * 2);
                ctx.stroke();
            }
        }
        ctx.globalAlpha = 1;
        if (this.attivita) {
            disegnaAttivita(ctx, sim, this.attivita, { k, scuro, visibile: (p) => this.visibile(p) });
        }

        // Le etichette dei nodi: tutte da vicino, solo quelle utili da lontano.
        ctx.textAlign = 'left';
        ctx.font = `${11 / k}px system-ui, sans-serif`;
        for (const p of sim.punti) {
            if (!this.visibile(p)) continue;
            const inPrimoPiano =
                p.id === this.selezionato ||
                p.id === this.sopra ||
                (this.cerca && this.corrisponde(p)) ||
                this.attivita?.intensita(p.id) > 0;
            if (!inPrimoPiano && k < 1.15) continue;
            if (!this.corrisponde(p)) continue;
            ctx.fillStyle = scuro ? '#e2e8f0' : '#0f172a';
            ctx.fillText(p.nodo.nome, p.x + (RAGGI[p.nodo.tipo] || 5) + 3 / k, p.y + 3.5 / k);
        }
    }

    // ------------------------------------------------------------ interazione

    _punto(evento) {
        const r = this.canvas.getBoundingClientRect();
        return { x: evento.clientX - r.left, y: evento.clientY - r.top };
    }

    _ascolta(bersaglio, tipo, funzione, opzioni) {
        bersaglio.addEventListener(tipo, funzione, opzioni);
        this._ascolti.push(() => bersaglio.removeEventListener(tipo, funzione, opzioni));
    }

    distruggi() {
        if (this._frame) cancelAnimationFrame(this._frame);
        this._frame = 0;
        this._ascolti.forEach((scollega) => scollega());
        this._ascolti = [];
    }
}
