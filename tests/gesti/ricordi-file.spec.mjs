// Esportare e importare i ricordi come file (#251): l'anteprima viene prima, non scrive niente, e solo «Applica» manda la conferma.
//
// Il server e' finto: qui si prova cio' che nel sorgente non si vede, cioe' che scegliere un file apre l'anteprima e non scrive,
// che «Annulla» lascia tutto com'e', che «Applica» invia il contenuto con la conferma, e che un ricordo con markup resta testo.

import { test, expect } from '@playwright/test';

const ANTEPRIMA = {
    nuovi: [{ testo: 'Mi piace il caffe', categoria: 'gusti', attivo: true, sospetto: false }],
    modificati: [
        {
            id: 'k_a2',
            prima: { testo: 'Mi sveglio alle sette', categoria: 'routine', attivo: true },
            dopo: {
                testo: '<img src=x onerror="window.__iniettato=1"> alle sei',
                categoria: 'routine',
                attivo: true,
            },
            sospetto: false,
        },
    ],
    tolti: [{ id: 'k_a1', testo: 'Preferisco il te verde', categoria: 'gusti', attivo: true }],
    invariati: 0,
    ignorate: 0,
};

async function apri(page) {
    const visti = { anteprime: [], importazioni: [] };
    await page.route('**/api/knowledge', (r) =>
        r.fulfill({ status: 200, contentType: 'application/json', body: '[]' }),
    );
    await page.route('**/api/ricordi?**', (r) =>
        r.fulfill({ status: 200, contentType: 'application/json', body: '{"ricordi":[]}' }),
    );
    await page.route('**/api/ricordi/importa/anteprima', async (r) => {
        visti.anteprime.push(r.request().postDataJSON());
        await r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ANTEPRIMA) });
    });
    await page.route('**/api/ricordi/importa', async (r) => {
        visti.importazioni.push(r.request().postDataJSON());
        await r.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                success: true,
                nuovi: 1,
                modificati: 1,
                archiviati: 1,
                saltati: 0,
                da_confermare: 0,
            }),
        });
    });
    await page.goto('/index.html?scheda=knowledge');
    await page.locator('#tab-knowledge').waitFor({ state: 'visible' });
    return visti;
}

const FILE = {
    name: 'memorie.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Memorie\n\n- Mi piace il caffe\n'),
};

test.describe('i ricordi in un file', () => {
    test("scegliere un file apre l'anteprima e non scrive niente", async ({ page }) => {
        const visti = await apri(page);
        await page.locator('#ricordi-file').setInputFiles(FILE);

        const riquadro = page.locator('#ricordi-anteprima');
        await expect(riquadro).toBeVisible();
        await expect(riquadro).toContainText('Mi piace il caffe');
        await expect(riquadro).toContainText('Mi sveglio alle sette');
        await expect(riquadro).toContainText('Preferisco il te verde');
        expect(visti.anteprime).toHaveLength(1);
        expect(visti.anteprime[0]).toMatchObject({ ambito: 'casa' });
        expect(visti.importazioni, "l'anteprima ha scritto").toHaveLength(0);
        expect(
            await page.evaluate(() => window.__iniettato),
            'il markup di un ricordo e stato eseguito',
        ).toBeUndefined();
    });

    test("Annulla lascia tutto com'e'", async ({ page }) => {
        const visti = await apri(page);
        await page.locator('#ricordi-file').setInputFiles(FILE);
        await page.getByRole('button', { name: 'Annulla' }).click();

        await expect(page.locator('#ricordi-anteprima')).toBeHidden();
        await expect(page.locator('#ricordi-esito')).toContainText('non ho scritto niente');
        expect(visti.importazioni).toHaveLength(0);
    });

    test("Applica manda il contenuto con la conferma, e togliere e' una scelta a parte", async ({ page }) => {
        const visti = await apri(page);
        await page.locator('#ricordi-file').setInputFiles(FILE);

        await page.getByRole('button', { name: 'Applica' }).click();
        await expect(page.locator('#ricordi-esito')).toContainText('1 nuovi, 1 corretti');
        expect(visti.importazioni).toHaveLength(1);
        expect(visti.importazioni[0]).toMatchObject({
            conferma: true,
            togli: false,
            contenuto: '# Memorie\n\n- Mi piace il caffe\n',
        });

        await page.locator('#ricordi-file').setInputFiles(FILE);
        await page.getByLabel('Archivia anche quelli che non sono nel file', { exact: false }).check();
        await page.getByRole('button', { name: 'Applica' }).click();
        await expect.poll(() => visti.importazioni.length).toBe(2);
        expect(visti.importazioni[1].togli).toBe(true);
    });
});
