---
title: "refactor(interfaccia): Impostazioni a sezioni, aperta solo quella che serve"
issue: 124
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

La scheda Impostazioni e' **421 righe di markup**: 19 campi, 15 pulsanti, 9
pannelli, 11 titoli, tutti aperti contemporaneamente. Pesa quanto le altre
sette schede messe insieme.

Non e' una schermata da leggere, e' una schermata in cui si cerca — e cercare
in un muro aperto e' piu' lento che aprire la sezione giusta.

## Cosa fare

- [x] Trasformare i nove pannelli in sezioni richiudibili, chiuse per difetto tranne la prima
- [x] Ogni sezione dice in una riga cosa contiene, anche da chiusa
- [x] Ricordare quale sezione era aperta, per chi torna a sistemare la stessa cosa
- [x] Accogliere qui cio' che arriva dalla console: modello e invocazione Alexa

## Criteri di accettazione

- [x] Nessun campo sparisce: sono tutti raggiungibili
- [x] A schermata appena aperta e' visibile meno di un terzo dei campi di oggi
- [x] Trovare un'impostazione nota richiede un clic, non uno scorrimento
- [x] La memoria della sezione aperta non rompe la pagina se `localStorage` non risponde

## Com'e' andata

Fatta con la PR #138. I pannelli erano otto, non nove.

Misurato a scheda appena aperta: **17 campi visibili diventati 0**, 7 pulsanti
diventati 1 — quello che salva. Lo zero non e' un trionfo: la prima sezione e'
la scelta della palette, che si fa con delle carte e non con dei campi. I
diciassette restano tutti a un clic, e una guardia lo verifica leggendo gli
identificativi che la pagina cerca davvero.

Modello e invocazione Alexa erano gia' arrivati qui con la #123.

Due difetti trovati guardando la schermata: l'icona `house` non esiste in
lucide 0.344.0, e le carte delle palette erano grigio scuro su bianco perche'
`bg-slate-900/50` non era fra le riscritture del tema chiaro — la guardia dei
colori salta apposta la famiglia `slate`. Adesso c'e' anche la sorella per i
grigi.
