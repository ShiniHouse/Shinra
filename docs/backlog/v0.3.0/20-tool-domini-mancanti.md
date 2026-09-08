---
title: "feat(skills): tool per serrature, media player, aspirapolvere e ventilatori"
issue: 20
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`server/routes_admin.py` elenca `lock`, `media_player`, `vacuum` e `fan` fra i
domini controllabili, e l'interfaccia li mostra nella mappa dispositivi. Ma
`control_device` gestisce solo luci, prese, clima e tapparelle: **nessun tool sa
comandarli**. L'utente li vede e non puo' usarli.

## Cosa fare

- [x] `lock`: blocca, sblocca, stato. Lo sblocco chiede conferma — una seconda
      richiesta entro un minuto, non un parametro che il modello puo' riempire
      da solo — e il permesso `sicurezza.comanda` e' gia' imposto dal client di
      Home Assistant, quindi vale anche qui. In piu': **dalla voce non si
      apre**, perche' l'ADR 0004 dice che il canale vocale non distingue chi
      parla
- [x] `media_player`: riproduci, pausa, traccia successiva e precedente,
      volume, sorgente. Il multiroom no: e' un raggruppamento di entita' e
      merita una scheda sua, non una riga in fondo a questa
- [x] `vacuum`: avvia, ferma, rientra alla base, pulisci una stanza
- [x] `fan`: acceso/spento, velocita', oscillazione
- [x] Ogni tool valida l'`entity_id` contro le entita' reali prima di inviare
      il comando. Con la cache della issue #19 non costa niente, e l'errore
      propone l'alternativa piu' simile invece di dire solo «no»
- [x] Ogni azione finisce nel registro della issue #15 — passa da
      `execute_tool`, quindi senza che questi tool debbano ricordarsene

## Criteri di accettazione

- [x] Ogni dominio elencato come controllabile ha un tool che lo comanda
- [x] Lo sblocco di una serratura richiede conferma e non e' possibile da un profilo `child`
- [x] Un `entity_id` inesistente produce un errore chiaro senza raggiungere Home Assistant
- [x] Ogni tool ha test, senza rete
