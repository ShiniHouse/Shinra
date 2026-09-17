// I gesti dell'editor a nodi, chiesti a un browser vero.
//
// Perche' esiste questo file: in un solo pomeriggio due difetti sono
// arrivati fino in casa passando davanti a novantotto guardie.
//
//   1. la crocetta di un nodo faceva partire il trascinamento, perche'
//      `e.target.tagName === 'BUTTON'` e' sempre falso quando il
//      bersaglio e' l'icona dentro al pulsante;
//   2. la crocetta che stacca un cavo non si poteva premere, perche' il
//      piano dei nodi copriva tutta la tela e si prendeva il clic.
//
// Nessuna delle due si vede leggendo il sorgente: la prima vive negli
// eventi, la seconda nel disegno. Le guardie di `test_interfaccia.py`
// leggono il sorgente, quindi erano cieche per costruzione — e
// aggiungerne una che legge le classi con piu' attenzione non basta,
// perche' un elemento puo' coprirne un altro in mille modi.
//
// Qui invece si preme davvero, con un mouse, e si guarda cosa succede.

import { test, expect } from '@playwright/test';

/**
 * Le due cose che devono essere arrivate prima di toccare qualcosa:
 * Tailwind, che decide dove stanno gli elementi, e lucide, che
 * sostituisce le icone. Senza Tailwind il disegno collassa e ogni gesto
 * fallisce per la ragione sbagliata; senza lucide il bersaglio di un
 * clic sulla crocetta non e' quello vero.
 *
 * Arrivano dai CDN come in casa. Se un CDN e' giu', questo test deve
 * dirlo con queste parole, non lasciare sei gesti che falliscono in modo
 * misterioso.
 */
async function preparata(page) {
    await page
        .waitForFunction(() => getComputedStyle(document.body).display === 'flex', null, { timeout: 15_000 })
        .catch(() => {
            throw new Error(
                "Tailwind non e'arrivato dal CDN: il disegno non e' quello vero, i gesti non si possono provare",
            );
        });
}

/** Apre l'editor con la routine di partenza: un innesco e un dispositivo, collegati. */
async function apriEditor(page) {
    await page.goto('/index.html');
    await preparata(page);
    await page.waitForFunction(() => typeof openModularModeBuilder === 'function');
    await page.evaluate(() => openModularModeBuilder());
    await page.waitForSelector('#c-node-node_ha1');
    // Le icone arrivano da lucide: finche' non le ha sostituite, il
    // bersaglio di un clic sulla crocetta non e' quello vero.
    await page.waitForFunction(() => !document.querySelector('#flow-nodes-container i[data-lucide]'));
}

/** Il centro di un elemento, in coordinate di pagina. */
async function centro(page, selettore) {
    const riquadro = await page.locator(selettore).first().boundingBox();
    expect(riquadro, `${selettore} non e' sullo schermo`).not.toBeNull();
    return { x: riquadro.x + riquadro.width / 2, y: riquadro.y + riquadro.height / 2 };
}

/** Un clic vero: premi, sposta di un pelo come fa una mano, rilascia. */
async function premi(page, selettore) {
    const p = await centro(page, selettore);
    await page.mouse.move(p.x, p.y);
    await page.mouse.down();
    await page.mouse.move(p.x + 1, p.y + 1);
    await page.mouse.up();
}

test.describe('editor a nodi', () => {
    test("la crocetta che stacca un cavo si puo' premere", async ({ page }) => {
        await apriEditor(page);
        expect(await page.evaluate(() => _canvasState.edges.length)).toBe(1);

        // Prima di premere: chi c'e' davvero sotto al dito? Se non e' la
        // crocetta, il clic non le arrivera' mai — ed e' esattamente
        // com'era: li' c'era il telaio dei nodi.
        const sotto = await page.evaluate(() => {
            const c = document.querySelector('#flow-svg-layer circle');
            const r = c.getBoundingClientRect();
            const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
            return e ? e.tagName.toLowerCase() : null;
        });
        expect(sotto, 'qualcosa copre la crocetta del cavo').toBe('circle');

        await premi(page, '#flow-svg-layer circle');
        await expect.poll(() => page.evaluate(() => _canvasState.edges.length)).toBe(0);
    });

    test('la crocetta di un nodo lo toglie invece di trascinarlo', async ({ page }) => {
        await apriEditor(page);
        const prima = await page.evaluate(() => _canvasState.nodes.length);

        const p = await centro(page, 'button[title="Elimina nodo"]');
        await page.mouse.move(p.x, p.y);
        await page.mouse.down();

        // Qui, col dito ancora premuto, si vede la differenza. A mouse
        // rilasciato `isDraggingNode` torna nullo da solo, quindi
        // guardarlo dopo non direbbe niente: la prima versione di questo
        // test lo guardava dopo, e infatti non mordeva.
        expect(
            await page.evaluate(() => _canvasState.isDraggingNode),
            'premere la crocetta fa partire il trascinamento del nodo',
        ).toBeNull();

        await page.mouse.move(p.x + 1, p.y + 1);
        await page.mouse.up();
        await expect.poll(() => page.evaluate(() => _canvasState.nodes.length)).toBe(prima - 1);
    });

    test("prendere il nodo per l'intestazione invece lo trascina", async ({ page }) => {
        // L'altra meta' della guardia sopra: se qualcuno spegnesse il
        // trascinamento del tutto, quella resterebbe verde avendo rotto
        // lo spostamento dei nodi.
        await apriEditor(page);
        const p = await centro(page, '#c-node-node_ha1 .flow-node-header');
        await page.mouse.move(p.x, p.y);
        await page.mouse.down();
        expect(await page.evaluate(() => _canvasState.isDraggingNode)).toBe('node_ha1');
        await page.mouse.up();
    });

    test("un nodo si sposta prendendolo per l'intestazione", async ({ page }) => {
        await apriEditor(page);
        const prima = await page.evaluate(() => _canvasState.nodes[1].x);
        const p = await centro(page, '#c-node-node_ha1 .flow-node-header');
        await page.mouse.move(p.x, p.y);
        await page.mouse.down();
        await page.mouse.move(p.x + 70, p.y + 40, { steps: 6 });
        await page.mouse.up();
        await expect.poll(() => page.evaluate(() => _canvasState.nodes[1].x)).toBeGreaterThan(prima + 50);
    });

    test('scrivere in un campo del nodo non lo sposta', async ({ page }) => {
        await apriEditor(page);
        const prima = await page.evaluate(() => _canvasState.nodes[1].x);
        await page.locator('#c-node-node_ha1 input').first().click();
        await page.keyboard.type('light.salotto');
        expect(await page.evaluate(() => _canvasState.nodes[1].x)).toBe(prima);
        await expect(page.locator('#c-node-node_ha1 input').first()).toHaveValue('light.salotto');
    });

    test("un cavo si tira da un pin all'altro", async ({ page }) => {
        await apriEditor(page);
        await page.evaluate(() => {
            _canvasState.edges = [];
            renderCanvasWires();
            updateCanvasStats();
        });
        const da = await centro(page, '#c-node-node_trig .port-pin-out');
        const a = await centro(page, '#c-node-node_ha1 .port-pin-in');
        await page.mouse.move(da.x, da.y);
        await page.mouse.down();
        await page.mouse.move(a.x, a.y, { steps: 10 });
        await page.mouse.up();
        await expect.poll(() => page.evaluate(() => _canvasState.edges.length)).toBe(1);
    });

    test('la barra aggiunge un blocco', async ({ page }) => {
        await apriEditor(page);
        const prima = await page.evaluate(() => _canvasState.nodes.length);
        await page.getByRole('button', { name: /Ritardo \(Pausa\)/ }).click();
        await expect.poll(() => page.evaluate(() => _canvasState.nodes.length)).toBe(prima + 1);
    });
});
