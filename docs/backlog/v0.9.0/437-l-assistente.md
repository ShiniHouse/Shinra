---
title: "feat(assistente): domande di chiarimento, riprendere un lavoro a meta', un riepilogo di cio' che e' successo"
issue: 437
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core", "area: frontend"]
---

> **Fase F — Un assistente, non un esecutore.** Dipende da: la coda dei lavori (02) e i piani (#191).

## Contesto

Un assistente chiede quando la richiesta e' ambigua invece di indovinare, riprende un lavoro lasciato a meta', e dice cosa e' successo mentre non c'eri.
Se un passo richiede una decisione, **si ferma e la chiede**, e il lavoro aspetta.

## Cosa fare

- [ ] Una richiesta ambigua produce una domanda di chiarimento (con le opzioni), non una scelta a caso
- [ ] Un lavoro fermo in attesa di una decisione resta visibile, ricorda cosa manca, e riparte quando si risponde
- [ ] Un riepilogo del giorno per profilo: cosa e' stato fatto, cosa e' in corso, cosa aspetta una risposta

## Criteri di accettazione

- [ ] Provato in casa con il modello vero: almeno tre richieste a piu' passi di una settimana d'uso, con l'esito scritto, compreso cio' che non funziona
- [ ] Un lavoro in attesa non scade in silenzio e non esegue niente senza la risposta
