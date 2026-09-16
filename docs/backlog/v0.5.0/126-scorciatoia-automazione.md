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

- [x] Un modulo breve in «Automazioni e routine»: quando (orario, alba, tramonto, stato, evento), cosa fare, e basta
- [x] Usare `POST /api/regole`, che ha gia' la sua validazione: un innesco sconosciuto viene rifiutato con il motivo
- [x] Il rifiuto del server si legge nella schermata, non in un `alert`
- [x] Un collegamento «serve qualcosa di piu' complicato?» che apre l'editor con quell'innesco gia' impostato
- [x] Le regole nate cosi' sono indistinguibili dalle altre nell'elenco: stessa riga, stesso prossimo scatto, stessa prova

## Criteri di accettazione

- [x] «Alle 23 spegni tutto» si crea senza aprire l'editor
- [x] Una regola creata dalla scorciatoia scatta davvero, e il suo prossimo scatto compare nell'elenco
- [x] Il passaggio all'editor non perde cio' che era gia' stato scritto nel modulo
- [x] Nessun percorso dell'editor viene rimosso o accorciato

## Com'e' andata

Fatta con la PR #140.

Il test di accettazione manda alla rotta vera il corpo che il modulo
manderebbe, costruito **eseguendo le sue funzioni** invece di riscriverle, e
controlla che la regola compaia nell'elenco con il prossimo scatto alle 23 e
l'azione sul dispositivo giusto.

**Provando a rompere la scorciatoia e' saltato fuori un difetto del server**:
un'azione su un dispositivo senza entita' veniva accettata, scattava, chiamava
il servizio su una stringa vuota e tornava «riuscita». L'elenco diceva «ultima
volta: riuscita» e la luce restava accesa. `_valida` applica adesso lo stesso
metro di «una regola senza azioni non fa niente» anche alle azioni che non
dicono su cosa agire.
