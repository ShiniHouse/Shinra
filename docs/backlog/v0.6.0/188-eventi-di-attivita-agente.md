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

- [x] Eventi tipizzati: richiesta ricevuta, conoscenza consultata (quali voci), skill scelta, dispositivo comandato, risposta data, errore
- [x] Ogni evento porta l'identificativo del nodo del grafo a cui si riferisce
- [x] Il canale degli eventi verso la dashboard li inoltra solo al profilo che ha fatto la richiesta (un altro utente non deve vedere cosa chiede un familiare)
- [x] Il contenuto della richiesta non viaggia nell'evento: solo il tipo e i nodi toccati
- [x] Emettere un evento non puo' rallentare ne' rompere una risposta

## Criteri di accettazione

- [x] Un test esegue una richiesta vera con un modello finto e verifica la sequenza di eventi
- [x] Un test verifica che un secondo profilo non riceva gli eventi del primo
- [x] Se il canale e' giu', la risposta arriva lo stesso

## Com'e' andata

- `domain/eventi_agente.py`: sei tipi (`agente.richiesta`, `.conoscenza`, `.skill`, `.dispositivo`,
  `.risposta`, `.errore`) e il modo di costruirli. Un evento accetta solo booleani, numeri e un
  `motivo` da due parole: la frase, gli argomenti di uno strumento, il testo di un fatto e il
  messaggio di un errore **non possono** entrarci (`ValueError`).
- `services/cronaca.py`: l'agente chiama questi metodi nei suoi punti di passaggio. Ogni evento
  parte in un compito a parte, senza attenderlo, e ogni eccezione si ferma li'.
- I nodi sono quelli del grafo del Cervello: `strumento:<nome>`, `dispositivo:<entity_id>`,
  `fatto:<id>`, `sistema:modello`. «Richiesta ricevuta» non ha nodo: non si sa ancora se rispondera'
  un intento o il modello.
- `/ws/eventi`: gli eventi `agente.*` arrivano solo al profilo che ha fatto la richiesta; il
  proprietario non viene inoltrato al browser. Senza autenticazione la casa e' di tutti.
- Limite noto: la conoscenza consultata ha i nodi solo quando il recupero seleziona i fatti
  (oltre venticinque); sotto, il prompt li manda tutti e non c'e' una scelta da raccontare.
