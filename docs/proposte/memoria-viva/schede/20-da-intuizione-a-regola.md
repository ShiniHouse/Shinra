---
title: "feat(regole): un'intuizione puo' diventare una bozza di regola, spenta, da confermare"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase D — Il sogno.** Dipende da: Intuizioni, #192.

## Contesto

Il motore di regole (v0.4.0) sa gia' scattare su orario, stato ed evento, e ha una provenienza per le regole
nate dal grafo. Una regola che nasce da un'abitudine osservata e' utile e **pericolosa se nasce attiva**: la
stessa disciplina della #192 — il modello propone, una persona decide.

## Cosa fare

- [ ] Creare la regola **disattivata**, con provenienza `sogno` e un riferimento all'intuizione
- [ ] Mostrare una simulazione: «nell'ultima settimana sarebbe scattata 3 volte»
- [ ] Attivare solo con conferma esplicita; le azioni sensibili passano comunque dal varco della #192

## Criteri di accettazione

- [ ] Nessuna regola nasce attiva (test)
- [ ] Una regola con un'azione su una serratura non si attiva senza il varco di conferma
