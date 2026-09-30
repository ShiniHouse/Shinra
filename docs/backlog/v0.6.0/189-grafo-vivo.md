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

- [ ] Ogni evento dell'agente accende il nodo corrispondente e i collegamenti verso di esso, con dissolvenza
- [ ] Un percorso leggibile: dalla richiesta alla skill, al dispositivo
- [ ] Un errore si vede (nodo in rosso), non scompare
- [ ] Rispetta la riduzione del movimento: senza animazioni il nodo cambia solo colore
- [ ] Un registro in chiaro accanto al grafo con le stesse informazioni, per chi non vede bene o legge con un lettore di schermo

## Criteri di accettazione

- [ ] Un test dei gesti invia una richiesta e vede accendersi i nodi attesi
- [ ] Senza eventi il grafo resta fermo e non consuma CPU
- [ ] Il registro in chiaro e' coerente con l'animazione
