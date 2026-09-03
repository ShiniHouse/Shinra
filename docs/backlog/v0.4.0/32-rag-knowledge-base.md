---
title: "feat(conoscenza): recupero per similarita' al posto dell'iniezione totale"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`get_enabled_knowledge_summary()` concatena **tutti** i fatti abilitati e li
inietta nel prompt di sistema a ogni richiesta. Con la Modalita' Apprendimento
funzionante (v0.1.0) la conoscenza crescera' rapidamente, e il contesto cresce
linearmente con essa: prima si paga in latenza, poi si satura la finestra e i
fatti piu' vecchi vengono silenziosamente troncati.

Il problema e' aggravato dalla configurazione attuale, che imposta `num_ctx` a
1024 o 2048 token.

## Cosa fare

- [ ] Calcolo degli embedding dei fatti tramite Ollama, con archiviazione nel database
- [ ] Recupero dei soli fatti pertinenti alla domanda, con soglia e numero massimo
- [ ] Ricalcolo dell'embedding alla modifica di un fatto
- [ ] Ricerca ibrida: similarita' semantica piu' corrispondenza testuale, che regge meglio nomi propri e numeri
- [ ] Nell'interfaccia, mostrare quali fatti hanno contribuito a una risposta

## Criteri di accettazione

- [ ] Con cinquecento fatti memorizzati, il contesto inviato al modello resta di dimensione costante
- [ ] Una domanda specifica recupera i fatti pertinenti e non gli altri
- [ ] La latenza non peggiora rispetto all'iniezione totale
