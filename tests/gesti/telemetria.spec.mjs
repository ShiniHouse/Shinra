// «Il server» nella console: tre barre e la temperatura, dai numeri di `/api/telemetria`.
//
// Il server e' finto. Si prova cio' che nel sorgente non si vede: che i numeri arrivano alle barre, che il colore segue il carico
// e che dove il server non puo' leggere i propri numeri il pannello non compare.

import { test, expect } from '@playwright/test';

const SERVER = {
    disponibile: true,
    cpu: 31,
    memoria: { percentuale: 75, usata_mb: 5859, totale_mb: 7812 },
    disco: { percentuale: 92, libero_gb: 12.4 },
    carico: 0.5,
    temperatura_c: 47.5,
};

async function apri(page, corpo) {
    await page.route('**/api/telemetria', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(corpo) }),
    );
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
}

test.describe('il pannello del server', () => {
    test('mostra le barre, la temperatura, e il colore segue il carico', async ({ page }) => {
        await apri(page, SERVER);
        await expect(page.locator('#pannello-server')).toBeVisible();
        await expect(page.locator('#server-cpu-valore')).toHaveText('31%');
        await expect(page.locator('#server-memoria-valore')).toHaveText('75%');
        await expect(page.locator('#server-disco-valore')).toHaveText('92% · 12.4 GB liberi');
        await expect(page.locator('#server-temperatura')).toHaveText('48°C');
        await expect(page.locator('#server-cpu')).toHaveAttribute('data-livello', 'basso');
        await expect(page.locator('#server-memoria')).toHaveAttribute('data-livello', 'medio');
        await expect(page.locator('#server-disco')).toHaveAttribute('data-livello', 'alto');
        await expect(page.locator('#server-disco')).toHaveCSS('width', /^[1-9]/);
    });

    test("se il server non puo' leggere i propri numeri il pannello non compare", async ({ page }) => {
        await apri(page, { disponibile: false });
        await expect(page.locator('#pannello-server')).toBeHidden();
    });

    test('se la richiesta fallisce il pannello resta nascosto, senza errori in faccia', async ({ page }) => {
        await page.route('**/api/telemetria', (route) => route.fulfill({ status: 500, body: '{}' }));
        await page.goto('/index.html');
        await page.waitForLoadState('networkidle');
        await expect(page.locator('#pannello-server')).toBeHidden();
    });
});
