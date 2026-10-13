---
title: "feat(luoghi): regole e promemoria che dipendono da un luogo"
issue: 346
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Luoghi — Fetta e. Dipende da: dove sei.**

## Contesto

«Quando arrivo al mare accendi il riscaldamento»: una regola o un promemoria che scatta all'arrivo in un luogo registrato. Si riusano
le zone che Home Assistant gia' legge.

## Cosa fare

- [ ] Una condizione «arrivo in / lascio» un luogo nel motore delle regole e nei promemoria
- [ ] Come per ogni regola, un'azione sensibile resta soggetta alla conferma (#192)
- [ ] Il registro dice quale luogo ha fatto scattare la regola, senza coordinate

## Criteri di accettazione

- [ ] Su un telefono vero la regola scatta all'arrivo nel luogo, con una riga di registro
- [ ] Se la posizione e' spenta la regola non scatta e lo dice
