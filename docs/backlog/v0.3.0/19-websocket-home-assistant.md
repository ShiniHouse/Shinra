---
title: "feat(home-assistant): connessione WebSocket per stato ed eventi in tempo reale"
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: integrazioni", "gravita': alta"]
---

## Contesto

Oggi ogni informazione da Home Assistant arriva da `GET /api/states`, cioe' da
una fotografia richiesta su domanda. Il sistema non sa mai **quando** qualcosa
accade: non esiste il concetto di evento.

Questo e' il vincolo che blocca l'intera fase v0.4.0. Una regola come «se la
porta si apre dopo le 23, accendi l'ingresso» e' impossibile senza eventi.

## Cosa fare

- [ ] Client WebSocket verso `/api/websocket` con autenticazione a token
- [ ] Sottoscrizione a `state_changed` e mantenimento di una cache locale degli stati
- [ ] Riconnessione automatica con attesa progressiva; fallback su REST mentre la connessione e' assente
- [ ] Bus eventi interno a cui i servizi si sottoscrivono
- [ ] `get_relevant_entities_summary` legge dalla cache invece di interrogare la rete
- [ ] Stato dei dispositivi spinto all'interfaccia via WebSocket, al posto del polling

## Criteri di accettazione

- [ ] L'accensione di una luce da Home Assistant appare nell'interfaccia entro un secondo, senza ricaricare
- [ ] La caduta della connessione non blocca il sistema e la riconnessione e' automatica
- [ ] Un evento di apertura porta e' osservabile e sottoscrivibile
- [ ] Il contesto per il modello si costruisce senza chiamate di rete
