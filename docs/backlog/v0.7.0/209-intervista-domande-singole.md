---
title: "feat(apprendimento): una domanda per volta, e niente domande su cio' che la casa gia' sa"
issue: 209
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Residuo della #170, tappa uno. L'intervista adesso dice quando non ha capito e
mostra cosa ha capito prima di salvarlo (#171, #174). Restano i difetti che si
vedono solo parlandoci:

- le domande sono tre in una, e chi risponde ne coglie una;
- chiede cose che la casa ha gia' nel database (chi abita qui, le stanze);
- se la risposta e' troppo povera non insiste mai.

## Cosa fare

- [ ] Una domanda per volta: i passi che ne contengono piu' di una si dividono
- [ ] Prima di ogni domanda si guarda il database: un fatto gia' presente si salta, o si chiede di confermarlo invece di ridirlo
- [ ] Se l'estrazione non tira fuori niente, si chiede **una volta sola** di approfondire, con un esempio concreto, poi si passa oltre
- [ ] Il riepilogo prima di salvare resta com'e'

## Criteri di accettazione

- [ ] Nessun passo dell'intervista contiene piu' di una domanda (un test lo verifica sui testi)
- [ ] Con la conoscenza gia' popolata, l'intervista non rifa' le domande a cui ha risposta (test con un database di esempio)
- [ ] Una risposta povera produce un solo approfondimento, non un ciclo
- [ ] Provata in casa con il modello vero: la scheda riporta cosa ha estratto e cosa no
