// Il colore che si vede nel primo istante, chiesto a un browser vero.
//
// Issue #152. Il tema veniva deciso da `initTheme()`, che gira dentro
// `window.addEventListener('load', ...)`: dopo i ventuno copioni, Tailwind,
// lucide e i caratteri di Google. Fino a quel momento valeva il `class="dark"`
// scritto sul tag `<html>`, e la pagina era scura anche a mezzogiorno.
//
// Misurato in locale: 640 ms. In casa, con un CDN lento, sono secondi — ed e'
// cosi' che sono nati gli scatti da cui e' partita la #152: sei schede su otto
// fotografate in quella finestra sembravano un difetto del tema chiaro.
//
// Nessuna guardia che legge il sorgente puo' vedere questo, perche' nel
// sorgente e' tutto scritto giusto: il difetto sta nel **quando**.

import { test, expect } from '@playwright/test';

/** Chiaro sul serio: i tre canali alti e vicini fra loro. */
function eChiaro(colore) {
    const [r, v, b] = colore.match(/\d+/g).map(Number);
    return r > 200 && v > 200 && b > 200;
}

/**
 * Trattiene i copioni per due secondi, come farebbe una rete lenta.
 * Senza questo il test non prova niente: in locale i file arrivano subito
 * e la finestra scura e' troppo stretta perche' qualcuno la veda.
 */
async function conICopioniLenti(page) {
    await page.route('**/static/js/*.js', async (rotta) => {
        await new Promise((r) => setTimeout(r, 2000));
        await rotta.continue();
    });
}

test.describe('il tema al primo pixel', () => {
    test('di giorno la pagina nasce chiara, prima che i copioni arrivino', async ({ page }) => {
        await conICopioniLenti(page);
        await page.goto('/index.html?tema=light', { waitUntil: 'domcontentloaded' });

        const classe = await page.evaluate(() => document.documentElement.className);
        expect(classe, "il tag <html> e' ancora scuro quando la pagina si disegna").toContain('light');

        const fondo = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        expect(
            eChiaro(fondo),
            `il fondo della pagina e' ${fondo} mentre i copioni devono ancora arrivare: ` +
                'chi apre la dashboard di giorno vede una schermata scura che poi cambia colore',
        ).toBe(true);
    });

    test('di notte resta scura, e nessuno la sbianca per un istante', async ({ page }) => {
        await conICopioniLenti(page);
        await page.goto('/index.html?tema=dark', { waitUntil: 'domcontentloaded' });

        const classe = await page.evaluate(() => document.documentElement.className);
        expect(classe).toContain('dark');
        expect(classe).not.toContain('light');

        const fondo = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        expect(eChiaro(fondo), `di notte il fondo e' ${fondo}`).toBe(false);
    });

    test('a copioni arrivati il tema non cambia piu', async ({ page }) => {
        await page.goto('/index.html?tema=light');
        await page.waitForFunction(() => getComputedStyle(document.body).display === 'flex', null, {
            timeout: 15_000,
        });
        // `initTheme()` gira su `load` e ridecide: deve ridecidere uguale.
        await page.waitForTimeout(1500);

        const dopo = await page.evaluate(() => ({
            classe: document.documentElement.className,
            fondo: getComputedStyle(document.body).backgroundColor,
        }));
        expect(dopo.classe).toContain('light');
        expect(eChiaro(dopo.fondo), `a pagina caricata il fondo e' ${dopo.fondo}`).toBe(true);
    });
});
