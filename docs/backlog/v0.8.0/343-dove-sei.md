---
title: "feat(luoghi): Shinra sa dove sei, e lo sa solo adesso"
issue: 343
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Luoghi — Fetta b. Dipende da: il registro dei luoghi.**

## Contesto

Per rispondere bene Shinra deve sapere **in quale luogo si trova chi parla**. La posizione di una persona si confronta con i luoghi
registrati: vince il piu' vicino entro il suo raggio, altrimenti «in giro». La promessa del progetto e' che la posizione resta in
casa: si tiene il luogo attuale, **mai la traccia degli spostamenti**.

## Cosa fare

- [ ] Per ogni persona, solo il luogo attuale e quando e' stato aggiornato (nessuna storia)
- [ ] Aggiornamento dalla posizione che Home Assistant gia' conosce; per i dispositivi resta la stanza o il satellite da cui si parla
- [ ] Ogni persona puo' **spegnere** e **cancellare** la propria posizione dal profilo; il consenso e' per profilo (decisione da confermare)
- [ ] Una domanda «dove sono?» risponde col nome del luogo, senza coordinate

## Criteri di accettazione

- [ ] Su un telefono vero il luogo cambia da solo quando si arriva a un altro luogo registrato
- [ ] Spenta la posizione, nulla viene piu' aggiornato e quello salvato si cancella
- [ ] Nel database non c'e' nessuna traccia degli spostamenti passati
