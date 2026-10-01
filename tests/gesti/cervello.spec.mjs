// La scheda «Il Cervello», chiesta a un browser vero (issue #186).
//
// Il disegno e' un canvas: nel sorgente si legge cosa dovrebbe fare, ma solo un
// browser dice se il clic arriva, se la tastiera si sposta fra i nodi e se un
// nome ostile resta un nome. La pagina qui e' l'anteprima statica, che non ha un
// server: la risposta di `/api/cervello` si finge, e questo e' il punto — la
// scheda deve fare la cosa giusta con QUALUNQUE risposta, anche una ostile.

import { test, expect } from '@playwright/test';

const OSTILE = '<img src=x onerror="window.__rubato=1"> lampada';

const GRAFO = {
    nodi: [
        { id: 'stanza:cucina', tipo: 'stanza', nome: 'Cucina', cluster: 'stanze' },
        {
            id: 'dispositivo:light.cucina',
            tipo: 'dispositivo',
            nome: 'luce cucina',
            cluster: 'dispositivi',
            entita: 'light.cucina',
        },
        {
            id: 'dispositivo:light.sala',
            tipo: 'dispositivo',
            nome: OSTILE,
            cluster: 'dispositivi',
            entita: 'light.sala',
        },
        { id: 'alias:a1', tipo: 'alias', nome: 'luce cucina', cluster: 'alias' },
        { id: 'routine:m1', tipo: 'routine', nome: 'Cinema', cluster: 'routine', stato: 'attivo' },
        { id: 'regola:r1', tipo: 'regola', nome: 'Luce al tramonto', cluster: 'regole', stato: 'fermo' },
        { id: 'fatto:k1', tipo: 'fatto', nome: 'casa', cluster: 'conoscenza', stato: 'attivo' },
        { id: 'argomento:casa', tipo: 'argomento', nome: 'casa', cluster: 'conoscenza' },
    ],
    collegamenti: [
        { da: 'alias:a1', a: 'dispositivo:light.cucina', tipo: 'chiama' },
        { da: 'dispositivo:light.cucina', a: 'stanza:cucina', tipo: 'sta_in' },
        { da: 'regola:r1', a: 'dispositivo:light.cucina', tipo: 'comanda' },
        { da: 'routine:m1', a: 'dispositivo:light.sala', tipo: 'comanda' },
        { da: 'fatto:k1', a: 'argomento:casa', tipo: 'riguarda' },
    ],
    clusters: [
        { id: 'stanze', nome: 'Stanze', nodi: 1, nascosti: 0 },
        { id: 'routine', nome: 'Routine', nodi: 1, nascosti: 0 },
        { id: 'regole', nome: 'Regole', nodi: 1, nascosti: 0 },
        { id: 'dispositivi', nome: 'Dispositivi', nodi: 2, nascosti: 0 },
        { id: 'alias', nome: 'Alias', nodi: 1, nascosti: 0 },
        { id: 'conoscenza', nome: 'Conoscenza', nodi: 2, nascosti: 0 },
    ],
    sistemi: [
        {
            id: 'home_assistant',
            nome: 'Home Assistant',
            cluster: 'dispositivi',
            stato: 'non_raggiungibile',
            motivo: 'Il canale degli eventi non e connesso.',
        },
        {
            id: 'regole',
            nome: 'Regole',
            cluster: 'regole',
            stato: 'fermo',
            motivo: 'Regole disattivate: Luce al tramonto.',
        },
        { id: 'notizie', nome: 'Notizie', cluster: 'strumenti', stato: 'attivo', motivo: '' },
    ],
    contatori: { nodi: 8, collegamenti: 5, sistemi: 3, sistemi_attivi: 1, agenti_pronti: 0 },
    troncato: false,
};

async function apri(page, risposta = { status: 200, body: GRAFO }) {
    await page.route('**/api/cervello', (route) =>
        route.fulfill({
            status: risposta.status,
            contentType: 'application/json',
            body: JSON.stringify(risposta.body),
        }),
    );
    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
}

const visibili = (page) => page.locator('#cervello-canvas').getAttribute('data-nodi-visibili');

test.describe('il Cervello', () => {
    test('mostra i contatori, i nodi e lo stato dei sistemi', async ({ page }) => {
        await apri(page);

        await expect(page.locator('#cv-nodi')).toHaveText('8');
        await expect(page.locator('#cv-collegamenti')).toHaveText('5');
        await expect(page.locator('#cv-sistemi')).toHaveText('1/3');
        await expect.poll(() => visibili(page)).toBe('8');

        const sistemi = page.locator('#cervello-sistemi');
        await expect(sistemi).toContainText('Non raggiungibile');
        await expect(sistemi).toContainText('Fermo');
        await expect(sistemi).toContainText('Regole disattivate: Luce al tramonto.');
    });

    test('il nome di un nodo resta testo, anche se e markup', async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');

        // L'elenco in chiaro e il dettaglio scrivono il nome nella pagina: l'unico posto in cui potrebbe diventare codice.
        await page.locator('#cervello-elenco-box summary').click();
        const bottone = page.locator('#cervello-elenco button', { hasText: 'lampada' });
        await expect(bottone).toHaveCount(1);
        await expect(bottone).toContainText('<img src=x onerror=');
        await bottone.click();
        await expect(page.locator('#cervello-dettaglio')).toContainText('<img src=x onerror=');

        expect(
            await page.evaluate(() => window.__rubato),
            'il nome di un dispositivo ha eseguito codice',
        ).toBeUndefined();
        expect(await page.locator('#cervello-elenco img, #cervello-dettaglio img').count()).toBe(0);
    });

    test("un nodo si sceglie dall'elenco e il dettaglio dice a cosa e collegato", async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');

        await page.locator('#cervello-elenco-box summary').click();
        await page.locator('#cervello-elenco button', { hasText: 'Cinema' }).click();

        const dettaglio = page.locator('#cervello-dettaglio');
        await expect(dettaglio).toContainText('Cinema');
        await expect(dettaglio).toContainText('Routine');
        await expect(dettaglio).toContainText('Collegato a (1)');
        await expect(page.locator('#cervello-annuncio')).toHaveText('Routine: Cinema');
    });

    test('con la tastiera ci si sposta fra i nodi e Invio apre', async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');

        await page.locator('#cervello-canvas').focus();
        await page.keyboard.press('ArrowRight');
        // La prima freccia sceglie un nodo: l'annuncio smette di dire «nessuno».
        await expect(page.locator('#cervello-annuncio')).not.toHaveText('Nessun nodo selezionato');
        await expect(page.locator('#cervello-annuncio')).not.toHaveText('');

        // Si sceglie la routine dall'elenco per sapere cosa aprire: Invio la porta all'editor.
        await page.locator('#cervello-elenco-box summary').click();
        await page.locator('#cervello-elenco button', { hasText: 'Cinema' }).click();
        await page.locator('#cervello-canvas').focus();
        await page.keyboard.press('Enter');
        await expect(page.locator('#flow-canvas')).toBeVisible();
    });

    test('Esc toglie la selezione', async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');
        await page.locator('#cervello-elenco-box summary').click();
        await page.locator('#cervello-elenco button', { hasText: 'Cinema' }).click();
        await page.locator('#cervello-canvas').focus();
        await page.keyboard.press('Escape');

        await expect(page.locator('#cervello-annuncio')).toHaveText('Nessun nodo selezionato');
    });

    test('nascondere un tipo toglie i suoi nodi, e mostrarlo li riporta', async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');

        const casella = page.locator('#cervello-legenda label', { hasText: 'Conoscenza' }).locator('input');
        await casella.uncheck();
        await expect.poll(() => visibili(page)).toBe('6');

        await casella.check();
        await expect.poll(() => visibili(page)).toBe('8');
    });

    test('la ricerca non cambia quanti nodi ci sono, ne attenua il resto', async ({ page }) => {
        await apri(page);
        await expect.poll(() => visibili(page)).toBe('8');

        await page.locator('#cervello-cerca').fill('cinema');

        // Il numero dei nodi non cambia: la ricerca evidenzia, non filtra (per filtrare c'e' la legenda).
        expect(await visibili(page)).toBe('8');
    });

    test('senza niente da mostrare insegna la mossa successiva', async ({ page }) => {
        await apri(page, {
            status: 200,
            body: {
                ...GRAFO,
                nodi: [],
                collegamenti: [],
                clusters: [],
                sistemi: [],
                contatori: { nodi: 0, collegamenti: 0, sistemi: 0, sistemi_attivi: 0, agenti_pronti: 0 },
            },
        });

        await expect(page.locator('#cervello-vuoto')).toBeVisible();
        await expect(page.locator('#cervello-vuoto')).toContainText('Dai un nome ai dispositivi');
    });

    test('un permesso che manca si dice, non si nasconde', async ({ page }) => {
        await apri(page, { status: 403, body: { detail: 'no' } });

        await expect(page.locator('#cervello-errore')).toBeVisible();
        await expect(page.locator('#cervello-errore-testo')).toContainText('permesso');
    });

    test('si raggiunge dal menu Configurazione, che non diventa un quarto ingresso', async ({ page }) => {
        await page.route('**/api/cervello', (route) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GRAFO) }),
        );
        await page.goto('/index.html');
        await page.locator('#tab-btn-configurazione').click();
        await page.locator('#menu-configurazione [data-testo="cervello"]').click();

        await expect(page.locator('#tab-cervello')).toBeVisible();
        // Il pulsante di primo livello che si accende e' quello di Configurazione: da li' si e' passati.
        await expect(page.locator('#tab-btn-configurazione')).toHaveClass(/text-indigo-300/);
        expect(await page.locator('.tab-btn[data-gesto="switchTab"]').count()).toBe(3);
    });
});
