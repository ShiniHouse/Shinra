---
title: "feat(sicurezza): ruoli personalizzati e permessi per utente"
issue: 46
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

- [x] Modello `Ruolo`: nome, descrizione, insieme di permessi. Quattro
      predefiniti, modificabili, piu' quelli creati dall'utente
- [x] Ogni utente ha un ruolo; l'ultimo amministratore non puo' essere
      declassato ne' cancellato
- [x] Insieme minimo dei permessi:
      `dispositivi.comanda`, `sicurezza.comanda`, `modalita.attiva`,
      `modalita.modifica`, `conoscenza.leggi`, `conoscenza.scrivi`,
      `utenti.gestisci`, `impostazioni.gestisci`
- [x] `sicurezza.comanda` separato dagli altri dispositivi: serrature e allarme
      hanno conseguenze diverse da una lampadina
- [x] Verifica dei permessi come dipendenza FastAPI, dichiarata su ogni rotta
- [x] **L'esecuzione di una routine verifica i permessi di chi la invoca**, non
      di chi l'ha scritta: altrimenti il controllo si aggira scrivendo una routine
- [x] Applicare finalmente `restricted_topics` prima dell'invio al modello e
      sulla risposta — gia' fatto nella v0.1.0 (`core/argomenti_vietati.py`,
      issue #5), verificato dai suoi test
- [x] Schermata di gestione ruoli e assegnazione — fatta nella PR di frontend
      che porta anche i dispositivi fidati (issue #47). I permessi di ogni
      ruolo sono caselle da spuntare, i ruoli propri si creano dalla pagina, i
      predefiniti si modificano ma non si cancellano. E il ruolo di un profilo
      **si sceglie**: veniva dedotto da avatar e fascia d'eta', e la fascia
      «ragazzo» finiva nel ramo `adult` — un tredicenne con le serrature.
- [x] Ogni rifiuto finisce nel registro delle azioni (issue #15)
- [x] Un rifiuto si spiega: «non hai il permesso di aprire la serratura»,
      non un 403 muto

## Criteri di accettazione

- [x] Un profilo senza `dispositivi.comanda` non accende una luce, ne' da chat
      ne' da API diretta
- [x] Un profilo senza `sicurezza.comanda` non apre una serratura nemmeno
      tramite una routine che lo farebbe
- [x] Un ruolo creato dall'utente e assegnato produce esattamente i permessi scelti
- [x] L'ultimo amministratore non e' cancellabile ne' declassabile
- [x] Ogni rifiuto e' tracciato e spiegato all'utente
- [x] Un test elenca le rotte e fallisce se una non dichiara il permesso richiesto

## Limite dichiarato

Fino ai profili vocali Alexa (`v0.4.0`) il canale vocale non distingue chi
parla: chiunque si rivolga a un Echo agisce con l'identita' della sessione. Per
questo `sicurezza.comanda` **non e' raggiungibile da voce** finche' quel
problema non e' risolto.
