// Genera, o controlla, `web/static/css/tailwind.css`.
//
//   npm run css            riscrive il file
//   npm run css:verifica   fallisce se il file committato non e' quello che Tailwind produce adesso
//
// Il file e' generato e committato. Se qualcuno cambia una classe in un template o in un
// copione e non lo rigenera, la pagina perde quello stile senza nessun errore: la classe c'e'
// nel sorgente, e non nel CSS. Per questo la CI lo controlla.
//
// Il risultato di Tailwind viene chiuso con un a capo: e' una riga sola e senza, l'hook
// `end-of-file-fixer` dei ganci lo riscriverebbe a ogni commit, e il controllo qui sotto
// direbbe che non e' aggiornato.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const COMMITTATO = 'web/static/css/tailwind.css';
const verifica = process.argv.includes('--verifica');

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
    const atteso = readFileSync(generato, 'utf8').trimEnd() + '\n';

    if (!verifica) {
        writeFileSync(COMMITTATO, atteso);
        console.log(`${COMMITTATO} riscritto (${atteso.length} caratteri).`);
    } else if (atteso !== readFileSync(COMMITTATO, 'utf8')) {
        console.error(
            `${COMMITTATO} non e' aggiornato: hai cambiato delle classi? Esegui \`npm run css\` e includi il file nella modifica.`,
        );
        process.exit(1);
    } else {
        console.log(`${COMMITTATO} e' aggiornato.`);
    }
} finally {
    rmSync(cartella, { recursive: true, force: true });
}
