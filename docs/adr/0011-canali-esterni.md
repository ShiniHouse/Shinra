# 0011 — Canali esterni: cosa può passare da un servizio di terzi

- **Stato:** Proposto
- **Data:** 2026-10-13
- **Attuazione:** milestone `v0.8.0`, issue #265 (canale: #266, connettore: #267, interfaccia: #268)

> Bozza scritta per essere discussa: **nessuna di queste scelte è decisa** finché il proprietario non porta lo stato a `Accettato`.
> È ammesso che la decisione sia «non si fa»: in quel caso le schede #266–#268 si chiudono.

## Contesto

La `0.6.0` promette: «con l'opzione esterna spenta nessuna richiesta esce dalla rete locale». Un canale di messaggistica esterno
(Telegram, per esempio) è per definizione un servizio di terzi: i messaggi dei bot **non sono cifrati end-to-end**, e chi ha il
telefono con quella app ha un telecomando della casa. Va deciso se farlo, prima di come.

## Proposta

1. **Opt-in per profilo, spento di default.** Nessun canale esterno è attivo finché una persona non lo abbina.
2. **Abbinamento con codice monouso** mostrato nell'interfaccia di Shinra e scritto dalla persona sul canale; senza abbinamento il
   canale non risponde.
3. **Cosa non passa mai:** codici, segreti, PIN, dettagli dell'allarme. I messaggi in uscita passano da `registro.oscura`.
4. **Azioni sensibili:** il limite della #192 vale anche da qui (nessuna serratura o allarme da un canale esterno senza conferma).
5. **Il criterio della `0.6.0` resta vero con i canali spenti:** un test verifica che, con tutti i canali spenti, non esca nessuna richiesta.
6. **Si valutano prima le alternative senza terzi**: le notifiche push già presenti, un server `ntfy` o `Matrix` in casa.

## Alternative scartate

- *Un solo bot condiviso da tutti*: nessuna identità per persona, nessuna revoca.
- *Cifratura propria sopra il bot*: complessità enorme per un beneficio che il canale non può garantire sul telefono.

## Conseguenze

- Il canale è un'astrazione bidirezionale (#266) che sa chi è dall'altra parte.
- La guida alla memoria (#271) dice in chiaro cosa vede un servizio di terzi.

## Da decidere prima dell'accettazione

- Se farlo, davvero, o fermarsi alle notifiche push.
- Se esiste una modalità «riservata» che manda solo «c'è qualcosa, apri Shinra».
