---
title: "feat(luoghi): meteo, alba, tramonto e prompt per il luogo giusto"
issue: 344
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Luoghi — Fetta c. Dipende da: dove sei.**

## Contesto

Meteo (Open-Meteo, oggi per nome della citta'), alba e tramonto (`sun.sun` di Home Assistant, che ha la *sua* posizione) e il prompt
di sistema usano una sola citta'. Con piu' luoghi, «che tempo fa?» deve rispondere per il luogo giusto: **quello nominato nella
frase** («al mare»), poi dove si trova chi parla, poi la casa principale.

## Cosa fare

- [ ] Risoluzione del luogo di una richiesta nell'ordine detto sopra
- [ ] Il meteo e l'alba/tramonto si calcolano per le coordinate del luogo; le coordinate mandate al servizio esterno sono **arrotondate a circa un chilometro**
- [ ] Il prompt dice in quale luogo si trova chi parla, non una citta' fissa
- [ ] Il fuso orario resta quello della casa (limite dichiarato nella guida)

## Criteri di accettazione

- [ ] Lo stesso «che tempo fa?» risponde per due luoghi diversi, con la riga di registro che dice quale
- [ ] Un test verifica che al servizio esterno non esca una coordinata con piu' di due decimali
