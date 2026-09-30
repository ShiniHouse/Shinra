---
title: "feat(sicurezza): le azioni sensibili chiedono sempre conferma, anche dentro un piano"
issue: 192
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: sicurezza", "gravita': alta"]
---

## Contesto

Un principio permanente di Shinra e' che il modello non e' fidato. Un agente
che pianifica da solo e puo' comandare una serratura o disinserire l'allarme
e' esattamente il caso in cui quel principio deve diventare codice. Questa
scheda e' obbligatoria: la fase non si chiude senza.

## Cosa fare

- [ ] Una classificazione degli strumenti: sicuri, sensibili (serrature, allarme, apertura di garage e porte), vietati agli agenti
- [ ] Un'azione sensibile dentro un piano sospende il piano e chiede conferma al profilo che l'ha richiesto, sul canale da cui e' arrivata
- [ ] Da un canale senza identita' sicura (Alexa senza riconoscimento della voce) un'azione sensibile non parte, e lo dice
- [ ] Una conferma scade dopo pochi minuti e vale per quel solo piano
- [ ] Ogni conferma, rifiuto e scadenza finisce nel registro delle azioni

## Criteri di accettazione

- [ ] Un test prova che nessun percorso, nemmeno un piano o un agente, raggiunge una serratura senza conferma
- [ ] Un test prova che una conferma scaduta non esegue niente
- [ ] Un test prova che la conferma di un profilo non vale per un altro
