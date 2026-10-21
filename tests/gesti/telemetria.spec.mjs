// La pillola «CPU 31%» nell'intestazione: i numeri di `/api/telemetria`, accanto a Ollama e Home Assistant.
//
// Il server e' finto. Si prova cio' che nel sorgente non si vede: che i numeri arrivano alla pillola, che il colore segue il valore
// piu' alto e che dove il server non puo' leggere i propri numeri la pillola non compare.

import { test, expect } from '@playwright/test';

const SERVER = {
    disponibile: true,
    cpu: 31,
    memoria: { percentuale: 75, usata_mb: 5859, totale_mb: 7812 },
    disco: { percentuale: 92, libero_gb: 12.4 },
    carico: 0.5,
    temperatura_c: 47.5,
};

async function apri(page, corpo, stato = 200) {
    await page.route('**/api/telemetria', (route) =>
        route.fulfill({ status: stato, contentType: 'application/json', body: JSON.stringify(corpo) }),
    );
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
}

test.describe('la pillola del server', () => {
    test('mostra la CPU, e il suggerimento dice il resto; il colore segue il valore piu alto', async ({
        page,
    }) => {
        await apri(page, SERVER);
        const pillola = page.locator('#server-chip');
        await expect(pillola).toBeVisible();
        await expect(page.locator('#server-testo')).toHaveText('CPU 31%');
        await expect(pillola).toHaveAttribute(
            'title',
            'Il server: Processore 31% · Memoria 75% · Disco 92% (12.4 GB liberi) · Temperatura 48°C',
        );
        // Il disco al 92% e il valore piu alto: la pillola e rossa anche se la CPU e tranquilla.
        await expect(pillola).toHaveAttribute('data-livello', 'alto');
    });

    test('anche il menu del telefono ha la sua pillola, con tutti i numeri', async ({ page }) => {
        await apri(page, SERVER);
        const nelMenu = page.locator('#mobile-menu-drawer [data-server-chip]');
        await expect(nelMenu).toHaveCount(1);
        await expect(nelMenu.locator('[data-server-testo]')).toHaveText(
            'Processore 31% · Memoria 75% · Disco 92% (12.4 GB liberi) · Temperatura 48°C',
        );
    });

    test('con tutto basso il livello e basso', async ({ page }) => {
        await apri(page, {
            ...SERVER,
            disco: { percentuale: 40, libero_gb: 80 },
            memoria: { percentuale: 30 },
        });
        await expect(page.locator('#server-chip')).toHaveAttribute('data-livello', 'basso');
    });

    test('se il server non puo leggere i propri numeri la pillola non compare', async ({ page }) => {
        await apri(page, { disponibile: false });
        await expect(page.locator('#server-chip')).toBeHidden();
    });

    test('se la richiesta fallisce la pillola resta nascosta, senza errori in faccia', async ({ page }) => {
        await apri(page, {}, 500);
        await expect(page.locator('#server-chip')).toBeHidden();
    });
});
