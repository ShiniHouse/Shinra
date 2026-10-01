// Controlla che `web/static/css/tailwind.css` sia quello che Tailwind produrrebbe adesso.
//
// Il file e' generato e committato. Se qualcuno cambia una classe in un template o in un
// copione e non lo rigenera, la pagina perde quello stile senza nessun errore: la classe c'e'
// nel sorgente, e non nel CSS. Qui si rigenera in un file temporaneo e si confronta.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const COMMITTATO = 'web/static/css/tailwind.css';
const cartella = mkdtempSync(join(tmpdir(), 'shinra-tailwind-'));
const generato = join(cartella, 'tailwind.css');

try {
    execFileSync(
        process.execPath,
        [
            'node_modules/tailwindcss/lib/cli.js',
            '-c',
            'tailwind.config.js',
            '-i',
            'web/tailwind.ingresso.css',
            '-o',
            generato,
            '--minify',
        ],
        { stdio: 'pipe' },
    );
    const atteso = readFileSync(generato, 'utf8');
    const attuale = readFileSync(COMMITTATO, 'utf8');
    if (atteso !== attuale) {
        console.error(
            `${COMMITTATO} non e' aggiornato: hai cambiato delle classi? Esegui \`npm run css\` e includi il file nella modifica.`,
        );
        process.exit(1);
    }
    console.log(`${COMMITTATO} e' aggiornato.`);
} finally {
    rmSync(cartella, { recursive: true, force: true });
}
