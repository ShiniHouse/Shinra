---
title: "feat(sicurezza): ruoli personalizzati e permessi per utente"
milestone: "v0.2.0"
labels: ["tipo: funzione", "area: sicurezza", "gravita': alta"]
riferimento: "ADR 0004"
---

## Contesto

Con l'identita' per persona in piedi (issue #3), i permessi diventano
applicabili sul serio. Oggi il profilo distingue adulto, ragazzo e bambino ma
quella distinzione cambia **solo il tono delle risposte**: `restricted_topics`
esiste nel modello e nessuna riga lo applica, e un bambino puo' comandare
qualunque cosa.

I permessi non sono attributi del profilo ma di un **ruolo**, e i ruoli si
creano: oltre ai quattro predefiniti — Amministratore, Adulto, Ragazzo, Ospite
— devono poterne nascere altri, «Collaboratrice domestica», «Nonno», «Ospite
fine settimana», con la propria combinazione di permessi.

Motivazioni e alternative in [ADR 0004](../../adr/0004-identita-ruoli-e-permessi.md).

## Cosa fare

- [ ] Modello `Ruolo`: nome, descrizione, insieme di permessi. Quattro
      predefiniti, modificabili, piu' quelli creati dall'utente
- [ ] Ogni utente ha un ruolo; l'ultimo amministratore non puo' essere
      declassato ne' cancellato
- [ ] Insieme minimo dei permessi:
      `dispositivi.comanda`, `sicurezza.comanda`, `modalita.attiva`,
      `modalita.modifica`, `conoscenza.leggi`, `conoscenza.scrivi`,
      `utenti.gestisci`, `impostazioni.gestisci`
- [ ] `sicurezza.comanda` separato dagli altri dispositivi: serrature e allarme
      hanno conseguenze diverse da una lampadina
- [ ] Verifica dei permessi come dipendenza FastAPI, dichiarata su ogni rotta
- [ ] **L'esecuzione di una routine verifica i permessi di chi la invoca**, non
      di chi l'ha scritta: altrimenti il controllo si aggira scrivendo una routine
- [ ] Applicare finalmente `restricted_topics` prima dell'invio al modello e
      sulla risposta
- [ ] Schermata di gestione ruoli e assegnazione
- [ ] Ogni rifiuto finisce nel registro delle azioni (issue #15)
- [ ] Un rifiuto si spiega: «non hai il permesso di aprire la serratura»,
      non un 403 muto

## Criteri di accettazione

- [ ] Un profilo senza `dispositivi.comanda` non accende una luce, ne' da chat
      ne' da API diretta
- [ ] Un profilo senza `sicurezza.comanda` non apre una serratura nemmeno
      tramite una routine che lo farebbe
- [ ] Un ruolo creato dall'utente e assegnato produce esattamente i permessi scelti
- [ ] L'ultimo amministratore non e' cancellabile ne' declassabile
- [ ] Ogni rifiuto e' tracciato e spiegato all'utente
- [ ] Un test elenca le rotte e fallisce se una non dichiara il permesso richiesto

## Limite dichiarato

Fino ai profili vocali Alexa (`v0.4.0`) il canale vocale non distingue chi
parla: chiunque si rivolga a un Echo agisce con l'identita' della sessione. Per
questo `sicurezza.comanda` **non e' raggiungibile da voce** finche' quel
problema non e' risolto.
