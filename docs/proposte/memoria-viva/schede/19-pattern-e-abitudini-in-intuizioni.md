---
title: "feat(sogno): le abitudini si contano con il codice, il modello le racconta"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase D — Il sogno.** Dipende da: Il job notturno.

## Contesto

Un modello da pochi miliardi di parametri **sbaglia i conti**. Dire «ogni sera alle 22 spegni il salotto»
richiede di contare occorrenze in giorni diversi: quello lo fa una funzione pura e testata, e al modello
resta il compito di dare un nome e una frase leggibile.

## Cosa fare

- [ ] Tabella `intuizioni` (ambito, tipo: abitudine, anomalia o preferenza, testo, prove, confidenza, stato proposta/accettata/scartata, scadenza)
- [ ] Una abitudine richiede almeno N occorrenze in almeno M giorni, calcolate in `domain/`, con le prove (identificativi delle righe del registro)
- [ ] Il modello riceve i numeri gia' calcolati e produce solo la frase; se contraddice i numeri, si scarta

## Criteri di accettazione

- [ ] Test sulla soglia (N-1 occorrenze: niente; N: intuizione)
- [ ] Ogni intuizione porta le sue prove, controllabili in interfaccia
