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

- [ ] Spostare modello e invocazione Alexa in Impostazioni, dove si va quando si vogliono cambiare
- [ ] Rendere i tool invocati una finestra da aprire quando qualcosa non torna, non un pannello acceso
- [ ] Lasciare nella colonna cio' che riguarda **adesso**: timer e promemoria attivi, cosa sta facendo la casa, cosa scattera' fra poco (il prossimo scatto lo sa gia' `/api/regole`)
- [ ] Mantenere raggiungibile tutto: nessun dato sparisce, cambia dove si guarda

## Criteri di accettazione

- [ ] La colonna di destra mostra solo informazioni che cambiano nell'arco di una giornata
- [ ] Modello e invocazione Alexa restano leggibili, in Impostazioni
- [ ] I tool invocati restano consultabili in un clic
- [ ] Gli elementi visibili a riposo sulla schermata di casa calano di almeno un terzo
