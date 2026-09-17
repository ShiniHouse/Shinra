// Configurazione di ESLint per il frontend (issue #34).
//
// I file sotto `web/static/js/` sono copioni normali, non moduli ES: la
// pagina chiama le funzioni dagli attributi `onclick`, che leggono solo lo
// spazio globale. Quindi ogni file dichiara i suoi nomi *in globale* e legge
// quelli dichiarati dagli altri.
//
// ESLint guarda un file per volta e non sa niente degli altri, percio' senza
// aiuto `no-undef` griderebbe su ogni chiamata fra un'area e l'altra. La
// soluzione non e' spegnere la regola — sarebbe spegnere l'unica che trova
// il refuso in un nome, cioe' il guasto che ha gia' ucciso questa pagina —
// ma dirgli quali sono i nostri nomi globali.
//
// L'elenco non si scrive a mano: si legge dai file. Un'area nuova entra il
// giorno che nasce, e un nome che nessuno dichiara piu' esce da solo. A ogni
// file diamo i nomi degli *altri*: i suoi li dichiara lui, e darglieli
// sarebbe una ridichiarazione.

import fs from "node:fs";
import path from "node:path";
import globals from "globals";

const CARTELLA = "web/static/js";

// `function nome(`, `const nome =`, `let nome =`, `var nome =` a colonna
// zero: sono le dichiarazioni che finiscono nello spazio globale. Quelle
// rientrate stanno dentro una funzione e non ci interessano.
const DICHIARAZIONE = /^(?:async\s+)?(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)/gm;

const dichiaratiDa = new Map();
for (const file of fs.readdirSync(CARTELLA).filter((f) => f.endsWith(".js"))) {
  const testo = fs.readFileSync(path.join(CARTELLA, file), "utf8");
  dichiaratiDa.set(file, [...testo.matchAll(DICHIARAZIONE)].map((t) => t[1]));
}

const REGOLE = {
  // Le tre che trovano i guasti veri di questa pagina.
  "no-undef": "error",
  "no-redeclare": "error",
  "no-dupe-keys": "error",

  "no-dupe-args": "error",
  "no-dupe-else-if": "error",
  "no-duplicate-case": "error",
  "no-unsafe-negation": "error",
  "no-unreachable": "error",
  "no-self-assign": "error",
  "no-constant-condition": ["error", { checkLoops: false }],
  "no-fallthrough": "error",
  "no-cond-assign": "error",
  "valid-typeof": "error",
  "use-isnan": "error",
  "no-sparse-arrays": "error",
  "no-func-assign": "error",
  "no-import-assign": "error",

  // Solo le variabili locali: una funzione globale mai chiamata da un altro
  // file non e' morta — la chiama un `onclick` nel markup, che ESLint non
  // vede. Quel controllo lo fa una guardia in `test_interfaccia.py`, che il
  // markup ce l'ha sotto gli occhi.
  "no-unused-vars": ["warn", { vars: "local", args: "none" }],
};

const AMBIENTE = {
  ...globals.browser,
  // Caricate dalla pagina prima dei nostri copioni.
  lucide: "readonly",
  tailwind: "readonly",
};

export default [
  ...[...dichiaratiDa.keys()].map((file) => {
    const altrui = {};
    for (const [altro, nomi] of dichiaratiDa) {
      if (altro === file) continue;
      for (const nome of nomi) {
        // "writable": un'area puo' assegnare una variabile dichiarata altrove.
        altrui[nome] = "writable";
      }
    }
    // I nomi che il file dichiara da se' non vanno dati come globali:
    // sarebbero una ridichiarazione di qualcosa che ESLint crede predefinito.
    for (const nome of dichiaratiDa.get(file)) delete altrui[nome];

    return {
      files: [`${CARTELLA}/${file}`],
      languageOptions: {
        ecmaVersion: 2022,
        sourceType: "script",
        globals: { ...AMBIENTE, ...altrui },
      },
      rules: REGOLE,
    };
  }),
  {
    files: ["eslint.config.js"],
    languageOptions: { ecmaVersion: 2022, sourceType: "module", globals: globals.node },
  },
];
