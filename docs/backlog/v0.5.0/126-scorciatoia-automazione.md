---
title: "feat(automazioni): una scorciatoia per «a quest'ora fai questo»"
issue: 126
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

`POST /api/regole` esiste dalla v0.3.0 e **la dashboard non la chiama mai**.
L'unico modo di creare un'automazione e' aprire l'editor a nodi, disegnare una
routine e cambiare il tipo di innesco del primo blocco.

Per «alle 23 spegni tutto» — fra le richieste piu' frequenti di una casa — e'
un giro lungo. Per tutto il resto l'editor e' insostituibile.

## L'editor non si tocca

Questa e' una **porta in piu' sulla stessa stanza, non una porta al posto di
quella**. L'editor a nodi resta esattamente com'e', al primo livello, e resta
la strada per rami, condizioni, ritardi e sequenze.

La scorciatoia copre il caso semplice: un innesco, nessuna condizione, una o
due azioni. Quando serve di piu', porta all'editor invece di crescere.

## Cosa fare

- [ ] Un modulo breve in «Automazioni e routine»: quando (orario, alba, tramonto, stato, evento), cosa fare, e basta
- [ ] Usare `POST /api/regole`, che ha gia' la sua validazione: un innesco sconosciuto viene rifiutato con il motivo
- [ ] Il rifiuto del server si legge nella schermata, non in un `alert`
- [ ] Un collegamento «serve qualcosa di piu' complicato?» che apre l'editor con quell'innesco gia' impostato
- [ ] Le regole nate cosi' sono indistinguibili dalle altre nell'elenco: stessa riga, stesso prossimo scatto, stessa prova

## Criteri di accettazione

- [ ] «Alle 23 spegni tutto» si crea senza aprire l'editor
- [ ] Una regola creata dalla scorciatoia scatta davvero, e il suo prossimo scatto compare nell'elenco
- [ ] Il passaggio all'editor non perde cio' che era gia' stato scritto nel modulo
- [ ] Nessun percorso dell'editor viene rimosso o accorciato
