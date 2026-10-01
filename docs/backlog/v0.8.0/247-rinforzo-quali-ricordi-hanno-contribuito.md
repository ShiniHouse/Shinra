---
title: "fix(conoscenza): quali ricordi hanno contribuito si sa per richiesta, non per servizio"
issue: 247
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase A — Le fondamenta.** Dipende da: Schema della memoria, budget del contesto.

## Contesto

`servizio_conoscenza.ultimo_recupero` e' una lista **condivisa dal servizio**: due richieste
contemporanee, di due profili diversi, si sovrascrivono. Oggi serve solo a un'etichetta di debug; se
diventa la base del rinforzo (l'uso aggiorna `ultimo_uso`) il difetto diventa un errore di privacy
e di conteggio.

## Cosa fare

- [ ] Il recupero **restituisce** i fatti usati invece di scriverli nel servizio
- [ ] `ultimo_uso` e `usi` si aggiornano dopo la risposta, in blocco e fuori dal percorso della richiesta, e solo per i ricordi **entrati davvero** nel prompt (non quelli tagliati dal budget)

## Criteri di accettazione

- [ ] Due richieste concorrenti di profili diversi non si mescolano (test con due task)
- [ ] Il contatore degli usi cresce di uno per risposta
