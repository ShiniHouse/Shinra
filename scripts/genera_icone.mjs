// Rifa le icone PNG dall'SVG, con un browser vero (Playwright e' gia' fra gli attrezzi del frontend).
//
//   node scripts/genera_icone.mjs
//
// `web/static/favicon.svg` e' la fonte: il PNG normale e' quella forma con gli angoli tondi su fondo trasparente. `web/static/icons/
// maschera.svg` e' la stessa cosa a tutto campo, per le icone «maskable» (il sistema le ritaglia: il disegno sta nella parte
// centrale). Con `PLAYWRIGHT_CHANNEL=chrome` usa il Chrome installato invece del Chromium di Playwright.
import { chromium } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';

const ICONE = [
    ['web/static/favicon.svg', 'web/static/icons/icon-192.png', 192],
    ['web/static/favicon.svg', 'web/static/icons/icon-512.png', 512],
    ['web/static/favicon.svg', 'web/static/icons/apple-touch-icon.png', 180],
    ['web/static/icons/maschera.svg', 'web/static/icons/icon-maskable-192.png', 192],
    ['web/static/icons/maschera.svg', 'web/static/icons/icon-maskable-512.png', 512],
];

const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
for (const [sorgente, destinazione, lato] of ICONE) {
    const svg = readFileSync(sorgente, 'utf8').replace(/ width="64" height="64"/, ` width="${lato}" height="${lato}"`);
    const pagina = await browser.newPage({ viewport: { width: lato, height: lato } });
    await pagina.setContent(`<body style="margin:0;background:transparent">${svg}</body>`);
    const png = await pagina.screenshot({ omitBackground: true, clip: { x: 0, y: 0, width: lato, height: lato } });
    writeFileSync(destinazione, png);
    await pagina.close();
    console.log(`${destinazione} (${lato}px)`);
}
await browser.close();
