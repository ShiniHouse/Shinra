---
title: "refactor(interfaccia): da otto ingressi a tre, senza perdere niente"
issue: 128
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

Otto schede di primo livello, tutte dello stesso peso, ciascuna con
un'etichetta da due parole: Console Vocale, Conoscenza Casa, Fonti & Notizie,
Mappa Dispositivi, Modalita' & Routine, Automazioni, Gestione Utenti,
Impostazioni. Una riga che riempie tutta la larghezza e chiede di essere letta
per intero ogni volta.

Ma non sono la stessa cosa. Tre si usano ogni giorno; cinque si usano una
volta e poi mai piu'. Trattare «parla alla casa» e «configura le fonti RSS»
come voci gemelle e' la scelta che genera piu' affaticamento di qualunque
altra.

## Cosa fare

- [ ] Primo livello: **Console**, **Automazioni e routine**, **Dispositivi**
- [ ] Dietro un solo ingresso di configurazione: Conoscenza, Fonti, Utenti, Impostazioni
- [ ] Unire in un ingresso solo l'elenco delle automazioni e il costruttore di routine

## L'editor a nodi resta al primo livello

Non e' un dettaglio: e' un vincolo. L'editor a grafo **non va nascosto sotto
la configurazione, non va sostituito e non va semplificato**. Rami,
condizioni, ritardi e sequenze non si esprimono in un modulo, ed e' l'unico
posto dove si puo' dire alla casa qualcosa che non sta in una riga.

Sta dentro «Automazioni e routine» perche' e' li' che appartiene, non per
levarlo di mezzo. Lo dice gia' il codice delle rotte: *una modalita' e' una
sequenza che parte a comando, una regola e' una sequenza che parte da sola.*
Sono la stessa cosa vista da due lati, e tenerle in due schede separate e'
esattamente il motivo per cui una routine puo' esistere in una e non comparire
nell'altra senza che nessuna delle due lo spieghi.

## Cosa non fare

- [ ] Non nascondere dietro un menu a panino, su computer, cio' che si usa ogni giorno: si guadagna spazio e si perde la mappa
- [ ] Non togliere le scritte per fare posto alle icone: un'icona senza etichetta e' un indovinello che si ripresenta ogni volta

## Criteri di accettazione

- [ ] Gli ingressi di primo livello sono tre
- [ ] Nessuna funzione raggiungibile prima richiede piu' di due clic in piu'
- [ ] L'editor a nodi si apre dal primo livello
- [ ] Su telefono la navigazione resta una sola, non una seconda scritta a parte
