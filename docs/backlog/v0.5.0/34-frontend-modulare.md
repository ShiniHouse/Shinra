---
title: "refactor(frontend): scomporre index.html in moduli ES"
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

`web/templates/index.html` e' un file unico di **4.657 righe** che contiene
markup, tutto il CSS, 126 funzioni JavaScript, l'editor a grafo, il catalogo
RSS, la gestione vocale e i modali. Non c'e' build, non c'e' linting, non c'e'
alcuna separazione.

Ogni modifica al frontend e' rischiosa perche' l'ambito di una variabile e'
l'intero file. E' il freno principale a ogni funzione nuova con interfaccia.

## Cosa fare

- [ ] Separare CSS e JavaScript in file propri
- [ ] Suddividere il JavaScript in moduli ES per area: autenticazione, chat, voce, dispositivi, routine, canvas, timer, impostazioni
- [ ] Sostituire lo stato globale sparso con un contenitore unico
- [ ] Sostituire la generazione di HTML per concatenazione di stringhe, che oggi e' esposta a injection dai nomi delle entita'
- [ ] Aggiungere ESLint e Prettier alla CI
- [ ] Valutare un bundler leggero (Vite) mantenendo la possibilita' di servire senza build

## Criteri di accettazione

- [ ] Nessun file frontend supera le cinquecento righe
- [ ] ESLint passa in CI
- [ ] Nessuna regressione funzionale sull'interfaccia
- [ ] Un nome di entita' contenente HTML non altera la pagina
