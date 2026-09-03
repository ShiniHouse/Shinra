---
title: "feat(canvas): nodi condizione e trigger temporale nell'editor a grafo"
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

L'editor visuale a nodi e' il pezzo migliore del progetto, ma supporta solo
quattro tipi di nodo: innesco vocale, dispositivo, ritardo e annuncio vocale.
Il flusso e' quindi sempre lineare: nessuna diramazione, nessuna condizione.

Il motore di esecuzione fa gia' una visita in ampiezza sul grafo con calcolo dei
gradi entranti: la struttura per i rami c'e' gia'.

## Cosa fare

- [ ] Nodo condizione con due uscite (vero e falso)
- [ ] Nodo trigger temporale: a un orario, a intervalli, all'alba, al tramonto
- [ ] Nodo trigger su evento e su stato, collegato al motore della issue #27
- [ ] Nodo notifica, distinto dall'annuncio vocale
- [ ] Simulazione che mostri quale ramo viene percorso
- [ ] Validazione del grafo prima del salvataggio: nodi scollegati, cicli, rami senza uscita

## Criteri di accettazione

- [ ] Una routine con una condizione percorre il ramo corretto in esecuzione reale
- [ ] Una routine con trigger all'alba scatta all'alba
- [ ] Un grafo non valido non puo' essere salvato, e l'errore dice cosa non va
