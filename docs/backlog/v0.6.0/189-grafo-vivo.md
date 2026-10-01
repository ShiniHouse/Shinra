---
title: "feat(frontend): il grafo vivo, si illumina quando Shinra lavora"
issue: 189
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

E' la parte che fa effetto: si fa una domanda e si vedono accendersi i nodi
che Shinra consulta e comanda. Non va costruita prima che l'agente sia
affidabile: un bel grafo che si illumina su una risposta sbagliata e' una
demo, non un prodotto. Dipende dalla scheda degli eventi dell'agente.

## Cosa fare

- [x] Ogni evento dell'agente accende il nodo corrispondente e i collegamenti verso di esso, con dissolvenza
- [x] Un percorso leggibile: dalla richiesta alla skill, al dispositivo
- [x] Un errore si vede (nodo in rosso), non scompare
- [x] Rispetta la riduzione del movimento: senza animazioni il nodo cambia solo colore
- [x] Un registro in chiaro accanto al grafo con le stesse informazioni, per chi non vede bene o legge con un lettore di schermo

## Criteri di accettazione

- [x] Un test dei gesti invia una richiesta e vede accendersi i nodi attesi
- [x] Senza eventi il grafo resta fermo e non consuma CPU
- [x] Il registro in chiaro e' coerente con l'animazione

## Com'e' andata

- `cervello_attivita.js`: gli eventi `agente.*` diventano accensioni sul disegno (alone, collegamenti
  del nodo, percorso tratteggiato modello → fatti → strumento → dispositivo → modello) e voci di un
  **registro in chiaro** (`role="log"`, `aria-live`) accanto al grafo. Disegno e registro nascono dallo
  stesso evento: non possono dire cose diverse.
- Il percorso **non e' un collegamento del grafo**: ha un altro tratto (tratteggiato), dura pochi
  secondi, e le tappe parallele (i fatti consultati) non sono messe in fila.
- Un errore resta rosso 20 s (le accensioni normali 4 s) e il registro lo scrive in rosa.
- **Movimento ridotto**: nessuna dissolvenza, il nodo e' acceso o spento.
- **Fermo se non succede niente**: nessun ciclo di disegno e nessun timer (un solo `setTimeout`,
  armato solo con qualcosa di acceso). `data-animando` sul canvas lo rende osservabile ai test.
- Backend: il modello di Ollama e' ora un nodo del grafo (`agente:modello`, collegato a tutti gli
  strumenti) perche' gli eventi abbiano da dove partire; un secondo evento `agente.richiesta` con
  `al_modello` segna quando la richiesta passa al modello; uno strumento fallito emette `agente.errore`
  con il nodo dello strumento (e del dispositivo, se c'era).
- Limite noto: gli eventi arrivano solo al profilo che ha fatto la richiesta; chi guarda il Cervello
  da un'altra sessione non vede lavorare la casa per conto di altri (scelta di riservatezza di #188).
- Come dice il contesto della scheda, questo non va preso come prova che l'agente e' affidabile: la
  misura sul modello vero (#183) resta da fare.
