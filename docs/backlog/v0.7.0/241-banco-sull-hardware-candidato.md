---
title: "test(llm): il banco di prova sull'hardware candidato, misurato e non stimato"
issue: 241
milestone: "v0.7.0"
labels: ["tipo: attivita'", "area: core"]
---

> **Dipende da:** il banco della #183 e l'Ollama su un server dedicato.

## Contesto

Sull'hardware di casa non c'e' una misura: le cifre che circolano (qualche token al secondo su una CPU senza
GPU, 20 e oltre su un Mac con memoria unificata, 10–18 su un mini PC con GPU integrata) vengono da blog, non da
questa casa. Prima di spendere, si misura con **lo stesso banco** su ogni candidata, in modo che i numeri siano
confrontabili.

Su CPU il costo piu' alto e' leggere il prompt a ogni richiesta (circa 5000 token), non scrivere la risposta: la
tabella deve dire *entrambe* le cose.

## Cosa fare

- [ ] Eseguire il banco sull'hardware attuale (i5-8500T) con i modelli scelti
- [ ] Eseguirlo su almeno una candidata (per esempio un Mac mini M1 16 GB, anche in prestito o con reso)
- [ ] Per ogni coppia macchina/modello: scelte giuste, argomenti giusti, **troncati**, tempo di lettura del prompt, token al secondo in scrittura, picco di memoria
- [ ] Salvare i risultati in `banco/risultati/` e riassumerli in una tabella
- [ ] La guida dice quale hardware serve per quale modello, con i numeri

## Criteri di accettazione

- [ ] La tabella ha almeno due macchine e due modelli, **misurati**
- [ ] Una riga di conclusione: «con questo hardware, questo modello e' il minimo», oppure «non basta»
- [ ] Le cifre della ricerca in rete non compaiono come fatti: solo come punto di partenza dichiarato
