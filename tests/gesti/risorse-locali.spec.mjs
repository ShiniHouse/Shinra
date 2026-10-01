// Cosa chiede la pagina al mondo, e cosa ottiene dal nostro server.
//
// La dashboard di casa non deve mandare richieste a terzi per disegnarsi: ogni richiesta
// esterna dice a qualcuno che la dashboard e' aperta, e quel qualcuno puo' cambiarne il
// comportamento. Qui si apre la pagina e si guarda cosa chiede davvero.

import { test, expect } from '@playwright/test';

// Nessun host esterno ammesso: la pagina si disegna con quello che il nostro server le da'.
const ANCORA_ESTERNI = [];

test.describe('le risorse della pagina', () => {
    test('i caratteri e le icone vengono dal nostro server, non da terzi', async ({ page }) => {
        const esterne = [];
        const locali = [];
        page.on('request', (richiesta) => {
            const url = new URL(richiesta.url());
            if (url.hostname === '127.0.0.1' || url.hostname === 'localhost') locali.push(url.pathname);
            else if (!url.protocol.startsWith('data') && !url.protocol.startsWith('blob'))
                esterne.push(url.hostname);
        });

        await page.goto('/index.html');
        await page.evaluate(() => document.fonts.ready);

        const inattese = [...new Set(esterne)].filter((host) => !ANCORA_ESTERNI.includes(host));
        expect(inattese, `la pagina chiede a terzi: ${inattese.join(', ')}`).toEqual([]);

        expect(
            locali.some((p) => p.includes('/static/vendor/lucide-')),
            'lucide non arriva dal server',
        ).toBe(true);
        expect(
            locali.some((p) => p.includes('/static/fonts/plus-jakarta-sans-latin-wght-normal.woff2')),
            'il carattere principale non arriva dal server',
        ).toBe(true);
    });

    test('il carattere della pagina e quello vero, non un ripiego di sistema', async ({ page }) => {
        await page.goto('/index.html');
        await page.evaluate(() => document.fonts.ready);

        const caricato = await page.evaluate(() =>
            [...document.fonts].some(
                (f) => f.family.replace(/"/g, '') === 'Plus Jakarta Sans' && f.status === 'loaded',
            ),
        );
        expect(caricato, 'Plus Jakarta Sans non risulta caricato').toBe(true);

        const mono = await page.evaluate(() => document.fonts.check('500 12px "JetBrains Mono"'));
        expect(mono).toBe(true);
    });
});
