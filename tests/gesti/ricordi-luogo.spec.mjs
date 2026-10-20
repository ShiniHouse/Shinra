// I ricordi hanno un luogo (#345): si sceglie dove vale un ricordo, la scheda lo mostra, e un nome di luogo con markup resta testo.

import { test, expect } from '@playwright/test';

const LUOGHI = [
    { id: 'l_casa', nome: 'Casa' },
    { id: 'l_mare', nome: 'Casa al <b>mare</b>' },
];

async function apri(page) {
    const visti = { scritti: [], corretti: [] };
    await page.route('**/api/knowledge', (r) =>
        r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    );
    await page.route('**/api/luoghi', (r) =>
        r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ luoghi: LUOGHI }) }),
    );
    await page.route('**/api/ricordi?**', (r) =>
        r.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                ricordi: [
                    {
                        id: 'k_1',
                        testo: 'Le chiavi sono sotto il vaso',
                        categoria: 'generale',
                        ambito: 'mio',
                        origine: 'manuale',
                        importanza: 3,
                        fissato: false,
                        usi: 0,
                        stato: 'attivo',
                        attivo: true,
                        luogo_id: 'l_mare',
                        luogo: 'Casa al <b>mare</b>',
                    },
                ],
            }),
        }),
    );
    await page.route('**/api/ricordi', async (r) => {
        if (r.request().method() === 'POST') visti.scritti.push(r.request().postDataJSON());
        await r.fulfill({ status: 200, contentType: 'application/json', body: '{"success":true}' });
    });
    await page.route('**/api/ricordi/k_1', async (r) => {
        visti.corretti.push(r.request().postDataJSON());
        await r.fulfill({ status: 200, contentType: 'application/json', body: '{"success":true}' });
    });
    await page.goto('/index.html?scheda=knowledge');
    await page.locator('#tab-knowledge').waitFor({ state: 'visible' });
    await page.locator('#ricordi-ambito-mio').click();
    return visti;
}

test.describe('i ricordi hanno un luogo', () => {
    test('la scheda mostra il luogo e il nome resta testo', async ({ page }) => {
        await apri(page);
        const scheda = page.locator('[data-ricordo="k_1"]');
        await expect(scheda).toContainText('Casa al <b>mare</b>');
        await expect(scheda.locator('b')).toHaveCount(0);
    });

    test('scrivendo un ricordo si sceglie dove vale', async ({ page }) => {
        const visti = await apri(page);
        await expect(page.locator('#ricordi-luogo option')).toHaveCount(3);
        await page.locator('#ricordi-nuovo').fill('La caldaia del mare e in garage');
        await page.locator('#ricordi-luogo').selectOption('l_mare');
        await page.getByRole('button', { name: 'Ricordalo' }).click();
        await expect.poll(() => visti.scritti.length).toBe(1);
        expect(visti.scritti[0]).toMatchObject({ ambito: 'mio', luogo_id: 'l_mare' });
    });

    test('senza scegliere vale ovunque', async ({ page }) => {
        const visti = await apri(page);
        await page.locator('#ricordi-nuovo').fill('Mi piace il te verde');
        await page.getByRole('button', { name: 'Ricordalo' }).click();
        await expect.poll(() => visti.scritti.length).toBe(1);
        expect(visti.scritti[0].luogo_id).toBe('');
    });
});
