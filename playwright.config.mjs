// I test dei gesti: un browser vero che preme i pulsanti della
// dashboard e guarda cosa succede. Vedi tests/gesti/ per il perche'.
//
// La pagina viene servita statica da `.anteprima/`, preparata da
// `scripts/anteprima.py`. Tailwind e lucide arrivano dai loro CDN come
// in casa: il disegno e' quello vero, ed e' il punto — questi test
// esistono per i difetti che nel sorgente non si vedono.

import { defineConfig, devices } from '@playwright/test';

const PORTA = 8899;

export default defineConfig({
    testDir: './tests/gesti',
    // In CI nessun `.only` dimenticato, e nessun tentativo ripetuto che
    // trasformi un difetto vero in un test che "ogni tanto passa".
    forbidOnly: !!process.env.CI,
    retries: 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: process.env.CI ? 'list' : 'line',
    timeout: 30_000,
    expect: { timeout: 7_000 },

    use: {
        baseURL: `http://127.0.0.1:${PORTA}`,
        viewport: { width: 1400, height: 900 },
        trace: 'retain-on-failure',
    },

    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],

    // Prima prepara la copia statica, poi la serve. `python3 -m http.server`
    // basta: non c'e' niente da eseguire lato server.
    webServer: {
        command: `python scripts/anteprima.py && python -m http.server ${PORTA} --directory .anteprima --bind 127.0.0.1`,
        url: `http://127.0.0.1:${PORTA}/index.html`,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
    },
});
