// Il service worker mostra una notifica quando riceve un push (issue #29).
//
// Le prove di `notifiche.spec.mjs` fingono tutto il lato del browser. Questa no: carica il vero `sw.js`, gli
// consegna un messaggio con il protocollo di debug di Chromium (`ServiceWorker.deliverPushMessage`, lo stesso che
// usa il pulsante «Push» degli strumenti per sviluppatori) e guarda se compare la notifica. Non prova la rete: prova
// che, **se** il messaggio arriva, il worker lo sa mostrare, con il titolo e il testo giusti. Quando una notifica
// «non arriva», questa e' la prima meta' del percorso che si puo' escludere senza un telefono.

import { test, expect } from '@playwright/test';

// In CI gira `chromium-headless-shell`, che non sa mostrare notifiche: `getNotifications()` torna sempre vuoto, anche
// con un worker perfetto. Un test che li' fallisce sempre non dice niente: si prova in locale, con un browser vero
// (`channel: 'msedge'` o `'chrome'`), e in CI si salta dichiarandolo.
test.skip(!!process.env.CI, 'il browser senza testa di CI non mostra notifiche');

test('il worker mostra la notifica con il titolo e il testo del messaggio', async ({ page, context }) => {
    await context.grantPermissions(['notifications']);
    const client = await context.newCDPSession(page);
    await client.send('ServiceWorker.enable');
    let registrationId = null;
    client.on('ServiceWorker.workerRegistrationUpdated', (e) => {
        for (const r of e.registrations)
            if (r.scopeURL.includes('/static/')) registrationId = r.registrationId;
    });
    await page.goto('/index.html');
    await page.evaluate(async () => {
        const r = await navigator.serviceWorker.register('/static/sw.js');
        await new Promise((ok) => {
            const w = r.installing || r.waiting || r.active;
            if (w.state === 'activated') ok();
            else w.addEventListener('statechange', () => w.state === 'activated' && ok());
        });
    });
    await expect.poll(() => registrationId).not.toBeNull();
    await client.send('ServiceWorker.deliverPushMessage', {
        origin: new URL(page.url()).origin,
        registrationId,
        data: JSON.stringify({
            titolo: 'Prova',
            testo: 'Se leggi questo funziona',
            categoria: 'promemoria',
            priorita: 'importante',
            destinazione: '/',
        }),
    });
    await page.waitForTimeout(1500);
    const mostrate = await page.evaluate(async () => {
        const r = await navigator.serviceWorker.getRegistration('/static/');
        const n = await r.getNotifications();
        return n.map((x) => ({ titolo: x.title, testo: x.body, tag: x.tag }));
    });
    expect(mostrate).toEqual([{ titolo: 'Prova', testo: 'Se leggi questo funziona', tag: 'promemoria' }]);
});
