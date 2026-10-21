---
title: "feat(apprendimento): cosa osserva Shinra: frasi corrette, routine fallite, dispositivi che non rispondono"
issue: 434
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase D.** Dipende da: il ciclo dell'imparare (04).

## Contesto

Il ciclo e' vuoto senza qualcosa da osservare. Le fonti devono essere **fatti verificabili dal codice** (dal registro), non impressioni del modello.

## Cosa fare

- [ ] Una frase che l'utente ha corretto o annullato subito dopo («no, intendevo la luce del salotto») diventa un'osservazione, per il profilo che l'ha detta
- [ ] Una routine o regola che fallisce piu' volte in un periodo; un dispositivo che non risponde; un alias che nessuno usa
- [ ] Richieste ripetute che potrebbero essere una routine (come le abitudini del sogno, ma per qualunque richiesta)
- [ ] Ogni osservazione porta il motivo e i dati, **mai** il testo di una conversazione di un altro profilo

## Criteri di accettazione

- [ ] Un test per ogni fonte, con un registro finto, e uno che prova che un profilo non osserva cio' che e' di un altro
- [ ] Il numero di proposte per notte ha un tetto: Shinra non sommerge la persona
