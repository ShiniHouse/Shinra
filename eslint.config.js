// Configurazione di ESLint per il frontend (issue #34).
//
// I file sotto `web/static/js/` sono moduli ES: ognuno dichiara `import` e
// `export` per quello che condivide, e ESLint lo vede file per file — un
// nome che non e' ne' locale, ne' importato, ne' del browser e' un errore,
// e non serve piu' un elenco dei "nostri nomi globali" costruito leggendo
// gli altri file. Quell'elenco era il ponteggio dei copioni classici: lo
// spazio globale come contenitore, e una regola per fingere che fosse
// dichiarato.
//
// Due regole fanno il lavoro che prima non si poteva fare:
//
//   - `no-import-assign`: un'area non puo' piu' riassegnare una variabile
//     di un'altra. Lo stato che attraversa le aree sta in `Stato`, e una
//     riassegnazione cross-file e' l'errore che il contenitore esiste per
//     impedire.
//   - `no-unused-vars` anche sui nomi di primo livello: una funzione che
//     nessuno importa, registra o chiama e' codice morto, e lo si vede.

import globals from 'globals';

const CARTELLA = 'web/static/js';

const REGOLE = {
    // Le tre che trovano i guasti veri di questa pagina.
    'no-undef': 'error',
    'no-redeclare': 'error',
    'no-dupe-keys': 'error',

    'no-dupe-args': 'error',
    'no-dupe-else-if': 'error',
    'no-duplicate-case': 'error',
    'no-unsafe-negation': 'error',
    'no-unreachable': 'error',
    'no-self-assign': 'error',
    'no-constant-condition': ['error', { checkLoops: false }],
    'no-fallthrough': 'error',
    'no-cond-assign': 'error',
    'valid-typeof': 'error',
    'use-isnan': 'error',
    'no-sparse-arrays': 'error',
    'no-func-assign': 'error',
    'no-import-assign': 'error',

    'no-unused-vars': ['warn', { args: 'none' }],
};

const AMBIENTE = {
    ...globals.browser,
    // Caricate dalla pagina prima dei nostri copioni.
    lucide: 'readonly',
    tailwind: 'readonly',
};

export default [
    {
        files: [`${CARTELLA}/*.js`],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: AMBIENTE,
        },
        rules: REGOLE,
    },
    {
        // La configurazione e il banco dei gesti: moduli ES che girano in
        // node. Dentro un `page.evaluate()` il codice gira nel browser e
        // importa i moduli della dashboard con `import('/static/js/...')`.
        files: ['eslint.config.js', 'playwright.config.mjs', 'tests/gesti/*.mjs'],
        languageOptions: {
            ecmaVersion: 2022,
            sourceType: 'module',
            globals: { ...globals.node, ...globals.browser },
        },
        rules: {
            'no-undef': 'error',
            'no-unused-vars': ['warn', { args: 'none' }],
        },
    },
];
