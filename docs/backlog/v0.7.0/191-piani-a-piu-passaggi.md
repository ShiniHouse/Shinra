---
title: "feat(agente): piani a piu' passaggi, con correzione se un passaggio fallisce"
issue: 191
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

«Prepara la casa per la sera» non e' uno strumento: sono luci, tapparelle,
clima e forse un allarme. Oggi il ciclo fa una scelta alla volta. Serve un
piano: scomporre, eseguire, verificare, e correggersi se un passaggio fallisce.

> **Spostata dalla `0.6.0` alla `0.7.0` (2026-10-06).** Con il router e gli agenti di dominio la categoria
> «piu' passaggi» del banco e' a 5/10 sul portatile (6/10 sul server), e un piano strutturato e' il lavoro piu'
> grosso della fase per un guadagno incerto con il 3B su questo hardware. Si riprende con i numeri del banco rifatto
> sull'hardware nuovo, o quando la casa mostra che serve: il ciclo attuale accetta gia' piu' chiamate in uno stesso
> giro, e il controllo del dominio e del bersaglio valido (#190, #290) vale anche per un piano.

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
