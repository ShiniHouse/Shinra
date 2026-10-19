# 0011 — Canali esterni: cosa può passare da un servizio di terzi

- **Stato:** Rifiutato
- **Data:** 2026-10-13
- **Decisione:** 2026-10-19, del proprietario: **non si fa, per ora**. Le schede #265–#268 sono chiuse.
- **Attuazione:** nessuna (era: issue #265; canale #266, connettore #267, interfaccia #268)

> Decisione: **non si fa, per ora.** Le notifiche push e la PWA bastano, e un canale di terzi non è cifrato end-to-end e
> metterebbe un telecomando della casa su un'app esterna. Il testo sotto resta come traccia del ragionamento, per chi
> riaprisse la questione.
>
> **Se un giorno si riapre:** si parte dalle alternative senza terzi (un server `ntfy` o `Matrix` in casa, punto 6), si
> riapre la #265 e questo ADR torna `Proposto`. La promessa della `0.6.0` — con l'opzione esterna spenta non esce nessuna
> richiesta — resta vera: nel codice non c'è nessun canale esterno.

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
