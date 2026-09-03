---
title: "feat(i18n): separare le stringhe dalla logica"
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: core", "area: frontend"]
---

## Contesto

Le stringhe italiane sono intrecciate alla logica in tutto il progetto, incluse
le espressioni regolari di riconoscimento degli intenti
(`^(accendi|attiva|spegni|disattiva)\s+...`) e le liste di parole chiave del
fast-path. Non e' un problema di traduzione delle etichette: e' la logica di
comprensione a essere monolingue.

## Cosa fare

- [ ] Estrarre le stringhe dell'interfaccia in file di traduzione
- [ ] Estrarre gli schemi di intento in una configurazione per lingua
- [ ] Prompt di sistema parametrico sulla lingua
- [ ] Selezione della lingua per utente, non solo per installazione
- [ ] Italiano come lingua di riferimento, inglese come seconda per validare la separazione

## Criteri di accettazione

- [ ] Aggiungere una lingua non richiede modifiche al codice della logica
- [ ] Due utenti con lingue diverse ricevono risposte nella propria lingua
- [ ] Nessuna stringa visibile all'utente resta scritta nel codice
