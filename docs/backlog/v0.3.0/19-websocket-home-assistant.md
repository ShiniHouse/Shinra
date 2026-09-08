---
title: "feat(home-assistant): connessione WebSocket per stato ed eventi in tempo reale"
issue: 19
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

- [x] Client WebSocket verso `/api/websocket` con autenticazione a token
- [x] Sottoscrizione a `state_changed` e mantenimento di una cache locale degli stati
- [x] Riconnessione automatica con attesa progressiva; fallback su REST mentre la connessione e' assente
- [x] Bus eventi interno a cui i servizi si sottoscrivono — esisteva gia' dalla
      v0.2.0 per timer e promemoria (`domain/eventi.py`): qui si e' aggiunto il
      tipo `ha.stato_cambiato` e chi lo pubblica
- [x] `get_relevant_entities_summary` legge dalla cache invece di interrogare la rete.
      Passa dalla stessa funzione anche `/api/ha/entities`: due strade diverse
      per la stessa domanda divergerebbero, e la differenza si noterebbe solo
      quando la connessione cade
- [x] Stato dei dispositivi spinto all'interfaccia via WebSocket, al posto del polling

## Criteri di accettazione

- [x] L'accensione di una luce da Home Assistant appare nell'interfaccia entro un secondo, senza ricaricare
- [x] La caduta della connessione non blocca il sistema e la riconnessione e' automatica
- [x] Un evento di apertura porta e' osservabile e sottoscrivibile
- [x] Il contesto per il modello si costruisce senza chiamate di rete
