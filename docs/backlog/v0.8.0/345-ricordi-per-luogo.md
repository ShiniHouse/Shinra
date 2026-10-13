---
title: "feat(luoghi): i ricordi hanno un luogo, e l'intervista chiede degli altri luoghi"
issue: 345
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Luoghi — Fetta d. Dipende da: lo schema della memoria (#245) e il registro dei luoghi.**

## Contesto

Il luogo e' uno degli ambiti dei ricordi, accanto alle persone e alla casa: un fatto della casa al mare non deve finire fra quelli della
casa principale. L'intervista oggi chiede una citta' e la salva come una frase.

## Cosa fare

- [ ] Un ricordo puo' avere un luogo; il recupero lo usa per scegliere i fatti da mettere nel prompt
- [ ] L'intervista chiede «hai altre abitazioni o luoghi?» e propone di registrarli da dove si e'
- [ ] La domanda sulla citta' dell'intervista crea il luogo principale invece di una frase
- [ ] La vista dei ricordi e il «dimentica» rispettano il luogo

## Criteri di accettazione

- [ ] Un fatto detto per la casa al mare non compare nel prompt quando si parla della casa principale
- [ ] Un luogo creato dall'intervista compare nel registro dei luoghi
