---
title: "feat(memoria): quanta storia grezza tenere lo decide il budget, non un numero fisso"
issue: 257
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase C — La storia compressa.** Dipende da: Budget del contesto, riassunti persistenti.

## Contesto

`max_history = 10` e' un numero scelto una volta. Con un prompt di 5000 token e un contesto di 2048, dieci
scambi sono troppi; con un modello a contesto largo, troppo pochi.

## Cosa fare

- [ ] Il numero di turni grezzi e' quello che resta del budget dopo sistema, strumenti e ricordi
- [ ] Una richiesta con molti strumenti pesa di piu' di una chiacchierata: si adegua da sola

## Criteri di accettazione

- [ ] Nessuna richiesta supera il budget (test deterministici)
- [ ] Con un contesto piu' largo la finestra cresce, senza toccare il codice
