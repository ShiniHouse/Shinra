---
title: "feat(canali): un canale sa mandare e ricevere, e sa chi e' dall'altra parte"
issue: 266
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: integrazioni"]
---

> **Fase E — I canali esterni.** Dipende da: ADR canali esterni.

## Contesto

Oggi i canali in uscita sono ascoltatori sul bus (avviso verso web push, Echo, WebSocket) e i canali in
entrata sono Alexa e la chat web, ciascuno con la sua logica di identita'. Per un canale nuovo serve
un'interfaccia comune, con **l'identita' al centro**: «chat 12345» e' una persona solo se e' stata abbinata.

## Cosa fare

- [ ] Interfaccia `Canale`: `invia(avviso, destinatario)` e `ricevi()` che produce una richiesta con identita' e canale
- [ ] I canali esistenti si adeguano senza cambiare comportamento (guardia: stessi test di prima)
- [ ] Mappa identita' -> profilo con abbinamento a codice monouso mostrato in dashboard, che scade
- [ ] Una richiesta da un'identita' non abbinata viene ignorata e registrata
- [ ] Il contesto della richiesta porta il `canale`, cosi' il varco della #192 funziona

## Criteri di accettazione

- [ ] Una chat non abbinata non fa niente, e il registro lo dice
- [ ] Un codice di abbinamento scaduto o gia' usato non abbina
