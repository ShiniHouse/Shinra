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

> **Misurato il 2026-10-13 (qwen2.5:3b):** piu' storia grezza non e' sempre meglio. Con una sola risposta inventata fra
> i messaggi il modello non chiama piu' lo strumento (0 su 3, contro 3 su 3 senza storia). Oggi l'agente rimedia riprovando
> una volta senza storia (#338); la finestra adattiva deve poter scartare i turni sospetti, non solo i piu' vecchi.

## Cosa fare

- [ ] Il numero di turni grezzi e' quello che resta del budget dopo sistema, strumenti e ricordi
- [ ] Una richiesta con molti strumenti pesa di piu' di una chiacchierata: si adegua da sola

## Criteri di accettazione

- [ ] Nessuna richiesta supera il budget (test deterministici)
- [ ] Con un contesto piu' largo la finestra cresce, senza toccare il codice
