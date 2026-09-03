---
title: "feat(presenza): presenza delle persone e automazioni di arrivo e uscita"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`person` e `device_tracker` sono elencati fra i domini visibili, ma nessuna
logica li usa. Il sistema non sa se c'e' qualcuno in casa: e' l'informazione
piu' utile della domotica e oggi e' inutilizzata.

## Cosa fare

- [ ] Servizio di presenza che aggrega `person` in uno stato di casa: qualcuno presente, casa vuota, prima persona rientrata, ultima persona uscita
- [ ] Eventi di transizione pubblicati sul bus della issue #19
- [ ] Collegare la presenza al profilo utente, cosi' che l'assistente sappia con chi sta parlando senza chiederlo
- [ ] Trigger di presenza disponibili nell'editor di routine
- [ ] Ritardo configurabile contro i falsi negativi del GPS

## Criteri di accettazione

- [ ] L'uscita dell'ultima persona produce un evento «casa vuota»
- [ ] Una routine puo' essere attivata dal rientro di una persona specifica
- [ ] Una breve perdita di segnale GPS non genera un falso «casa vuota»
