// «Ci penso»: una richiesta lenta risponde subito «ci sto lavorando», e l'esito arriva dopo in chat dal canale degli eventi (#431).
//
// Il server e' finto, e il canale degli eventi pure: la pagina e' l'anteprima statica. Si prova cio' che nel sorgente non si vede: che la
// dashboard dichiara di poter aspettare, che la risposta provvisoria si legge, che l'esito che arriva dopo finisce in chat, e che un testo
// con markup resta testo.

import { test, expect } from '@playwright/test';

const OSTILE = '<img src=x onerror="window.__iniettato=1"> fatto';

async function apri(page) {
    const corpiInviati = [];
    let canale = null;
    await page.routeWebSocket(/\/ws\/eventi/, (ws) => {
        canale = ws;
    });
    await page.route('**/api/chat', (route) => {
        corpiInviati.push(route.request().postDataJSON());
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                response: 'Ci sto lavorando: ti avviso appena ho finito.',
                actions: [],
                lavoro: { id: 'l_1', stato: 'in_coda' },
            }),
        });
    });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
    return { corpiInviati, canale: () => canale };
}

async function chiedi(page) {
    await page.locator('#user-input').fill('prepara la casa per la sera');
    await page.locator('#send-btn').click();
}

test.describe('«ci penso»', () => {
    test('la dashboard dichiara di poter aspettare e mostra «ci sto lavorando»', async ({ page }) => {
        const { corpiInviati } = await apri(page);
        await chiedi(page);
        await expect(page.locator('#messages-container')).toContainText('Ci sto lavorando');
        expect(corpiInviati).toHaveLength(1);
        expect(corpiInviati[0].puo_attendere).toBe(true);
    });

    test("l'esito che arriva dopo dal canale degli eventi finisce in chat", async ({ page }) => {
        const { canale } = await apri(page);
        await chiedi(page);
        await expect(page.locator('#messages-container')).toContainText('Ci sto lavorando');
        await expect.poll(() => canale() !== null, { timeout: 20_000 }).toBe(true);
        canale().send(
            JSON.stringify({
                tipo: 'lavoro.finito',
                dati: { id: 'l_1', stato: 'fatto', testo: 'Ho acceso le luci e chiuso le tapparelle.' },
                momento: new Date().toISOString(),
                frase: '',
            }),
        );
        await expect(page.locator('#messages-container')).toContainText(
            'Ho acceso le luci e chiuso le tapparelle.',
        );
    });

    test('un esito con markup resta testo e un evento senza testo non scrive niente', async ({ page }) => {
        const { canale } = await apri(page);
        await chiedi(page);
        await expect(page.locator('#messages-container')).toContainText('Ci sto lavorando');
        await expect.poll(() => canale() !== null, { timeout: 20_000 }).toBe(true);
        canale().send(
            JSON.stringify({
                tipo: 'lavoro.finito',
                dati: { id: 'l_1', stato: 'fatto' },
                momento: '',
                frase: '',
            }),
        );
        canale().send(
            JSON.stringify({
                tipo: 'lavoro.finito',
                dati: { id: 'l_1', stato: 'fatto', testo: OSTILE },
                momento: new Date().toISOString(),
                frase: '',
            }),
        );
        await expect(page.locator('#messages-container')).toContainText('<img src=x onerror=');
        expect(await page.evaluate(() => window.__iniettato)).toBeUndefined();
        await expect(page.locator('#messages-container img')).toHaveCount(0);
    });
});
