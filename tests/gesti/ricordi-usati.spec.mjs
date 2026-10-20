// «Ho usato 3 ricordi», sotto la risposta (#252): la risposta di `/api/chat` porta i ricordi entrati nel prompt, la pagina li
// mostra, si aprono, e il collegamento porta alla scheda dei ricordi.
//
// Il server e' finto: qui si prova cio' che nel sorgente non si vede, cioe' che il disegno nasce davvero dalla risposta e che il
// clic su «Apri i ricordi» arriva fino al cambio di scheda. Un ricordo con markup dentro deve restare testo.

import { test, expect } from '@playwright/test';

const RICORDI = [
    { id: 'k_1', categoria: 'casa', estratto: 'La caldaia e in cantina' },
    {
        id: 'k_2',
        categoria: 'salute',
        estratto: '<img src=x onerror="window.__iniettato=1"> la medicina alle sette',
    },
];

async function chiedi(page, ricordi) {
    await page.route('**/api/chat', (route) =>
        route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ response: 'Ecco.', actions: [], ricordi_usati: ricordi }),
        }),
    );
    await page.goto('/index.html');
    // I moduli della pagina devono aver collegato il modulo di invio: scrivere prima fa partire l'invio nativo del form.
    await page.waitForLoadState('networkidle');
    await page.locator('#user-input').fill('dov e la caldaia');
    await page.locator('#send-btn').click();
}

test.describe('i ricordi usati sotto la risposta', () => {
    test('dice quanti ricordi ha usato, si apre, e non esegue il markup di un ricordo', async ({ page }) => {
        await chiedi(page, RICORDI);

        const riquadro = page.locator('[data-ricordi-usati]');
        await expect(riquadro.locator('summary')).toHaveText('Ho usato 2 ricordi');

        await riquadro.locator('summary').click();
        await expect(riquadro).toContainText('La caldaia e in cantina');
        await expect(riquadro).toContainText('la medicina alle sette');
        expect(
            await page.evaluate(() => window.__iniettato),
            'il markup di un ricordo e stato eseguito',
        ).toBeUndefined();
    });

    test('«Apri i ricordi» porta alla scheda della conoscenza', async ({ page }) => {
        await chiedi(page, RICORDI);
        await page.locator('[data-ricordi-usati] summary').click();
        await page.locator('[data-ricordi-usati]').getByText('Apri i ricordi').click();
        await expect(page.locator('#tab-knowledge')).toBeVisible();
    });

    test('senza ricordi usati non compare niente', async ({ page }) => {
        await chiedi(page, []);
        await expect(page.getByText('Ecco.')).toBeVisible();
        await expect(page.locator('[data-ricordi-usati]')).toHaveCount(0);
    });
});
