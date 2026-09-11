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

- [ ] Trasformare i nove pannelli in sezioni richiudibili, chiuse per difetto tranne la prima
- [ ] Ogni sezione dice in una riga cosa contiene, anche da chiusa
- [ ] Ricordare quale sezione era aperta, per chi torna a sistemare la stessa cosa
- [ ] Accogliere qui cio' che arriva dalla console: modello e invocazione Alexa

## Criteri di accettazione

- [ ] Nessun campo sparisce: sono tutti raggiungibili
- [ ] A schermata appena aperta e' visibile meno di un terzo dei campi di oggi
- [ ] Trovare un'impostazione nota richiede un clic, non uno scorrimento
- [ ] La memoria della sezione aperta non rompe la pagina se `localStorage` non risponde
