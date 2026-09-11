---
title: "feat(interfaccia): ogni lista vuota insegna la mossa successiva"
issue: 127
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: frontend"]
---

## Contesto

La scheda Automazioni, quando non ci sono regole, mostra un titolo, un
pulsante «Aggiorna» e uno spazio bianco. Diciannove righe di markup in tutto,
di cui una e' il contenitore vuoto.

Il proprietario della casa ha guardato quella schermata e ha chiesto: «le
automazioni si creano da sole o no? non so come crearle». La risposta e' che
nascono da una routine con un innesco non vocale — e nessuna delle due
schermate lo dice.

**Una lista vuota che non insegna la mossa successiva e' indistinguibile da
una funzione rotta.** Vale per Automazioni, Modalita', Fonti, Dispositivi e
Conoscenza: cinque schermate, cinque silenzi identici.

## Cosa fare

- [ ] Automazioni: «Non c'e' ancora nessuna automazione. Nascono dalle routine: creane una e dai al primo blocco un innesco che non sia la voce», con il pulsante che porta li'
- [ ] Automazioni: elencare sotto le routine a innesco vocale, dicendo che esistono ma partono solo se chiamate — e' l'informazione che oggi manca del tutto
- [ ] Modalita' e Routine, Fonti, Dispositivi, Conoscenza: uno stato vuoto ciascuno, che nomina l'azione successiva
- [ ] Guardia: ogni contenitore che puo' restare vuoto ha un ramo che scrive qualcosa

## Criteri di accettazione

- [ ] Nessuna delle cinque schermate puo' presentarsi come uno spazio bianco
- [ ] Da ciascuno stato vuoto si raggiunge in un clic l'azione che lo riempie
- [ ] La guardia fallisce se una lista nuova nasce senza stato vuoto
