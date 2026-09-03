---
title: "feat(skills): clima completo e tapparelle con posizione"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`control_device` supporta `set_temperature` per il clima e `open`/`close` per le
tapparelle. Manca tutto il resto: modalita', ventola, umidita', posizione
intermedia, orientamento delle lamelle.

«Abbassa la tapparella a meta'» e «metti il condizionatore in deumidificazione»
oggi non sono esprimibili.

## Cosa fare

- [ ] Clima: modalita' (riscaldamento, raffrescamento, automatico, deumidificazione, ventilazione), velocita' ventola, umidita' obiettivo, preset
- [ ] Tapparelle: posizione percentuale, orientamento lamelle, arresto a meta' corsa
- [ ] Lettura dello stato corrente, non solo comando
- [ ] Aggiornare gli schemi dei tool e il prompt di sistema

## Criteri di accettazione

- [ ] «Abbassa la tapparella del salotto al 40%» funziona
- [ ] «Metti il clima della camera in deumidificazione a 50%» funziona
- [ ] «A che temperatura e' impostato il termostato?» risponde con il valore reale
