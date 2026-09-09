---
title: "feat(automazioni): motore di regole con trigger su evento, stato e orario"
issue: 27
milestone: "v0.4.0"
labels: ["tipo: funzione", "area: core", "gravita': alta"]
---

## Contesto

Il sistema e' puramente reattivo: risponde soltanto quando gli si parla. Le
"modalita'" esistenti sono sequenze di azioni, non automazioni: si attivano solo
con una frase.

Con lo scheduler (issue #11) e gli eventi Home Assistant (issue #19) disponibili,
mancano solo i trigger.

## Cosa fare

- [x] Modello di regola: trigger, condizioni, azioni. In JSON e non in colonne:
      le forme cambiano a ogni tipo di trigger nuovo, e una tabella che cambia
      forma a ogni tipo nuovo e' una migrazione a ogni tipo nuovo
- [x] Trigger su evento, stato, orario, presenza, alba e tramonto. **Su stato,
      quello che conta e' l'attraversamento, non lo stare sotto:** «avvisami se
      scende sotto i 15» detto a una casa a 12 gradi non deve suonare a ogni
      lettura del sensore. La differenza e' un avviso al giorno contro trecento,
      e trecento avvisi al giorno diventano zero avvisi letti
- [x] Condizioni componibili: fascia oraria, giorni della settimana, presenza,
      stato di un'entita'. La fascia scavalca la mezzanotte, perche' «dalle 23
      alle 6» e' la finestra piu' usata in una casa ed e' quella che un confronto
      ingenuo sbaglia sempre
- [x] Riuso del grafo: un'azione di tipo `modalita` chiama `activate_mode`. Le
      altre due sono un servizio diretto e un avviso — quest'ultimo possibile
      solo dopo la #29
- [x] Protezione contro i cicli. Si guarda **la catena** e non solo un contatore
      di profondita', perche' il messaggio possa dire quali regole formano
      l'anello: «una regola ha creato un ciclo» manda a rileggerle tutte
- [x] Registro di ogni attivazione — **e di ogni rifiuto**, con il motivo. Una
      regola che non scatta mai e una regola rotta si somigliano troppo

## Criteri di accettazione

- [x] Una regola «se la porta si apre dopo le 23, accendi l'ingresso» funziona
      senza intervento
- [x] Una regola a orario scatta anche a browser chiuso: passa dallo scheduler
      persistente, e si riprogramma da sola dopo ogni scatto
- [x] Due regole che si innescano a vicenda vengono fermate **e segnalate**, con
      i nomi in ordine, su un avviso vero
- [x] Ogni attivazione e' tracciata nel registro

## Tre guardiani, tre cose trovate

**Il ratchet d'architettura** ha bocciato la rotta di prova, che leggeva da
`infra.db`: sarebbe stata la tredicesima voce di `api -> infra`. Adesso passa
dal motore.

**Il test che confronta migrazioni e modelli** ha trovato che le tre colonne
JSON erano `nullable=True` nella migrazione e non-nullable nei modelli. Non e'
un dettaglio: uno schema che diverge dai modelli e' il difetto che si scopre
al primo errore in casa, mesi dopo.

**Il controllo di mutazione** ha trovato due buchi nei test:

- togliendo la guardia su «non so chi c'e' in casa», la funzione rispondeva
  comunque «no» ma con la frase sbagliata — «in casa non c'e' nessuno» detto
  quando non lo si sa e' un'affermazione, non un'ammissione;
- togliendo l'annotazione del rifiuto sulla regola, la suite passava lo
  stesso, perche' l'unico test che la guardava usava la strada
  dell'esecuzione riuscita.

## Cosa e' rimasto fuori

**L'editor a grafo** con nodi condizione e trigger temporale e' la issue #28:
qui le regole si creano dall'API, non dal disegno.
