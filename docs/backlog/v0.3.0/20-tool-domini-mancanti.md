---
title: "feat(skills): tool per serrature, media player, aspirapolvere e ventilatori"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`server/routes_admin.py` elenca `lock`, `media_player`, `vacuum` e `fan` fra i
domini controllabili, e l'interfaccia li mostra nella mappa dispositivi. Ma
`control_device` gestisce solo luci, prese, clima e tapparelle: **nessun tool sa
comandarli**. L'utente li vede e non puo' usarli.

## Cosa fare

- [ ] `lock`: blocca, sblocca, stato. Lo sblocco richiede conferma esplicita e ruolo adeguato, e non e' mai accessibile a un profilo `child`
- [ ] `media_player`: riproduci, pausa, traccia successiva, volume, sorgente, multiroom
- [ ] `vacuum`: avvia, ferma, rientra alla base, pulisci una stanza
- [ ] `fan`: acceso/spento, velocita', oscillazione
- [ ] Ogni tool valida l'`entity_id` contro le entita' reali prima di inviare il comando: quello prodotto dal modello non e' un dato fidato
- [ ] Ogni azione finisce nel registro della issue #15

## Criteri di accettazione

- [ ] Ogni dominio elencato come controllabile ha un tool che lo comanda
- [ ] Lo sblocco di una serratura richiede conferma e non e' possibile da un profilo `child`
- [ ] Un `entity_id` inesistente produce un errore chiaro senza raggiungere Home Assistant
- [ ] Ogni tool ha test, senza rete
