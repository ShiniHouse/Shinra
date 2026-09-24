// I gesti, chiesti a un browser vero.
//
// Issue #34, ADR 0006. Fino alla #179 il markup eseguiva stringhe:
// `onclick="switchTab('console')"`. Adesso nomina un gesto — `data-gesto` —
// e ad ascoltare c'e' un guardiano solo su `document`.
//
// Le guardie che leggono il sorgente sanno dire che il nome e' registrato e
// che l'attributo e' scritto giusto. Non sanno dire se **il clic arriva**:
// la delega passa per la risalita dell'evento, e basta un `stopPropagation`
// per strada, o un ascolto registrato nell'ordine sbagliato, perche' un
// pulsante smetta di fare qualcosa senza un errore in console.
//
// E' la stessa ragione della #156, che ha portato in CI i gesti dell'editor:
// un test che legge il sorgente non sa se un clic arriva o se se lo mangia
// un antenato.

import { test, expect } from '@playwright/test';

/**
 * Quale scheda e' accesa. `switchTab` lavora **solo** su `style.display` e
 * non tocca la classe `hidden` del markup — c'e' scritto anche nel suo
 * commento, «evita conflitti Tailwind JIT». Una prima versione di questo
 * aiutante chiedeva anche che `hidden` non ci fosse, e non trovava mai
 * nessuna scheda accesa.
 */
async function schedaAccesa(page) {
    return page.evaluate(() =>
        [...document.querySelectorAll('.tab-content')]
            .filter((s) => s.style.display !== 'none')
            .map((s) => s.id),
    );
}

test.describe('i gesti delegati', () => {
    test('un pulsante della barra cambia scheda', async ({ page }) => {
        await page.goto('/index.html');

        await page.locator('#tab-btn-aliases').click();
        expect(await schedaAccesa(page), 'il clic sulla barra non ha cambiato scheda').toEqual([
            'tab-aliases',
        ]);

        await page.locator('#tab-btn-console').click();
        expect(await schedaAccesa(page)).toEqual(['tab-console']);
    });

    test("il clic sull'icona dentro il pulsante vale come sul pulsante", async ({ page }) => {
        // Non e' un dettaglio: ogni pulsante della barra contiene una `<i>`,
        // ed e' quella che si preme davvero. Con `onclick` funzionava perche'
        // l'attributo stava sull'antenato; con la delega funziona solo se
        // chi ascolta risale con `closest`, e dimenticarlo vorrebbe dire una
        // barra che reagisce solo se si prende il pulsante per il bordo.
        await page.goto('/index.html');

        // Il figlio si prende come figlio e non per tag: nel markup e' una
        // `<i data-lucide>`, ma lucide la **sostituisce** con un `<svg>`
        // appena arriva dal suo CDN. Cercare `i` funziona solo dove quel CDN
        // non risponde, ed e' esattamente il rosso con cui questa prova e'
        // nata: verde in locale, in attesa per trenta secondi in CI.
        //
        // E `dispatchEvent` invece di `click()`: finche' lucide non e'
        // arrivata l'icona non ha dimensioni e nessuno «puo' premerla». Qui
        // non si prova la mira del browser — si prova che un evento il cui
        // bersaglio e' un figlio arrivi lo stesso al gesto dell'antenato,
        // cioe' il `closest`.
        await page.locator('#tab-btn-automazioni > *').first().dispatchEvent('click');
        expect(await schedaAccesa(page), "premere l'icona non ha fatto niente").toEqual(['tab-automazioni']);
    });

    test('il menu di configurazione si apre e non si richiude da solo', async ({ page }) => {
        // Il caso delicato della delega. `alternaMenuConfigurazione` chiama
        // `stopPropagation` per non farsi chiudere dal guardiano del
        // «clic fuori», che sta anche lui su `document`: fra due ascolti
        // sullo **stesso** nodo, `stopPropagation` non ferma niente.
        //
        // Regge lo stesso, perche' quel guardiano controlla anche
        // `bottone.contains(evento.target)`. Ma regge per quella ragione li',
        // e una ragione che nessuno prova e' una ragione che si perde.
        await page.goto('/index.html');

        // Si guarda la classe e non la visibilita': `hidden` fa sparire il
        // menu solo se il foglio di Tailwind e' arrivato dal suo CDN, e
        // questo test parla di cosa fa il nostro codice, non di cosa il
        // browser e' riuscito a scaricare.
        const menu = page.locator('#menu-configurazione');

        await page.locator('#tab-btn-configurazione').click();
        await expect(menu, "il menu si e' chiuso nello stesso istante in cui si e' aperto").not.toHaveClass(
            /\bhidden\b/,
        );

        // E da fuori si chiude davvero.
        await page.locator('main').click({ position: { x: 5, y: 5 } });
        await expect(menu, 'il menu resta aperto anche premendo fuori').toHaveClass(/\bhidden\b/);
    });

    test('una tavolozza si sceglie e la pagina cambia colore', async ({ page }) => {
        // Un gesto con un argomento scritto nel markup — `data-testo` — e un
        // effetto che si vede nel DOM invece che in una variabile.
        // Le tavolozze stanno in Impostazioni: la scheda va aperta, o il
        // pulsante c'e' ma non si puo' premere.
        await page.goto('/index.html?scheda=settings');
        await page.locator('#tab-settings').waitFor({ state: 'visible' });

        const prima = await page.evaluate(() => document.documentElement.dataset.palette || '');
        const bottone = page.locator('[data-gesto="setPalette"][data-testo="aurora"]');
        await bottone.scrollIntoViewIfNeeded();
        await bottone.click();
        const dopo = await page.evaluate(() => document.documentElement.dataset.palette || '');

        expect(dopo, `la tavolozza e' rimasta «${prima}»`).toBe('aurora');
    });

    test('nessun gesto resta senza chi lo sappia fare', async ({ page }) => {
        // Il guardiano stampa in console quando gli chiedono un nome che non
        // conosce. Qui si preme tutto quello che la pagina offre e si guarda
        // che non lo dica mai — che e' il modo di scoprire una registrazione
        // dimenticata senza doverla cercare a mano.
        const lamentele = [];
        page.on('console', (m) => {
            if (m.type() === 'error' && m.text().startsWith('Gesti:')) lamentele.push(m.text());
        });

        await page.goto('/index.html');

        const nomi = await page.evaluate(() =>
            [...document.querySelectorAll('[data-gesto]')].map((e) => e.dataset.gesto),
        );
        expect(nomi.length, "la pagina non chiede piu' nessun gesto").toBeGreaterThan(30);

        const sconosciuti = await page.evaluate((elenco) => elenco.filter((n) => !Gesti.conosce(n)), nomi);
        expect(sconosciuti, 'gesti che il markup chiede e nessuna area registra').toEqual([]);
        expect(lamentele, "il guardiano si e' lamentato al caricamento").toEqual([]);
    });
});
