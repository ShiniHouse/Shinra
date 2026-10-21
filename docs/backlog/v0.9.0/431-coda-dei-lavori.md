---
title: "feat(assistente): una coda di lavori in background, e «ci penso» per le richieste che richiedono tempo"
issue: 431
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core", "area: infra"]
---

> **Fase B — L'assistente prende tempo.** Dipende da: ADR 0013. Riusa lo scheduler (ADR 0003) e le notifiche.

## Contesto

Oggi una richiesta aspetta il modello; se e' difficile il risultato e' una risposta lenta o un fallimento, e non c'e' modo di dire «ci penso e ti
faccio sapere». Serve un **lavoro**: un'unita' con proprietario, scopo, tetto di tempo e di passi, stato e avanzamento, che sopravvive a un riavvio.

## Cosa fare

- [ ] Una tabella dei lavori (migrazione): proprietario, scopo, richiesta, stato (`in coda`, `in corso`, `fatto`, `fallito`, `annullato`), avanzamento, tetti, esito. I salvataggi **non** la contengono
- [ ] Una richiesta che supera la soglia di tempo diventa un lavoro e Shinra risponde subito «ci sto lavorando»; «a che punto sei?» e «annulla» funzionano
- [ ] Concorrenza **uno** per i lavori pesanti, priorita' bassa: cedono il passo alla chat e a Home Assistant
- [ ] L'esito arriva dove la persona sceglie (chat, notifica, ntfy, voce); un lavoro privato lo vede solo chi lo ha chiesto
- [ ] Il Cervello mostra i lavori in corso con l'avanzamento

## Criteri di accettazione

- [ ] Un lavoro supera il suo tetto di tempo e di passi? Si ferma e lo dice, con un test che simula un modello che non finisce mai
- [ ] Un riavvio a meta' non perde il lavoro e non lo ripete due volte
- [ ] La chat non si blocca mentre un lavoro gira (misurato)
- [ ] Una guardia: un profilo non vede, non annulla e non legge l'esito dei lavori di un altro
