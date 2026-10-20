// Il nucleo di Shinra: una galassia che gira e batte quando Shinra pensa, ascolta e parla.
//
// Sta sopra la conversazione, nella tavolozza «Jarvis». Non sa cosa si dice: riceve uno **stato** (`standby`, `ascolto`,
// `elaboro`, `parlo`) e, mentre Shinra parla, degli **impulsi** — veri, dall'audio che sta suonando, oppure sintetici quando la
// voce e' quella del browser e non si puo' misurare. Ogni impulso e' un'onda che parte dal centro e corre verso il bordo.
//
// Quattro garanzie, come per il grafo del Cervello:
//
//  - **Il movimento si puo' non volere.** Con `prefers-reduced-motion` il nucleo e' una sola immagine ferma, che cambia di
//    colore con lo stato ma non gira ne' pulsa.
//  - **Disegna solo se si vede.** Scheda in secondo piano, pagina nascosta o tela fuori schermo: nessun fotogramma. Un tablet
//    appeso al muro non deve scaldarsi per una galassia che nessuno guarda.
//  - **Costa poco.** Poche centinaia di punti, la risoluzione del pannello (mai oltre 2x), e meno punti su un telefono.
//  - **Niente di cio' che si dice entra qui.** Solo stati e numeri: nessun testo di una conversazione arriva a questo modulo.

const STATI = {
    standby: { scritta: 'STANDBY', colore: [34, 211, 238], giro: 0.12, battito: 0.0 },
    ascolto: { scritta: 'ASCOLTO', colore: [251, 191, 36], giro: 0.2, battito: 0.55 },
    elaboro: { scritta: 'ELABORO', colore: [125, 211, 252], giro: 1.1, battito: 0.25 },
    parlo: { scritta: 'PARLO', colore: [103, 232, 249], giro: 0.28, battito: 0.0 },
};

// Gli stati di `updateLivingCoreState` (accesso.js) e i loro nomi qui.
const DA_STATO_DEL_NUCLEO = { idle: 'standby', listening: 'ascolto', thinking: 'elaboro', speaking: 'parlo' };

const PUNTI_DESKTOP = 340;
const PUNTI_TELEFONO = 170;
const BRACCI = 3;
const TACCHE = 72;

let nuTela = null;
let nuCtx = null;
let nuEtichetta = null;
let nuStato = 'standby';
let nuPunti = [];
let nuOnde = [];
let nuFrame = 0;
let nuUltimo = 0;
let nuFase = 0; // quanto e' ruotata la galassia
let nuLivello = 0; // l'intensita' dell'impulso, 0..1, che decade da sola
let nuColore = [...STATI.standby.colore];
let nuDim = { w: 600, h: 240, dpr: 1 };
let nuVisibile = true;
let nuOss = null;
let nuAnalizzatore = null;
let nuDati = null;
let nuSintetico = 0; // un orologio che finge un parlato, se non si puo' misurare quello vero

function _ridotto() {
    try {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch {
        return false;
    }
}

function _casuale(seme) {
    // Un generatore ripetibile: la galassia ha la stessa forma a ogni caricamento, e i test possono contarla.
    let x = seme >>> 0;
    return () => {
        x = (x * 1664525 + 1013904223) >>> 0;
        return x / 4294967296;
    };
}

function _creaPunti(quanti) {
    const r = _casuale(20261020);
    const nuovi = [];
    for (let i = 0; i < quanti; i++) {
        const braccio = i % BRACCI;
        const t = Math.pow(r(), 0.7); // piu' punti verso il centro
        const raggio = 0.08 + t * 0.92;
        const angolo = (braccio / BRACCI) * Math.PI * 2 + raggio * 3.4 + (r() - 0.5) * (0.5 + raggio * 0.6);
        nuovi.push({
            raggio,
            angolo,
            // le stelle vicine al centro girano piu' in fretta, come in una galassia vera
            velocita: 0.35 + (1 - raggio) * 0.9,
            grandezza: 0.5 + r() * 1.7,
            luce: 0.35 + r() * 0.65,
            tremolio: r() * Math.PI * 2,
            nebbia: i % 7 === 0,
        });
    }
    return nuovi;
}

function _adatta() {
    if (!nuTela) return;
    const r = nuTela.getBoundingClientRect();
    const w = Math.max(160, Math.round(r.width || 600));
    const h = Math.max(120, Math.round(r.height || 240));
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    nuDim = { w, h, dpr };
    nuTela.width = Math.round(w * dpr);
    nuTela.height = Math.round(h * dpr);
    nuPunti = _creaPunti(w < 480 ? PUNTI_TELEFONO : PUNTI_DESKTOP);
    disegna(0);
}

function _livelloAudio() {
    if (nuAnalizzatore && nuDati) {
        nuAnalizzatore.getByteFrequencyData(nuDati);
        let somma = 0;
        for (let i = 0; i < nuDati.length; i++) somma += nuDati[i];
        return Math.min(1, somma / nuDati.length / 110);
    }
    return null;
}

function _emettiOnda(forza) {
    if (nuOnde.length > 8) nuOnde.shift();
    nuOnde.push({ eta: 0, forza: Math.min(1, Math.max(0.15, forza)) });
}

/** Un impulso: un'onda dal centro. Mentre Shinra parla lo chiamano l'audio e le pause del parlato. */
export function impulso(forza = 1) {
    nuLivello = Math.min(1, Math.max(nuLivello, forza));
    _emettiOnda(forza);
    _avvia();
}

/** Lo stato di Shinra, con i nomi di `updateLivingCoreState` (`idle`, `listening`, `thinking`, `speaking`). */
export function impostaStato(nome) {
    const nuovo = DA_STATO_DEL_NUCLEO[nome] || (STATI[nome] ? nome : 'standby');
    if (nuovo === nuStato) return;
    nuStato = nuovo;
    if (nuTela) nuTela.dataset.stato = nuStato;
    if (nuEtichetta) nuEtichetta.textContent = STATI[nuStato].scritta;
    if (nuStato !== 'parlo') {
        nuAnalizzatore = null;
        nuDati = null;
    }
    if (nuStato === 'parlo') impulso(0.9);
    _avvia();
}

/**
 * Collega l'audio che sta suonando: il nucleo batte con la voce vera. Se il browser non lo permette (o l'audio non e'
 * un elemento che si puo' misurare) non fa niente, e lo stato `parlo` batte con un ritmo sintetico.
 */
export function collegaAudio(elemento) {
    try {
        const Contesto = window.AudioContext || window.webkitAudioContext;
        if (!Contesto || !elemento) return false;
        const contesto = new Contesto();
        const sorgente = contesto.createMediaElementSource(elemento);
        const nodo = contesto.createAnalyser();
        nodo.fftSize = 64;
        sorgente.connect(nodo);
        nodo.connect(contesto.destination);
        nuAnalizzatore = nodo;
        nuDati = new Uint8Array(nodo.frequencyBinCount);
        elemento.addEventListener(
            'ended',
            () => {
                nuAnalizzatore = null;
                nuDati = null;
                contesto.close().catch(() => {});
            },
            { once: true },
        );
        return true;
    } catch {
        return false;
    }
}

function _colore(verso, dt) {
    const k = Math.min(1, dt * 4);
    for (let i = 0; i < 3; i++) nuColore[i] += (verso[i] - nuColore[i]) * k;
}

function _rgba(a) {
    return `rgba(${Math.round(nuColore[0])}, ${Math.round(nuColore[1])}, ${Math.round(nuColore[2])}, ${a})`;
}

function disegna(dt) {
    if (!nuCtx) return;
    const { w, h, dpr } = nuDim;
    const config = STATI[nuStato];
    nuCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    nuCtx.clearRect(0, 0, w, h);
    const cx = w / 2;
    const cy = h / 2;
    const schiacciamento = 0.46; // la galassia vista di taglio, inclinata
    // Sta tutta nel riquadro, in larghezza e in altezza: l'ellisse non si taglia ne' sopra ne' sotto.
    const raggio = Math.min(w * 0.48, (h * 0.5 * 0.9) / schiacciamento);

    // L'alone dietro a tutto: respira con l'impulso.
    const grande = nuCtx.createRadialGradient(cx, cy, 0, cx, cy, raggio * (0.55 + nuLivello * 0.25));
    grande.addColorStop(0, _rgba(0.3 + nuLivello * 0.35));
    grande.addColorStop(0.35, _rgba(0.1 + nuLivello * 0.1));
    grande.addColorStop(1, _rgba(0));
    nuCtx.fillStyle = grande;
    nuCtx.fillRect(0, 0, w, h);

    // Le stelle, in luce additiva: dove si sovrappongono si accendono.
    nuCtx.globalCompositeOperation = 'lighter';
    const t = nuFase;
    for (const p of nuPunti) {
        const a = p.angolo + t * p.velocita;
        const r = raggio * p.raggio * (1 + nuLivello * 0.06 * Math.sin(t * 5 + p.tremolio));
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r * schiacciamento;
        const brillio = p.luce * (0.7 + 0.3 * Math.sin(t * 2.2 + p.tremolio)) * (0.9 + nuLivello * 0.6);
        if (p.nebbia) {
            // una macchia larga e tenue: e' la polvere luminosa lungo i bracci
            nuCtx.fillStyle = _rgba(0.035 + nuLivello * 0.03);
            nuCtx.beginPath();
            nuCtx.arc(x, y, p.grandezza * 9, 0, Math.PI * 2);
            nuCtx.fill();
            continue;
        }
        nuCtx.fillStyle = _rgba(Math.min(1, brillio));
        nuCtx.beginPath();
        nuCtx.arc(x, y, p.grandezza * (1 + nuLivello * 0.6), 0, Math.PI * 2);
        nuCtx.fill();
    }
    nuCtx.globalCompositeOperation = 'source-over';

    // L'anello di misura, circolare: 72 tacche la cui altezza segue la voce, due cerchi e due archi che girano in versi opposti.
    const rc = Math.min(h * 0.46, w * 0.46);
    nuCtx.lineCap = 'round';
    for (let i = 0; i < TACCHE; i++) {
        const a = (i / TACCHE) * Math.PI * 2 - Math.PI / 2;
        const vivo =
            nuStato === 'standby'
                ? 0.12 + 0.08 * Math.sin(i * 0.5 + t)
                : Math.min(
                      1,
                      0.18 +
                          Math.abs(Math.sin(i * 0.7 + t * 9) * Math.cos(i * 0.21 - t * 3)) * nuLivello * 1.8,
                  );
        const r1 = rc * 0.8;
        const r2 = r1 + rc * (0.05 + vivo * 0.2);
        nuCtx.strokeStyle = _rgba(0.3 + vivo * 0.65);
        nuCtx.lineWidth = 1.6;
        nuCtx.beginPath();
        nuCtx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
        nuCtx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
        nuCtx.stroke();
    }
    nuCtx.lineWidth = 1;
    nuCtx.strokeStyle = _rgba(0.45);
    nuCtx.beginPath();
    nuCtx.arc(cx, cy, rc * 0.72, 0, Math.PI * 2);
    nuCtx.stroke();
    nuCtx.strokeStyle = _rgba(0.25);
    nuCtx.setLineDash([3, 6]);
    nuCtx.beginPath();
    nuCtx.arc(cx, cy, rc * 0.62, 0, Math.PI * 2);
    nuCtx.stroke();
    nuCtx.setLineDash([]);
    nuCtx.strokeStyle = _rgba(0.9);
    nuCtx.lineWidth = 2.6;
    nuCtx.beginPath();
    nuCtx.arc(cx, cy, rc * 0.72, t * 1.2, t * 1.2 + 1.1);
    nuCtx.stroke();
    nuCtx.strokeStyle = _rgba(0.6);
    nuCtx.lineWidth = 1.8;
    nuCtx.beginPath();
    nuCtx.arc(cx, cy, rc * 0.62, -t * 1.8, -t * 1.8 + 0.6);
    nuCtx.stroke();

    // Le onde: un impulso e' un'ellisse che si allarga e svanisce, con un alone piu' largo e tenue sotto il filo.
    for (const onda of nuOnde) {
        const quanto = onda.eta / 1.4;
        if (quanto >= 1) continue;
        const rr = raggio * (0.08 + quanto * 1.05);
        const forza = (1 - quanto) * onda.forza;
        nuCtx.strokeStyle = _rgba(forza * 0.22);
        nuCtx.lineWidth = 7 + forza * 9;
        nuCtx.beginPath();
        nuCtx.ellipse(cx, cy, rr, rr * schiacciamento, 0, 0, Math.PI * 2);
        nuCtx.stroke();
        nuCtx.strokeStyle = _rgba(Math.min(1, forza * 0.95));
        nuCtx.lineWidth = 1.2 + forza * 1.8;
        nuCtx.stroke();
    }

    // Il nucleo.
    const rn =
        Math.min(w, h * 1.4, 420) *
        0.06 *
        (1 + nuLivello * 0.35 + (config.battito ? 0.08 * Math.sin(t * 7) : 0));
    const nucleo = nuCtx.createRadialGradient(cx, cy, 0, cx, cy, rn * 2.6);
    nucleo.addColorStop(0, 'rgba(255,255,255,0.95)');
    nucleo.addColorStop(0.25, _rgba(0.95));
    nucleo.addColorStop(1, _rgba(0));
    nuCtx.fillStyle = nucleo;
    nuCtx.beginPath();
    nuCtx.arc(cx, cy, rn * 2.6, 0, Math.PI * 2);
    nuCtx.fill();
}

function _ciclo(adesso) {
    nuFrame = 0;
    if (!nuTela || !nuCtx) return;
    const dt = nuUltimo ? Math.min(0.05, (adesso - nuUltimo) / 1000) : 0.016;
    nuUltimo = adesso;
    const config = STATI[nuStato];

    nuFase += dt * config.giro * (1 + nuLivello * 1.5);
    _colore(config.colore, dt);

    // Il livello segue la voce vera, o un parlato sintetico, o un battito d'ascolto; altrimenti decade.
    let bersaglio = 0;
    if (nuStato === 'parlo') {
        const vero = _livelloAudio();
        if (vero !== null) {
            bersaglio = vero;
        } else {
            nuSintetico += dt;
            bersaglio = 0.35 + 0.35 * Math.abs(Math.sin(nuSintetico * 6.1) * Math.sin(nuSintetico * 2.3 + 1));
        }
        if (bersaglio > nuLivello + 0.12) _emettiOnda(bersaglio);
        else if (!nuOnde.length || nuOnde[nuOnde.length - 1].eta > 0.55) _emettiOnda(bersaglio * 0.8);
    } else if (nuStato === 'ascolto') {
        bersaglio = 0.2 + 0.2 * Math.sin(nuFase * 9);
    } else if (nuStato === 'elaboro') {
        bersaglio = 0.15 + 0.1 * Math.sin(nuFase * 4);
    }
    nuLivello += (bersaglio - nuLivello) * Math.min(1, dt * (bersaglio > nuLivello ? 14 : 3.5));
    if (nuLivello < 0.001) nuLivello = 0;
    for (const onda of nuOnde) onda.eta += dt;
    nuOnde = nuOnde.filter((o) => o.eta < 1.4);

    disegna(dt);

    const finito = nuStato === 'standby' && nuLivello === 0 && nuOnde.length === 0;
    // Anche in standby la galassia gira piano: si ferma solo se non si vede o non la si vuole in movimento.
    if (nuVisibile && !document.hidden && !_ridotto()) {
        nuFrame = requestAnimationFrame(_ciclo);
        nuTela.dataset.animando = finito ? 'lento' : 'si';
    } else {
        nuTela.dataset.animando = 'no';
    }
}

function _avvia() {
    if (!nuTela || nuFrame) return;
    if (!nuVisibile || document.hidden || _ridotto()) {
        nuTela.dataset.animando = 'no';
        disegna(0);
        return;
    }
    nuUltimo = 0;
    nuFrame = requestAnimationFrame(_ciclo);
}

/** Prepara il nucleo se la pagina ha il suo riquadro (`#nucleo`). Si puo' chiamare piu' volte. */
function avviaNucleo() {
    const t = document.getElementById('nucleo');
    if (!t || t === nuTela) return;
    nuTela = t;
    nuCtx = nuTela.getContext('2d');
    nuEtichetta = document.getElementById('nucleo-stato');
    nuTela.dataset.stato = nuStato;
    if (nuEtichetta) nuEtichetta.textContent = STATI[nuStato].scritta;
    nuColore = [...STATI[nuStato].colore];
    _adatta();
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(_adatta).observe(nuTela);
    if (typeof IntersectionObserver !== 'undefined') {
        nuOss = new IntersectionObserver((voci) => {
            nuVisibile = voci.some((v) => v.isIntersecting);
            if (nuVisibile) _avvia();
        });
        nuOss.observe(nuTela);
    }
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) _avvia();
    });
    _avvia();
}

// Parte da solo quando la pagina e' pronta, se c'e' il riquadro del nucleo.
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', avviaNucleo);
else avviaNucleo();
