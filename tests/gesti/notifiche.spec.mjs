// Le notifiche push dal dispositivo (issue #29).
//
// Il server le sapeva mandare, ma nessuna interfaccia iscriveva un dispositivo: il Cervello diceva «Notifiche push:
// fermo». Qui si prova la sezione di Impostazioni → Notifiche con un browser vero, ma **senza un servizio push vero**:
// `PushManager.subscribe()` ha bisogno di una connessione ai server di Google o Mozilla, che in CI non c'e'. Il
// service worker e il permesso si fingono; cio' che si prova e' cosa fa la *pagina* con le risposte — quali stati
// mostra, cosa manda al server, e che il permesso si chieda dentro il clic.

import { test, expect } from '@playwright/test';

const ENDPOINT = 'https://push.finto.example/abc123';

// Un'iscrizione e un service worker finti, prima che la pagina parta.
function falsifica() {
    return ({ permesso, conPushManager, iscritto, endpoint, readyMai }) => {
        window.__richieste_permesso = 0;
        window.__subscribe = 0;
        window.__unsubscribe = 0;
        let iscrizione = iscritto
            ? {
                  endpoint,
                  toJSON: () => ({ keys: { p256dh: 'chiave-p256dh', auth: 'chiave-auth' } }),
                  unsubscribe: async () => {
                      window.__unsubscribe += 1;
                      iscrizione = null;
                      return true;
                  },
              }
            : null;
        const registrazione = {
            pushManager: {
                getSubscription: async () => iscrizione,
                subscribe: async () => {
                    window.__subscribe += 1;
                    iscrizione = {
                        endpoint,
                        toJSON: () => ({ keys: { p256dh: 'chiave-p256dh', auth: 'chiave-auth' } }),
                        unsubscribe: async () => {
                            window.__unsubscribe += 1;
                            iscrizione = null;
                            return true;
                        },
                    };
                    return iscrizione;
                },
            },
        };
        Object.defineProperty(navigator.serviceWorker, 'ready', {
            get: () => (readyMai ? new Promise(() => {}) : Promise.resolve(registrazione)),
        });
        if (!conPushManager) delete window.PushManager;
        else window.PushManager = window.PushManager || function PushManager() {};
        const Falsa = function Notification() {};
        Falsa.permission = permesso;
        Falsa.requestPermission = async () => {
            window.__richieste_permesso += 1;
            Falsa.permission = 'granted';
            return 'granted';
        };
        window.Notification = Falsa;
    };
}

async function apri(
    page,
    { disponibile = true, dispositivi = [], opzioni = {}, rifiutaPreferenza = null } = {},
) {
    const visti = { sottoscrivi: [], dimentica: [], preferenze: [], prova: 0 };
    // Il server ricorda cio' che gli si consegna: un elenco fisso farebbe credere alla pagina di non essere iscritta.
    const elenco = [...dispositivi];
    await page.addInitScript(falsifica(), {
        permesso: 'default',
        conPushManager: true,
        iscritto: false,
        readyMai: false,
        ...opzioni,
        endpoint: ENDPOINT,
    });
    await page.route('**/api/notifiche/**', async (route) => {
        const richiesta = route.request();
        const percorso = new URL(richiesta.url()).pathname.replace('/api/notifiche/', '');
        const corpo = richiesta.postDataJSON?.() ?? null;
        const ok = (dati) =>
            route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(dati) });
        if (percorso === 'chiave')
            return ok({ chiave: disponibile ? 'BAAA-chiave_pubblica' : null, disponibile });
        if (percorso === 'dispositivi') return ok({ dispositivi: elenco });
        if (percorso === 'preferenze' && richiesta.method() === 'GET') {
            return ok({
                silenzioso: false,
                canali: { web: true, push: true, voce: false },
                categorie: {
                    sicurezza: true,
                    promemoria: true,
                    timer: true,
                    presenza: true,
                    energia: false,
                    manutenzione: true,
                },
                non_silenziabili: ['sicurezza'],
            });
        }
        if (percorso === 'preferenze') {
            visti.preferenze.push(corpo);
            if (rifiutaPreferenza && corpo.chiave === rifiutaPreferenza) {
                return route.fulfill({
                    status: 400,
                    contentType: 'application/json',
                    body: JSON.stringify({ detail: 'Non si può silenziare.' }),
                });
            }
            return ok({ success: true });
        }
        if (percorso === 'sottoscrivi') {
            visti.sottoscrivi.push(corpo);
            elenco.splice(0, elenco.length, { id: 'push_1', nome: corpo.nome, ultimo_invio: null });
            return ok({ success: true, sottoscrizione: { id: 'push_1', nome: corpo.nome } });
        }
        if (percorso === 'dimentica') {
            visti.dimentica.push(corpo);
            elenco.splice(0, elenco.length);
            return ok({ success: true });
        }
        if (percorso === 'prova') {
            visti.prova += 1;
            return ok({ success: true, inviate: 1 });
        }
        return route.fulfill({ status: 404, body: '{}' });
    });
    await page.goto('/index.html?scheda=settings');
    await page.locator('#tab-settings').waitFor({ state: 'visible' });
    await page.locator('details[data-sezione="notifiche"] summary').click();
    return visti;
}

const stato = (page) => page.locator('#notifiche-contenuto [data-stato]');

test.describe('le notifiche push', () => {
    test('da attivare: il clic chiede il permesso, iscrive il dispositivo e lo dice', async ({ page }) => {
        const visti = await apri(page);
        await expect(stato(page)).toHaveAttribute('data-stato', 'da_attivare');

        await page.getByRole('button', { name: 'Attiva le notifiche su questo dispositivo' }).click();

        await expect(stato(page)).toHaveAttribute('data-stato', 'attive');
        expect(await page.evaluate(() => window.__richieste_permesso)).toBe(1);
        expect(await page.evaluate(() => window.__subscribe)).toBe(1);
        expect(visti.sottoscrivi).toHaveLength(1);
        expect(visti.sottoscrivi[0]).toMatchObject({
            endpoint: ENDPOINT,
            p256dh: 'chiave-p256dh',
            auth: 'chiave-auth',
        });
        expect(visti.sottoscrivi[0].nome).toMatch(/·/);
    });

    test('attive: la prova parte, e disattivare toglie il dispositivo dal server e dal browser', async ({
        page,
    }) => {
        const visti = await apri(page, {
            opzioni: { permesso: 'granted', iscritto: true },
            dispositivi: [{ id: 'push_1', nome: 'iPhone · Safari', ultimo_invio: null }],
        });
        await expect(stato(page)).toHaveAttribute('data-stato', 'attive');
        await expect(page.locator('#notifiche-contenuto')).toContainText('iPhone · Safari');

        await page.getByRole('button', { name: 'Mandami una prova' }).click();
        await expect(page.locator('#notifiche-esito')).toContainText('Mandata');
        expect(visti.prova).toBe(1);

        await page.getByRole('button', { name: 'Disattiva su questo dispositivo' }).click();
        await expect(stato(page)).toHaveAttribute('data-stato', 'da_attivare');
        expect(visti.dimentica).toEqual([{ endpoint: ENDPOINT }]);
        expect(await page.evaluate(() => window.__unsubscribe)).toBe(1);
    });

    test("un'iscrizione che il browser ha e il server no si rimette a posto da sola", async ({ page }) => {
        const visti = await apri(page, { opzioni: { permesso: 'granted', iscritto: true }, dispositivi: [] });

        await expect(stato(page)).toHaveAttribute('data-stato', 'attive');
        await expect.poll(() => visti.sottoscrivi.length).toBe(1);
    });

    test('il server senza notifiche lo dice, invece di mostrare un pulsante che non fa niente', async ({
        page,
    }) => {
        await apri(page, { disponibile: false });

        await expect(stato(page)).toHaveAttribute('data-stato', 'server_senza_notifiche');
        await expect(page.getByRole('button', { name: /Attiva le notifiche/ })).toHaveCount(0);
    });

    test('con le notifiche bloccate nel browser lo dice e non chiede', async ({ page }) => {
        await apri(page, { opzioni: { permesso: 'denied' } });

        await expect(stato(page)).toHaveAttribute('data-stato', 'bloccate');
        await expect(page.getByRole('button', { name: /Attiva le notifiche/ })).toHaveCount(0);
    });

    test('un browser senza PushManager lo dice', async ({ page }) => {
        await apri(page, { opzioni: { conPushManager: false } });

        await expect(stato(page)).toHaveAttribute('data-stato', 'non_supportato');
    });

    test('le preferenze: una casella manda la chiave giusta, e quelle di sicurezza non si spengono', async ({
        page,
    }) => {
        const visti = await apri(page, { opzioni: { permesso: 'granted', iscritto: true } });
        await expect(stato(page)).toHaveAttribute('data-stato', 'attive');

        await page.getByLabel('Timer').uncheck();
        await expect.poll(() => visti.preferenze.length).toBe(1);
        expect(visti.preferenze[0]).toEqual({ chiave: 'categoria.timer', valore: false });

        await expect(page.getByLabel(/Sicurezza \(allarme, porte\)/)).toBeDisabled();
    });
});

test.describe('un service worker che non controlla la pagina', () => {
    // Era il difetto vero: il worker stava in /static/ e la pagina in /, quindi `serviceWorker.ready` non si
    // risolveva mai e la sezione restava su «Un momento…» su ogni dispositivo. Il test che fingeva il worker non
    // poteva vederlo: qui si finge proprio quel caso.
    test('la sezione lo dice invece di restare in attesa per sempre', async ({ page }) => {
        test.setTimeout(30_000);
        await apri(page, { opzioni: { readyMai: true } });

        await expect(stato(page)).toHaveAttribute('data-stato', 'errore', { timeout: 12_000 });
        await expect(page.locator('#notifiche-contenuto')).toContainText('service worker');
    });
});

test.describe('le notifiche su iPhone', () => {
    test.use({
        userAgent:
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
    });

    test("senza l'app sulla schermata Home spiega cosa fare", async ({ page }) => {
        await apri(page, { opzioni: { conPushManager: false } });

        await expect(stato(page)).toHaveAttribute('data-stato', 'ios_senza_app');
        await expect(page.locator('#notifiche-contenuto')).toContainText('Aggiungi a schermata Home');
    });
});
