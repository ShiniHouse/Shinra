---
title: "refactor(frontend): scomporre index.html in moduli ES"
issue: 34
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

> Quando la scheda e' stata scritta il file era di 4.657 righe. Le sei voci
> dell'interfaccia (#123-#128) l'hanno portato a **7.438** prima che questo
> lavoro cominciasse.

## Cosa fare

- [x] Separare CSS e JavaScript in file propri — #144
- [x] Suddividere il JavaScript per area: autenticazione, chat, voce,
      dispositivi, routine, canvas, timer, impostazioni — #145, #147, #151.
      Sono venti file, uno per area, ma sono ancora copioni classici caricati
      in ordine: **moduli ES veri no, non ancora**
- [ ] Sostituire lo stato globale sparso con un contenitore unico
- [x] Sostituire la generazione di HTML per concatenazione di stringhe, che
      oggi e' esposta a injection dai nomi delle entita' — #148, #149, #150,
      #151
- [x] Aggiungere ESLint e Prettier alla CI — #146, #147
- [ ] Valutare un bundler leggero (Vite) mantenendo la possibilita' di servire
      senza build

## Criteri di accettazione

- [ ] Nessun file frontend supera le cinquecento righe
- [x] ESLint passa in CI
- [ ] Nessuna regressione funzionale sull'interfaccia
- [x] Un nome di entita' contenente HTML non altera la pagina

## A che punto siamo

Otto PR unite: **#144** (CSS e JS fuori da index.html), **#145** (un file per
area), **#146** (ESLint, che al primo giro ha trovato un difetto vero in
produzione: il pulsante «+ Timer» chiamava un nome che non e' mai esistito),
**#147** (Prettier), **#148** (il modello `_html` che scappa i valori, piu' la
chat), **#149**, **#150** e **#151** (le restanti diciotto aree, fino a
svuotare la lista delle eccezioni).

Misurato adesso:

| | prima | dopo |
| :--- | :-- | :-- |
| `web/templates/index.html` | 7.438 righe | **1.294** |
| File JavaScript | 1 (dentro l'HTML) | 21, il piu' lungo di **451** righe |
| File CSS | 1 (dentro l'HTML) | 5 |
| Concatenazioni di stringhe non protette | tutte | **zero**, con guardia |

I due criteri ancora aperti, e perche':

- **Cinquecento righe.** Tutto il JavaScript e tutto il CSS ci stanno sotto.
  Resta `index.html`: 1.257 righe di solo markup. Scende quando il markup di
  ogni area seguira' il suo JavaScript, cosa che conviene fare insieme ai
  moduli ES.
- **Nessuna regressione.** Due ne sono uscite dalla scomposizione, tutte e due
  trovate in casa e chiuse: il nodo che non si trascinava dall'intestazione
  (#154) e la crocetta che non staccava il cavo (#155). Da li' e' nata la
  #156, che fa girare in CI sette gesti veri dell'editor con un browser vero.
  Restano aperte la #152 e la #153, che pero' c'erano gia' prima.

## Guardie

Il grosso sta in `tests/unit/test_interfaccia.py`. Le due che contano:

- uno scanner dei template letterali che **solleva** se il sorgente non e'
  bilanciato, invece di guardare meta' file in silenzio;
- una guardia su `_grezzo`, il marcatore che disattiva l'escaping apposta:
  puo' comparire solo su markup scritto da noi, mai su un dato.

Entrambe sono nate da una mutazione che non mordeva.
