---
title: "feat(cervello): un endpoint che descrive tutto quello che Shinra sa e fa, come grafo"
issue: 185
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

La scheda «Il Cervello» mostra un grafo: nodi e collegamenti. Tutto il
materiale esiste gia' nel database e nel codice — stanze, dispositivi, alias,
routine, regole, conoscenza, skill — ma nessuno lo espone come grafo. Questa
scheda e' il lato server: un solo endpoint che aggrega, con i permessi giusti.

## Cosa fare

- [ ] `GET /api/cervello` restituisce `{nodi, collegamenti, contatori}`
- [ ] Tipi di nodo: stanza, dispositivo, alias, routine, regola, voce di conoscenza, skill, agente
- [ ] Collegamenti veri, non decorativi: dispositivo -> stanza, alias -> dispositivo, regola -> dispositivi che comanda, routine -> nodi dell'editor, voce di conoscenza -> argomento
- [ ] I contatori (collegamenti, sistemi attivi, agenti pronti) si calcolano dagli stessi dati, cosi' non possono divergere dal grafo
- [ ] Rispetta ruoli e permessi: un profilo vede solo cio' che puo' gia' vedere altrove
- [ ] Il contenuto delle voci di conoscenza non esce: solo titolo e argomento
- [ ] Un tetto ai nodi e il raggruppamento in cluster oltre quella soglia, deciso dal server

## Criteri di accettazione

- [ ] Un test crea una casa di esempio e verifica che ogni oggetto compaia come nodo, una volta sola
- [ ] Nessun collegamento punta a un nodo che non esiste
- [ ] Senza autenticazione risponde `401`; con un profilo limitato non compaiono i nodi vietati
- [ ] La risposta per una casa grande resta sotto un secondo
