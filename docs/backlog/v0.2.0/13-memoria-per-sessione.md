---
title: "fix(memoria): contesto di conversazione separato per utente e canale"
milestone: "v0.2.0"
labels: ["tipo: difetto", "area: core", "gravita': alta"]
riferimento: REL-03
---

## Contesto

`core/memory.py:30` crea un singleton globale `ConversationMemory`. La chat del
salotto, quella del telefono e ogni richiesta Alexa scrivono nella **stessa**
cronologia: il contesto di un adulto finisce nella sessione impostata come
`child` e viceversa, e due persone che parlano insieme si confondono a vicenda.

Il design e' gia' corretto — `process_user_input` accetta un parametro
`session_memory` — ma **nessun chiamante lo passa**.

C'e' un difetto collegato: `ConversationMemory.add_tool_interaction()` ha corpo
`pass`. Le azioni eseguite non entrano mai nel contesto, quindi l'assistente non
ricorda cosa ha appena fatto: «spegnila» dopo «accendi la luce della cucina» non
puo' funzionare.

## Cosa fare

- [ ] Gestore delle sessioni indicizzato per `(utente, canale)`
- [ ] `session_memory` passato da `/api/chat` e dal gestore Alexa
- [ ] Scadenza delle sessioni inattive, con limite al numero di sessioni in memoria
- [ ] Implementare `add_tool_interaction`, cosi' che le azioni eseguite entrino nel contesto
- [ ] Continuita' fra canali: una conversazione iniziata sull'Echo prosegue sul telefono per lo stesso utente

## Criteri di accettazione

- [ ] Due utenti diversi in due schede non vedono i reciproci messaggi
- [ ] Una richiesta Alexa non altera il contesto della chat web di un altro utente
- [ ] «Accendi la luce della cucina» seguito da «spegnila» funziona
- [ ] Le sessioni inattive vengono liberate
