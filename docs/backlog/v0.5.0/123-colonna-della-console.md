---
title: "refactor(interfaccia): la colonna della console racconta adesso, non la diagnostica"
issue: 123
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

La console vocale e' la schermata che si apre per prima, e la sua colonna di
destra — un terzo dello schermo, sempre acceso — contiene:

- **Stato Sistema**: il nome del modello (`llama3.2:1b`) e la frase di
  invocazione di Alexa;
- **Tool invocati da Shinra**: l'elenco delle chiamate interne;
- **Timer & Promemoria live**.

Solo l'ultimo riguarda chi abita la casa. Gli altri due sono diagnostica:
utili a chi costruisce l'hub, rumore permanente per chi lo usa. Il modello non
cambia da un'ora all'altra, e la frase di invocazione si legge una volta nella
vita.

## Cosa fare

- [x] Spostare modello e invocazione Alexa in Impostazioni, dove si va quando si vogliono cambiare
- [x] Rendere i tool invocati una finestra da aprire quando qualcosa non torna, non un pannello acceso
- [x] Lasciare nella colonna cio' che riguarda **adesso**: timer e promemoria attivi, cosa sta facendo la casa, cosa scattera' fra poco (il prossimo scatto lo sa gia' `/api/regole`)
- [x] Mantenere raggiungibile tutto: nessun dato sparisce, cambia dove si guarda

## Criteri di accettazione

- [x] La colonna di destra mostra solo informazioni che cambiano nell'arco di una giornata
- [x] Modello e invocazione Alexa restano leggibili, in Impostazioni
- [x] I tool invocati restano consultabili in un clic
- [ ] Gli elementi visibili a riposo sulla schermata di casa calano di almeno un terzo

## Com'e' andata

Fatta con la PR #132.

**Un criterio non e' stato raggiunto, ed e' scritto nella guardia.** Il calo
degli elementi a riposo nella colonna e' del **30%**, non di un terzo: 27 tag
diventati 19. Non poteva esserlo — la scheda chiedeva insieme di *togliere* la
diagnostica e di *aggiungere* i prossimi scatti. Gli altri numeri: titoli da 3
a 1, pannelli accesi da 3 a 2, informazioni di diagnostica da 3 a nessuna.
`test_la_colonna_della_console_resta_leggera` tiene il tetto misurato.

Trovato strada facendo: la frase di invocazione di Alexa nella console era
**scritta a mano** e restava «Kyra» anche dopo averla rinominata. Adesso viene
dal campo.
