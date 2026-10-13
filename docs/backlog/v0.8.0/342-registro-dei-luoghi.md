---
title: "feat(luoghi): il registro dei luoghi, registrati dal posto in cui si e'"
issue: 342
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Luoghi — Fetta a.**

## Contesto

Oggi c'e' una sola citta', `assistant.default_city`, scritta a mano. Il proprietario vuole **piu' abitazioni o luoghi** oltre alla
casa principale, con le **coordinate vere** prese dalla posizione di uno smartphone o di un PC, non scritte a mano. La proposta
completa e le decisioni sono in [`docs/proposte/luoghi/README.md`](../../proposte/luoghi/README.md).

## Cosa fare

- [ ] Tabella `luoghi` (nome, tipo, se e' la principale, latitudine, longitudine, raggio in metri, citta') con migrazione Alembic che sale e scende; la citta' di oggi diventa il luogo principale
- [ ] API per elencare, registrare, correggere e **cancellare** un luogo (con le coordinate); permesso dedicato
- [ ] Registrazione dal **telefono** (posizione di `person` / `device_tracker` di Home Assistant) e dal **browser** (geolocalizzazione, pulsante «Registra questo luogo» nelle Impostazioni), con la precisione dichiarata in chiaro
- [ ] Le coordinate non entrano in log, registro delle azioni e grafo

## Criteri di accettazione

- [ ] Da un telefono vero si registra il luogo in cui si e', e compare nell'elenco con la sua citta'
- [ ] Dal browser di un PC si registra un luogo e la precisione e' dichiarata come approssimativa
- [ ] Cancellare un luogo cancella le sue coordinate dal database e dal salvataggio
- [ ] Un test cerca le coordinate nei log e nel registro e non le trova
