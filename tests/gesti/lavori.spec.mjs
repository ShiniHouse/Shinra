// «Lavori» nella scheda del Cervello: cosa sta facendo Shinra per me, a che punto e', e il pulsante per fermarlo (#431).
//
// Il server e' finto. Si prova cio' che nel sorgente non si vede: che il pannello compare solo se c'e' qualcosa, che mostra avanzamento e stato, che
// «Annulla» arriva alla rotta giusta e il pannello si aggiorna, e che una richiesta con markup resta testo.

import { test, expect } from '@playwright/test';

const GRAFO = {
    nodi: [{ id: 'stanza:cucina', tipo: 'stanza', nome: 'Cucina', cluster: 'stanze' }],
    collegamenti: [],
    clusters: [{ id: 'stanze', nome: 'Stanze', nodi: 1, nascosti: 0 }],
    sistemi: [],
    contatori: { nodi: 1, collegamenti: 0, sistemi: 0, sistemi_attivi: 0, agenti_pronti: 0 },
    troncato: false,
};

const OSTILE = '<img src=x onerror="window.__iniettato=1"> prepara la sera';

function lavoro(id, stato, extra = {}) {
    return {
        id,
        scopo: 'chat',
        richiesta: 'prepara la casa per la sera',
        stato,
        avanzamento: 0,
        fase: '',
        esito: '',
        motivo: '',
        creato_il: '2026-10-22T20:00:00',
        finito_il: null,
        ...extra,
    };
}

async function apri(page, lavori) {
    const annullati = [];
    let elenco = lavori;
    await page.route('**/api/cervello', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GRAFO) }),
    );
    await page.route('**/api/lavori', (route) =>
        route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ lavori: elenco }),
        }),
    );
    await page.route('**/api/lavori/*/annulla', (route) => {
        const id = route.request().url().split('/').slice(-2)[0];
        annullati.push(id);
        elenco = elenco.map((l) => (l.id === id ? { ...l, stato: 'annullato' } : l));
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ stato: 'annullato' }),
        });
    });
    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
    return { annullati };
}

test.describe('i lavori nel Cervello', () => {
    test('un lavoro in corso mostra la richiesta, la fase e l avanzamento, con Annulla', async ({ page }) => {
        await apri(page, [lavoro('l_1', 'in_corso', { avanzamento: 40, fase: 'consulto la casa' })]);
        const pannello = page.locator('#cervello-lavori');
        await expect(pannello).toBeVisible();
        const riga = pannello.locator('[data-lavoro="l_1"]');
        await expect(riga).toContainText('prepara la casa per la sera');
        await expect(riga).toContainText('ci sto lavorando · consulto la casa');
        await expect(riga).toContainText('40%');
        await expect(riga.getByRole('button', { name: 'Annulla' })).toBeVisible();
    });

    test('senza lavori il pannello non compare', async ({ page }) => {
        await apri(page, []);
        await expect(page.locator('#cervello-lavori')).toBeHidden();
    });

    test('un lavoro finito si vede, ma senza Annulla e senza barra', async ({ page }) => {
        await apri(page, [lavoro('l_2', 'fatto', { avanzamento: 100, esito: 'Fatto.' })]);
        const riga = page.locator('#cervello-lavori [data-lavoro="l_2"]');
        await expect(riga).toContainText('finito');
        await expect(riga.getByRole('button', { name: 'Annulla' })).toHaveCount(0);
        await expect(riga).not.toContainText('100%');
    });

    test('Annulla arriva alla rotta del lavoro giusto e il pannello si aggiorna', async ({ page }) => {
        const { annullati } = await apri(page, [lavoro('l_3', 'in_corso', { avanzamento: 10 })]);
        await page
            .locator('#cervello-lavori [data-lavoro="l_3"]')
            .getByRole('button', { name: 'Annulla' })
            .click();
        await expect.poll(() => annullati).toEqual(['l_3']);
        const riga = page.locator('#cervello-lavori [data-lavoro="l_3"]');
        await expect(riga).toContainText('annullato');
        await expect(riga.getByRole('button', { name: 'Annulla' })).toHaveCount(0);
    });

    test('una richiesta con markup resta testo', async ({ page }) => {
        await apri(page, [lavoro('l_4', 'in_corso', { richiesta: OSTILE })]);
        await expect(page.locator('#cervello-lavori')).toContainText('<img src=x onerror=');
        expect(await page.evaluate(() => window.__iniettato)).toBeUndefined();
        await expect(page.locator('#cervello-lavori img')).toHaveCount(0);
    });

    test('un lavoro fallito dice il perche, non un errore tecnico', async ({ page }) => {
        await apri(page, [lavoro('l_5', 'fallito', { motivo: 'tetto di tempo' })]);
        await expect(page.locator('#cervello-lavori [data-lavoro="l_5"]')).toContainText(
            'non riuscito · tetto di tempo',
        );
    });
});
