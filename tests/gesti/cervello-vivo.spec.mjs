// Il grafo vivo: si illumina quando Shinra lavora (issue #189).
//
// Il server racconta il ciclo dell'agente con eventi `agente.*` su `/ws/eventi`. Qui il
// canale si finge — la pagina e' l'anteprima statica, senza server — e si guarda cosa
// fa la scheda: quali nodi si accendono, cosa scrive il registro in chiaro, se un
// errore resta, e se a grafo spento il disegno si ferma davvero.

import { test, expect } from '@playwright/test';

const GRAFO = {
    nodi: [
        {
            id: 'agente:modello',
            tipo: 'agente',
            nome: 'Modello (Ollama)',
            cluster: 'agenti',
            stato: 'attivo',
        },
        {
            id: 'strumento:comanda_tapparella',
            tipo: 'strumento',
            nome: 'comanda_tapparella',
            cluster: 'strumenti',
        },
        {
            id: 'dispositivo:cover.salotto',
            tipo: 'dispositivo',
            nome: 'tapparella salotto',
            cluster: 'dispositivi',
        },
        { id: 'stanza:salotto', tipo: 'stanza', nome: 'Salotto', cluster: 'stanze' },
        { id: 'fatto:k1', tipo: 'fatto', nome: 'casa', cluster: 'conoscenza', stato: 'attivo' },
    ],
    collegamenti: [
        { da: 'agente:modello', a: 'strumento:comanda_tapparella', tipo: 'usa' },
        { da: 'dispositivo:cover.salotto', a: 'stanza:salotto', tipo: 'sta_in' },
    ],
    clusters: [
        { id: 'agenti', nome: 'Agenti', nodi: 1, nascosti: 0 },
        { id: 'strumenti', nome: 'Strumenti', nodi: 1, nascosti: 0 },
        { id: 'dispositivi', nome: 'Dispositivi', nodi: 1, nascosti: 0 },
        { id: 'stanze', nome: 'Stanze', nodi: 1, nascosti: 0 },
        { id: 'conoscenza', nome: 'Conoscenza', nodi: 1, nascosti: 0 },
    ],
    sistemi: [],
    contatori: { nodi: 5, collegamenti: 2, sistemi: 0, sistemi_attivi: 0, agenti_pronti: 1 },
    troncato: false,
};

const evento = (tipo, dati) =>
    JSON.stringify({ tipo, dati: { richiesta: 'r1', ...dati }, momento: '2026-10-01T10:00:00Z', frase: '' });

// Apre la scheda con un canale degli eventi finto, e restituisce una funzione per mandare eventi.
async function apri(page) {
    let canale = null;
    await page.routeWebSocket('**/ws/eventi', (ws) => {
        canale = ws;
    });
    await page.route('**/api/cervello', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GRAFO) }),
    );
    await page.goto('/index.html?scheda=cervello');
    await page.locator('#tab-cervello').waitFor({ state: 'visible' });
    await expect.poll(() => page.locator('#cervello-canvas').getAttribute('data-nodi-visibili')).toBe('5');
    await expect
        .poll(() => canale !== null, { message: 'il canale degli eventi non si e aperto' })
        .toBe(true);
    return (tipo, dati) => canale.send(evento(tipo, dati));
}

const accesi = (page) => page.locator('#cervello-canvas').getAttribute('data-nodi-accesi');
const inErrore = (page) => page.locator('#cervello-canvas').getAttribute('data-nodi-in-errore');

test.describe('il grafo vivo', () => {
    test('una richiesta accende i nodi attesi, e il registro dice le stesse cose', async ({ page }) => {
        const manda = await apri(page);

        manda('agente.richiesta', { nodi: [] });
        manda('agente.richiesta', { nodi: ['agente:modello'], al_modello: true });
        manda('agente.skill', { nodi: ['strumento:comanda_tapparella'] });
        manda('agente.dispositivo', { nodi: ['dispositivo:cover.salotto'], riuscito: true });
        manda('agente.risposta', { nodi: ['agente:modello'] });

        await expect
            .poll(async () => (await accesi(page)).split(' ').sort())
            .toEqual(['agente:modello', 'dispositivo:cover.salotto', 'strumento:comanda_tapparella']);

        // Il registro in chiaro racconta lo stesso, con i nomi che si vedono nel grafo.
        const registro = page.locator('#cervello-registro');
        await expect(registro.locator('li')).toHaveCount(5);
        await expect(registro).toContainText('Richiesta ricevuta');
        await expect(registro).toContainText('Passata al modello');
        await expect(registro).toContainText('Strumento scelto: comanda_tapparella');
        await expect(registro).toContainText('Dispositivo comandato: tapparella salotto');
        await expect(registro).toContainText('Risposta data da Modello (Ollama)');
        expect(await inErrore(page)).toBe('');
    });

    test('un errore resta rosso piu a lungo di un nodo normale, e il registro lo dice', async ({ page }) => {
        const manda = await apri(page);

        manda('agente.skill', { nodi: ['strumento:comanda_tapparella'] });
        manda('agente.errore', {
            nodi: ['strumento:comanda_tapparella', 'dispositivo:cover.salotto'],
            motivo: 'strumento',
        });

        await expect.poll(() => inErrore(page)).toContain('strumento:comanda_tapparella');
        await expect(page.locator('#cervello-registro li.text-rose-300')).toContainText('Errore (strumento)');

        // Dopo la durata di un'accensione normale (4 s) l'errore c'e' ancora.
        await page.waitForTimeout(5000);
        expect(await inErrore(page)).toContain('strumento:comanda_tapparella');
    });

    test('senza eventi il grafo e fermo: nessun ciclo di disegno', async ({ page }) => {
        const manda = await apri(page);
        const canvas = page.locator('#cervello-canvas');

        // Il grafo si assesta, poi il ciclo si ferma e non riparte da solo.
        await expect.poll(() => canvas.getAttribute('data-animando'), { timeout: 15000 }).toBe('no');

        manda('agente.skill', { nodi: ['strumento:comanda_tapparella'] });
        await expect.poll(() => canvas.getAttribute('data-animando')).toBe('si');

        // Spenta l'accensione, il ciclo si ferma di nuovo.
        await expect.poll(() => accesi(page), { timeout: 10000 }).toBe('');
        await expect.poll(() => canvas.getAttribute('data-animando')).toBe('no');
    });

    test('con il movimento ridotto il nodo cambia solo colore: acceso, poi spento', async ({ page }) => {
        await page.emulateMedia({ reducedMotion: 'reduce' });
        const manda = await apri(page);

        manda('agente.skill', { nodi: ['strumento:comanda_tapparella'] });
        await expect.poll(() => accesi(page)).toBe('strumento:comanda_tapparella');
        // Nessun ciclo di animazione, mai.
        expect(await page.locator('#cervello-canvas').getAttribute('data-animando')).not.toBe('si');

        await expect.poll(() => accesi(page), { timeout: 10000 }).toBe('');
    });

    test('un evento di un nodo che il grafo non ha non rompe niente e finisce nel registro', async ({
        page,
    }) => {
        const manda = await apri(page);

        manda('agente.skill', { nodi: ['strumento:che_non_esiste'] });
        await expect(page.locator('#cervello-registro')).toContainText('Strumento scelto: che_non_esiste');
        await expect(page.locator('#cervello-canvas')).toBeVisible();
    });

    test('il nome nel registro resta testo, anche se e markup', async ({ page }) => {
        const manda = await apri(page);

        manda('agente.skill', { nodi: ['strumento:<img src=x onerror="window.__rubato=1">'] });
        await expect(page.locator('#cervello-registro')).toContainText('<img src=x onerror=');
        expect(await page.evaluate(() => window.__rubato)).toBeUndefined();
        expect(await page.locator('#cervello-registro img').count()).toBe(0);
    });
});
