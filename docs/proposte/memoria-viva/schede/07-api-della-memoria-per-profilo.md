---
title: "feat(api): cosa sa Shinra, di casa e di me: lettura, correzione, cancellazione"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase B — Trasparenza.** Dipende da: ADR privacy, schema della memoria.

## Contesto

Le rotte attuali (`routes_conoscenza.py`) servono la conoscenza di casa a chi ha il permesso. Per la
vista «cosa sai di me» serve un'API per ambito, con il controllo del proprietario **nel codice**, non
nell'interfaccia: un profilo che indovina l'identificativo di un ricordo altrui deve ricevere un 404.

## Cosa fare

- [ ] `GET/POST/PATCH/DELETE` sui ricordi con ambito (`casa` o `mio`), filtri per origine, stato e importanza
- [ ] `GET` «i miei» come scorciatoia, e «dimentica tutto di me» con conferma
- [ ] Permessi come da ADR; ogni modifica nel registro azioni (identificativo e campo, **mai il testo**)
- [ ] Le rotte dichiarano la propria protezione come tutte le altre; `API.md` si rigenera

## Criteri di accettazione

- [ ] Test cross-profilo parametrizzati su ogni rotta: un profilo non legge, non modifica e non cancella i ricordi privati di un altro, nemmeno per identificativo
- [ ] Un profilo `child` rispetta i limiti decisi nell'ADR
