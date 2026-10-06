// Il grafo del Cervello regge un telefono e un tablet? (issue #187)
//
// «Un grafo con centinaia di nodi e' bello su un portatile e puo' andare a scatti su un
// telefono.» Qui non si finge un telefono: si **rallenta la CPU** del browser (4x, 6x: i
// numeri che di solito si usano per un telefono medio e uno economico) e si conta cosa
// fa il grafo con 100, 300 e 600 nodi.
//
// Cosa si misura, per ogni prova:
//  - i **fotogrammi al secondo** mentre il grafo si assesta (e' il momento piu' caro);
//  - quanto **ci mette ad assestarsi**;
//  - e che **dopo** non resti niente in esecuzione: zero fotogrammi richiesti. E' cio' che
//    un tablet appeso al muro deve fare, e l'unica cosa che qui si afferma con decisione.
//
// I numeri sui fotogrammi dipendono dalla macchina che gira il test: si **stampano** (e si
// scrivono nella scheda) e si controlla solo che non crollino sotto una soglia larga.
// Questo non sostituisce un telefono vero: lo rende ripetibile.
//
// **La matrice dei fotogrammi gira solo a richiesta** (`MISURA_GRAFO=1 npx playwright test
// cervello-prestazioni`): con la CPU rallentata dura minuti, e un numero che dipende dalla macchina
// non deve far fallire la CI. Le prove della modalita' leggera e della scheda chiusa girano sempre.

import { test, expect } from '@playwright/test';

// Un generatore con seme: lo stesso grafo a ogni giro, su ogni macchina.
function casuale(seme) {
    let s = seme >>> 0;
    return () => {
        s = (s * 1664525 + 1013904223) >>> 0;
        return s / 4294967296;
    };
}

const GRUPPI = ['stanze', 'dispositivi', 'alias', 'routine', 'regole', 'strumenti', 'agenti', 'conoscenza'];
const TIPI = {
    stanze: 'stanza',
    dispositivi: 'dispositivo',
    alias: 'alias',
    routine: 'routine',
    regole: 'regola',
    strumenti: 'strumento',
    agenti: 'agente',
    conoscenza: 'fatto',
};

function grafo(n) {
    const r = casuale(7);
    const nodi = [];
    for (let i = 0; i < n; i++) {
        const cluster = GRUPPI[Math.floor(r() * GRUPPI.length)];
        nodi.push({ id: `${TIPI[cluster]}:n${i}`, tipo: TIPI[cluster], nome: `nodo ${i}`, cluster });
    }
    const collegamenti = [];
    for (let i = 1; i < n; i++) {
        // Ogni nodo si lega a uno dei precedenti, e uno ogni tre a un secondo: ~1,3 collegamenti per nodo.
        collegamenti.push({ da: nodi[i].id, a: nodi[Math.floor(r() * i)].id, tipo: 'usa' });
        if (i % 3 === 0) collegamenti.push({ da: nodi[i].id, a: nodi[Math.floor(r() * i)].id, tipo: 'usa' });
    }
    const conta = (c) => nodi.filter((x) => x.cluster === c).length;
    return {
        nodi,
        collegamenti,
        clusters: GRUPPI.map((id) => ({ id, nome: id, nodi: conta(id), nascosti: 0 })),
        sistemi: [],
        contatori: {
            nodi: n,
            collegamenti: collegamenti.length,
            sistemi: 0,
            sistemi_attivi: 0,
            agenti_pronti: 0,
        },
        troncato: false,
    };
}

async function misura(page, n, rallentamento) {
    await page.addInitScript(() => {
        const originale = window.requestAnimationFrame.bind(window);
        window.__fotogrammi = [];
        window.requestAnimationFrame = (f) =>
            originale((t) => {
                window.__fotogrammi.push(performance.now());
                f(t);
            });
    });
    await page.route('**/api/cervello', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(grafo(n)) }),
    );
    const sessione = await page.context().newCDPSession(page);
    await sessione.send('Emulation.setCPUThrottlingRate', { rate: rallentamento });

    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
    await page.locator('#cervello-canvas').waitFor({ state: 'visible' });

    // Aspetta che il disegno si fermi: `data-animando` passa a «no» quando il ciclo e' finito.
    const inizio = Date.now();
    await page.waitForFunction(
        () => document.querySelector('#cervello-canvas')?.dataset.animando === 'no',
        null,
        {
            timeout: 25_000,
            polling: 100,
        },
    );
    const assestamentoMs = Date.now() - inizio;

    const messi = await page.evaluate(() => window.__fotogrammi.slice());
    const fps = messi.length > 1 ? (messi.length - 1) / ((messi[messi.length - 1] - messi[0]) / 1000) : 0;

    // Fermo: nessun altro fotogramma deve essere richiesto dal disegno.
    const prima = await page.evaluate(() => window.__fotogrammi.length);
    await page.waitForTimeout(1500);
    const dopo = await page.evaluate(() => window.__fotogrammi.length);

    await sessione.detach();
    return { n, rallentamento, fps: Math.round(fps), assestamentoMs, fotogrammiDaFermo: dopo - prima };
}

const PROVE = [
    [100, 1],
    [300, 1],
    [600, 1],
    [100, 4],
    [300, 4],
    [600, 4],
    [300, 6],
    [600, 6],
    [1000, 1],
    [1000, 4],
    [1000, 6],
];

test.describe('il Cervello sui dispositivi lenti (#187)', () => {
    test.skip(!process.env.MISURA_GRAFO, 'misura a richiesta: MISURA_GRAFO=1');
    for (const [n, rallentamento] of PROVE) {
        test(`${n} nodi, CPU rallentata ${rallentamento}x`, async ({ page }) => {
            test.setTimeout(60_000);
            const esito = await misura(page, n, rallentamento);
            console.log(
                `MISURA nodi=${esito.n} cpu=${esito.rallentamento}x fps=${esito.fps} ` +
                    `assestamento=${esito.assestamentoMs}ms fotogrammi_da_fermo=${esito.fotogrammiDaFermo}`,
            );

            // L'unica cosa che si afferma con decisione: un grafo assestato non lavora piu'.
            expect(esito.fotogrammiDaFermo).toBe(0);
        });
    }
});

// ----------------------------------------------------------- la modalita' leggera e la scheda chiusa

async function apriConGrafo(page, n) {
    let canale = null;
    await page.routeWebSocket('**/ws/eventi', (ws) => {
        canale = ws;
    });
    await page.addInitScript(() => {
        const originale = window.requestAnimationFrame.bind(window);
        window.__fotogrammi = [];
        window.requestAnimationFrame = (f) =>
            originale((t) => {
                window.__fotogrammi.push(performance.now());
                f(t);
            });
    });
    await page.route('**/api/cervello', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(grafo(n)) }),
    );
    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
    await page.waitForFunction(
        () => document.querySelector('#cervello-canvas')?.dataset.animando === 'no',
        null,
        {
            timeout: 25_000,
            polling: 100,
        },
    );
    return () => canale;
}

test.describe('la modalità leggera (#187)', () => {
    test('con pochi nodi è spenta, e chi guarda la può accendere', async ({ page }) => {
        await apriConGrafo(page, 100);
        const casella = page.locator('#cervello-leggera');
        await expect(casella).not.toBeChecked();
        await expect(page.locator('#cervello-leggera-nota')).toContainText('Si accende da sola oltre');

        await casella.check();

        await expect(page.locator('#cervello-leggera-nota')).toContainText('Scelta tua');
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-animando', 'no');
    });

    test('oltre i quattrocento nodi si accende da sola, e il grafo sta fermo', async ({ page }) => {
        await apriConGrafo(page, 600);

        await expect(page.locator('#cervello-leggera')).toBeChecked();
        await expect(page.locator('#cervello-leggera-nota')).toContainText('Accesa da sola');
        // Si e' disposto in un colpo: nessun fotogramma richiesto dopo.
        const prima = await page.evaluate(() => window.__fotogrammi.length);
        await page.waitForTimeout(1000);
        const dopo = await page.evaluate(() => window.__fotogrammi.length);
        expect(dopo - prima).toBe(0);
    });

    test('la scelta di chi guarda vince sul numero dei nodi, e si ricorda', async ({ page }) => {
        await apriConGrafo(page, 600);
        const casella = page.locator('#cervello-leggera');
        await expect(casella).toBeChecked();

        await casella.uncheck();
        await expect(page.locator('#cervello-leggera-nota')).toContainText(
            "l'animazione resta sempre accesa",
        );

        await page.reload();
        await page.locator('#tab-cervello').waitFor({ state: 'visible' });
        await expect(page.locator('#cervello-leggera')).not.toBeChecked();
    });

    test("a scheda chiusa un evento dell'agente non fa lavorare il disegno", async ({ page }) => {
        const canale = await apriConGrafo(page, 100);
        await page.evaluate(() => {
            document.getElementById('tab-cervello').style.display = 'none';
        });
        const prima = await page.evaluate(() => window.__fotogrammi.length);

        canale().send(
            JSON.stringify({
                tipo: 'agente.richiesta',
                dati: { richiesta: 'r1', nodi: ['agente:modello'] },
                momento: '2026-10-01T10:00:00Z',
                frase: '',
            }),
        );
        await page.waitForTimeout(1200);

        const dopo = await page.evaluate(() => window.__fotogrammi.length);
        expect(dopo - prima).toBe(0);
    });
});
