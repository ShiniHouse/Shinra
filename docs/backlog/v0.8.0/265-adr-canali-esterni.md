---
title: "docs(adr): canali esterni: cosa puo' passare da un servizio di terzi"
issue: 265
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: sicurezza"]
---

> **Fase E — I canali esterni.** Dipende da: #192.

## Contesto

La `0.6.0` promette: «con l'opzione esterna spenta nessuna richiesta esce dalla rete locale». Un canale di
messaggistica esterno (Telegram, per esempio) e' per definizione un servizio di terzi: i messaggi dei bot
**non sono cifrati end-to-end**, e chi ha il telefono con quella app ha un telecomando della casa. Va
deciso se farlo, prima di come.

## Cosa fare

- [ ] Decidere se si fa, e per chi: opt-in per profilo, **spento di default**
- [ ] Decidere cosa non passa mai: codici, segreti, dettagli dell'allarme; esiste una modalita' «riservata»?
- [ ] Decidere l'identita' (abbinamento con codice monouso) e il limite sulle azioni sensibili (la #192 si applica gia')
- [ ] Valutare alternative senza terzi: notifiche push gia' presenti, un server `ntfy` o `Matrix` in casa

## Criteri di accettazione

- [ ] L'ADR e' accettato, oppure dice «non si fa» e le schede E si chiudono
- [ ] Il criterio della `0.6.0` sulla rete spenta resta vero con i canali spenti
