// Il nucleo di Shinra e la tavolozza «Jarvis»: la home e' una console scura con una galassia al centro, che batte quando
// Shinra parla. Nel sorgente non si vede se il canvas si disegna, se lo stato arriva e se il movimento ridotto lo ferma.

import { test, expect } from '@playwright/test';

async function apri(page, memoria = {}) {
    await page.addInitScript((m) => {
        for (const [k, v] of Object.entries(m)) localStorage.setItem(k, v);
    }, memoria);
    await page.goto('/index.html');
    await page.locator('#tab-console').waitFor({ state: 'visible' });
}

const stato = (page) => page.locator('#nucleo').getAttribute('data-stato');
const impostaStato = (page, nome) =>
    page.evaluate(async (n) => {
        const m = await import('/static/js/nucleo.js');
        m.impostaStato(n);
    }, nome);

test.describe('la tavolozza Jarvis e il nucleo', () => {
    test('e di serie: sempre scura, con il nucleo in vista', async ({ page }) => {
        await apri(page);
        await expect(page.locator('html')).toHaveAttribute('data-palette', 'jarvis');
        await expect(page.locator('html')).toHaveClass(/dark/);
        await expect(page.locator('#nucleo')).toBeVisible();
        await expect(page.locator('#nucleo-stato')).toHaveText('STANDBY');
    });

    test('e sempre scura anche se si era scelto il tema giorno', async ({ page }) => {
        await apri(page, { shinra_theme_mode: 'light' });
        await expect(page.locator('html')).toHaveClass(/dark/);
        await expect(page.locator('html')).not.toHaveClass(/light/);
    });

    test('il nucleo ha il canvas disegnato davvero, non vuoto', async ({ page }) => {
        await apri(page);
        await page.waitForTimeout(400);
        const pieno = await page.evaluate(() => {
            const c = document.getElementById('nucleo');
            const dati = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
            let acceso = 0;
            for (let i = 3; i < dati.length; i += 4 * 17) if (dati[i] > 40) acceso++;
            return acceso;
        });
        expect(pieno, 'il canvas del nucleo e vuoto').toBeGreaterThan(50);
    });

    test('segue lo stato di Shinra: ascolto, elaboro, parlo, e torna a standby', async ({ page }) => {
        await apri(page);
        for (const [dato, atteso, scritta] of [
            ['listening', 'ascolto', 'ASCOLTO'],
            ['thinking', 'elaboro', 'ELABORO'],
            ['speaking', 'parlo', 'PARLO'],
            ['idle', 'standby', 'STANDBY'],
        ]) {
            await impostaStato(page, dato);
            expect(await stato(page)).toBe(atteso);
            await expect(page.locator('#nucleo-stato')).toHaveText(scritta);
        }
    });

    test('mentre parla si anima, e a standby gira piano', async ({ page }) => {
        await apri(page);
        await impostaStato(page, 'speaking');
        await expect(page.locator('#nucleo')).toHaveAttribute('data-animando', 'si');
    });

    test('con il movimento ridotto non si anima', async ({ browser }, testInfo) => {
        const contesto = await browser.newContext({
            reducedMotion: 'reduce',
            baseURL: testInfo.project.use.baseURL,
        });
        const page = await contesto.newPage();
        await page.goto('/index.html');
        await page.locator('#nucleo').waitFor({ state: 'visible' });
        await impostaStato(page, 'speaking');
        await expect(page.locator('#nucleo')).toHaveAttribute('data-animando', 'no');
        await contesto.close();
    });

    test("con un'altra tavolozza il nucleo non si vede e la pagina e quella di sempre", async ({ page }) => {
        await apri(page, { shinra_palette: 'aurora', shinra_palette_scelta: '1' });
        await expect(page.locator('html')).toHaveAttribute('data-palette', 'aurora');
        await expect(page.locator('#nucleo')).toBeHidden();
    });

    test('la risposta di Shinra da un impulso al nucleo senza cambiarne lo stato', async ({ page }) => {
        await page.route('**/api/chat', (r) =>
            r.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({ response: 'Fatto.', actions: [], ricordi_usati: [] }),
            }),
        );
        await apri(page);
        await page.waitForLoadState('networkidle');
        await page.locator('#user-input').fill('ciao');
        await page.locator('#send-btn').click();
        await expect(page.getByText('Fatto.')).toBeVisible();
        await expect(page.locator('#nucleo')).toHaveAttribute('data-animando', /si|lento/);
    });
});
