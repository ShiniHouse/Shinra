---
title: "feat(sicurezza): cancellare un ricordo lo cancella davvero, dappertutto"
issue: 253
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: sicurezza"]
---

> **Fase B — Trasparenza.** Dipende da: Schema della memoria.

## Contesto

Un ricordo non vive in un posto solo: ha un vettore (`embedding_fatti`), puo' essere citato da un
riassunto o da un'intuizione, finisce nel backup e nelle esportazioni. «Dimentica» che lascia copie e'
peggio di niente, perche' fa credere il contrario.

## Cosa fare

- [ ] Eliminare un ricordo elimina il suo vettore e marca come decaduti riassunti e intuizioni che lo citano
- [ ] «Dimentica tutto di me»: tutti i ricordi privati, i riassunti e le intuizioni del profilo, con conferma
- [ ] Il registro scrive che e' avvenuto, non cosa
- [ ] Dichiarare nella guida che i **backup precedenti** non vengono riscritti

## Criteri di accettazione

- [ ] Dopo una cancellazione, una scansione di tutte le tabelle non trova piu' il testo
- [ ] Un backup fatto dopo la cancellazione non lo contiene
