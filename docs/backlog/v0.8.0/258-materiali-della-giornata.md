---
title: "feat(sogno): raccogliere cio' che e' successo oggi, per profilo e con un tetto"
issue: 258
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase D — Il sogno.** Dipende da: Riassunti persistenti.

## Contesto

Il sogno riflette su cio' che c'e'. Cosa c'e' davvero: il **registro delle azioni** (chi ha fatto cosa, 90
giorni), i **riassunti** della fase C, la **cronologia di Home Assistant** (che Shinra non salva: la chiede a
HA). Gli eventi di presenza oggi non vengono conservati: o si salvano in forma aggregata o non esistono per
il sogno. Non si inventa materiale che non c'e'.

## Cosa fare

- [ ] Raccogliere per profilo: registro azioni, riassunti, cronologia HA (con un tetto di dimensione)
- [ ] Decidere se conservare la presenza in forma aggregata (ora e stanza, non traiettorie fini)
- [ ] Oscurare i dati sensibili con `registro.oscura`; mai dati di un profilo nel materiale di un altro (salvo la casa condivisa)

## Criteri di accettazione

- [ ] Il materiale di un profilo non contiene righe di un altro (test)
- [ ] Il tetto di dimensione e' rispettato anche con mesi di registro
