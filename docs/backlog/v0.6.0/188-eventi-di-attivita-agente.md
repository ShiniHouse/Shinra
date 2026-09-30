---
title: "feat(agente): il ciclo dell'agente racconta cosa sta facendo, evento per evento"
issue: 188
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Perche' il grafo si illumini quando Shinra lavora, il ciclo che ascolta una
richiesta, consulta la conoscenza, sceglie una skill e comanda un
dispositivo deve emettere eventi. Il bus di eventi e il canale verso la
dashboard esistono gia': manca che il ciclo dell'agente li usi per raccontarsi.

## Cosa fare

- [ ] Eventi tipizzati: richiesta ricevuta, conoscenza consultata (quali voci), skill scelta, dispositivo comandato, risposta data, errore
- [ ] Ogni evento porta l'identificativo del nodo del grafo a cui si riferisce
- [ ] Il canale degli eventi verso la dashboard li inoltra solo al profilo che ha fatto la richiesta (un altro utente non deve vedere cosa chiede un familiare)
- [ ] Il contenuto della richiesta non viaggia nell'evento: solo il tipo e i nodi toccati
- [ ] Emettere un evento non puo' rallentare ne' rompere una risposta

## Criteri di accettazione

- [ ] Un test esegue una richiesta vera con un modello finto e verifica la sequenza di eventi
- [ ] Un test verifica che un secondo profilo non riceva gli eventi del primo
- [ ] Se il canale e' giu', la risposta arriva lo stesso
