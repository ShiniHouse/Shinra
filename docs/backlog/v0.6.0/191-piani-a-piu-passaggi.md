---
title: "feat(agente): piani a piu' passaggi, con correzione se un passaggio fallisce"
issue: 191
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

«Prepara la casa per la sera» non e' uno strumento: sono luci, tapparelle,
clima e forse un allarme. Oggi il ciclo fa una scelta alla volta. Serve un
piano: scomporre, eseguire, verificare, e correggersi se un passaggio fallisce.

## Cosa fare

- [ ] Il modello produce un piano strutturato, non testo libero: elenco di passaggi con agente e strumento
- [ ] Il piano si valida prima di eseguirlo: ogni entity_id esiste davvero, ogni strumento e' consentito all'agente (il modello non e' fidato)
- [ ] Esecuzione passo per passo, con la verifica dello stato dopo ogni comando
- [ ] Se un passaggio fallisce: un tentativo di correzione, poi ci si ferma e si dice a voce cosa e' riuscito e cosa no
- [ ] Un tetto ai passaggi e ai tentativi, per evitare cicli infiniti
- [ ] Un piano riuscito si puo' salvare come routine

## Criteri di accettazione

- [ ] Il banco di prova ha un gruppo di richieste a piu' passaggi con un tasso di successo misurato
- [ ] Un test simula un passaggio che fallisce e verifica il comportamento
- [ ] Nessun piano supera il tetto di passaggi, nemmeno con un modello che continua ad aggiungerne
