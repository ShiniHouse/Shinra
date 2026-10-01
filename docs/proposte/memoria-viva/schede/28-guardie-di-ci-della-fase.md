---
title: "test(ci): le guardie della memoria: privacy, rete spenta, budget"
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: infra"]
---

> **Fase Trasversale.**

## Contesto

Cio' che questa fase protegge si rompe in silenzio: un profilo che legge un ricordo altrui, una richiesta
che esce dalla rete, un prompt tagliato. Sono guardie, non test di comportamento.

## Cosa fare

- [ ] Privacy cross-profilo parametrizzata su **tutte** le rotte della memoria
- [ ] Rete spenta: con canali esterni disabilitati, il sogno e la memoria non creano client HTTP verso host esterni
- [ ] Budget: nessun percorso produce un prompt oltre il contesto senza traccia
- [ ] Livelli dell'architettura per i moduli nuovi; tetto delle cinquecento righe; `API.md` rigenerato

## Criteri di accettazione

- [ ] Le guardie falliscono se si toglie il controllo che proteggono (prova per mutazione)
