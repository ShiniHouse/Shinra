---
title: "feat(notifiche): web push verso la PWA"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: frontend", "area: infra"]
---

## Contesto

`web/static/sw.js` esiste e gestisce installazione, attivazione e cache, ma
**non ha alcun handler per l'evento `push`**. Il sistema non puo' raggiungere
l'utente quando l'applicazione non e' aperta: promemoria, allarmi, avvisi
energetici e check-in restano tutti muti.

## Cosa fare

- [ ] Generazione delle chiavi VAPID e gestione delle sottoscrizioni per utente e dispositivo
- [ ] Handler `push` e `notificationclick` nel service worker
- [ ] Servizio di notifica unificato con instradamento per canale: push, annuncio su Echo, interfaccia web
- [ ] Preferenze per utente: quali eventi notificare e su quale canale
- [ ] Priorita': un allarme di intrusione ignora la modalita' silenziosa, un avviso energetico no

## Criteri di accettazione

- [ ] Un promemoria arriva sul telefono con l'applicazione chiusa
- [ ] Toccare la notifica apre il punto giusto dell'applicazione
- [ ] Le sottoscrizioni scadute vengono ripulite automaticamente
- [ ] Un utente puo' silenziare una categoria senza silenziarle tutte
