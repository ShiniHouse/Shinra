---
title: "test(llm): il banco di prova sull'hardware candidato, misurato e non stimato"
issue: 241
milestone: "v0.7.0"
labels: ["tipo: attivita'", "area: core"]
---

> **Dipende da:** il banco della #183 e l'Ollama su un server dedicato.
>
> **Ridotta il 2026-10-06.** Non e' previsto un hardware nuovo: le prove si fanno **sul portatile** (i7-1355U, in carica) e sul
> server di casa, con un solo modello. Il banco resta pronto se un giorno l'hardware cambia (un comando, un'ora).

## Contesto

Sull'hardware di casa non c'e' una misura: le cifre che circolano (qualche token al secondo su una CPU senza
GPU, 20 e oltre su un Mac con memoria unificata, 10–18 su un mini PC con GPU integrata) vengono da blog, non da
questa casa. Prima di spendere, si misura con **lo stesso banco** su ogni candidata, in modo che i numeri siano
confrontabili.

Su CPU il costo piu' alto e' leggere il prompt a ogni richiesta (circa 5000 token), non scrivere la risposta: la
tabella deve dire *entrambe* le cose.

## Cosa fare

- [x] Eseguire il banco sull'hardware attuale (i5-8500T) con i modelli scelti: `qwen2.5:3b`, sei configurazioni
- [x] Eseguirlo su una seconda macchina: il portatile i7-1355U (non un Mac mini: l'acquisto non e' previsto)
- [ ] Per ogni coppia macchina/modello: scelte giuste, argomenti giusti, **troncati** (fatto), **mediana e p90** (fatto); tempo di lettura del prompt, token al secondo in scrittura e picco di memoria **non misurati a parte** (si leggono solo come stime dai tempi)
- [x] Salvare i risultati in `banco/risultati/` e riassumerli in una tabella (le analisi `*-ANALISI.md`)
- [ ] ~~La guida dice quale hardware serve per quale modello, con i numeri~~ — non applicabile: nessun hardware nuovo da consigliare

## Criteri di accettazione

- [ ] ~~La tabella ha almeno due macchine e due modelli~~ — **due macchine e un modello**, misurati; il secondo modello non si fa (vedi la #183)
- [x] Una riga di conclusione: con questo hardware `qwen2.5:3b` **non basta** per le soglie dell'ADR 0008 (strumento giusto 79,8% contro 85%, ~29 s contro 15 s), vedi la scheda #183
- [x] Le cifre della ricerca in rete non compaiono come fatti: solo come punto di partenza dichiarato
