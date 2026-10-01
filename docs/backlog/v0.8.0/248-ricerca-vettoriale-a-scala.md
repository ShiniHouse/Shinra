---
title: "docs(adr): la ricerca per vettori regge la casa? misura prima di cambiare"
issue: 248
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: infra"]
---

> **Fase A — Le fondamenta.**

## Contesto

Oggi i vettori stanno come JSON in `embedding_fatti` e il coseno e' calcolato in Python puro per
ogni fatto. Con qualche centinaio di fatti e' invisibile; con migliaia non e' detto. L'idea di
`sqlite-vec` e' ragionevole ma ha un costo: e' un'**estensione caricabile**, e `enable_load_extension`
non e' disponibile in ogni build di Python (va verificato su Windows, nell'immagine Docker e su aarch64).
Prima si misura, poi si sceglie.

## Cosa fare

- [ ] Misurare tempo per richiesta a 100, 1.000, 5.000 e 20.000 fatti, con il modello di embedding configurato, sul i5-8500T
- [ ] Confrontare: Python puro (oggi), `numpy` (nuova dipendenza), `sqlite-vec`
- [ ] Verificare se l'estensione si carica nelle tre piattaforme del progetto
- [ ] Scrivere l'ADR con la tabella delle misure e una soglia dichiarata: sotto N fatti non si cambia niente

## Criteri di accettazione

- [ ] L'ADR riporta le misure vere, non stime
- [ ] Se si adotta un'alternativa, c'e' un ripiego automatico quando l'estensione non si carica, e la CI prova entrambi i percorsi
