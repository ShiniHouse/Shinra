// Il Cervello come una galassia (tavolozza Jarvis): stesso grafo, un altro disegno.
//
// Il server e' finto. Si prova che il disegno a stelle compare solo con la tavolozza Jarvis, che il canvas non e' vuoto, e che un
// impulso (un nodo acceso) non rompe niente e tiene il ciclo di disegno vivo finche' dura.

import { test, expect } from '@playwright/test';

const GRAFO = {
    nodi: [
        { id: 'stanza:cucina', tipo: 'stanza', nome: 'Cucina', cluster: 'stanze' },
        { id: 'dispositivo:light.cucina', tipo: 'dispositivo', nome: 'luce cucina', cluster: 'dispositivi' },
        { id: 'alias:a1', tipo: 'alias', nome: 'luce cucina', cluster: 'alias' },
    ],
    collegamenti: [
        { da: 'alias:a1', a: 'dispositivo:light.cucina', tipo: 'chiama' },
        { da: 'dispositivo:light.cucina', a: 'stanza:cucina', tipo: 'sta_in' },
    ],
    clusters: [
        { id: 'stanze', nome: 'Stanze', nodi: 1, nascosti: 0 },
        { id: 'dispositivi', nome: 'Dispositivi', nodi: 1, nascosti: 0 },
        { id: 'alias', nome: 'Alias', nodi: 1, nascosti: 0 },
    ],
    sistemi: [],
    contatori: { nodi: 3, collegamenti: 2, sistemi: 0, sistemi_attivi: 0, agenti_pronti: 0 },
    troncato: false,
};

async function apri(page, memoria = {}) {
    await page.addInitScript((m) => {
        for (const [k, v] of Object.entries(m)) localStorage.setItem(k, v);
    }, memoria);
    await page.route('**/api/cervello', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GRAFO) }),
    );
    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
    await expect.poll(() => page.locator('#cervello-canvas').getAttribute('data-nodi-visibili')).toBe('3');
}

const pixelAccesi = (page) =>
    page.evaluate(() => {
        const c = document.getElementById('cervello-canvas');
        const dati = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
        let accesi = 0;
        for (let i = 3; i < dati.length; i += 4) if (dati[i] > 0) accesi++;
        return accesi;
    });

test.describe('il Cervello a stelle', () => {
    test('con la tavolozza Jarvis il grafo e una galassia, e il canvas non e vuoto', async ({ page }) => {
        await apri(page);
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-stile', 'stelle');
        // Si aspetta invece di leggere una volta: dopo un ridimensionamento la tela e' vuota fino al fotogramma dopo, e in CI ci si puo' cadere in mezzo.
        await expect.poll(() => pixelAccesi(page)).toBeGreaterThan(500);
    });

    test("con un'altra tavolozza il disegno e quello di sempre", async ({ page }) => {
        await apri(page, { shinra_palette: 'aurora', shinra_palette_scelta: '1' });
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-stile', 'piano');
        await expect.poll(() => pixelAccesi(page)).toBeGreaterThan(100);
    });

    test('un nodo acceso manda un impulso sui fili e il ciclo resta vivo, poi si ferma', async ({ page }) => {
        await apri(page);
        await page.evaluate(async () => {
            const { attivita } = await import('/static/js/cervello_attivita.js');
            attivita.registra({
                tipo: 'agente.dispositivo',
                dati: { nodi: ['dispositivo:light.cucina'], richiesta: 'r1', riuscito: true },
            });
        });
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-nodi-accesi', /light\.cucina/);
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-animando', 'si');
        // L'accensione dura pochi secondi e poi il ciclo si ferma da solo: niente animazione senza motivo. Il tempo e' largo apposta: in CI
        // la fisica del grafo puo' metterci piu' di nove secondi ad assestarsi, e il ciclo non si ferma finche' qualcosa si muove.
        await expect(page.locator('#cervello-canvas')).toHaveAttribute('data-animando', 'no', {
            timeout: 25_000,
        });
    });
});
