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

- [x] Automazioni: «Non c'e' ancora nessuna automazione. Nascono dalle routine: creane una e dai al primo blocco un innesco che non sia la voce», con il pulsante che porta li'
- [x] Automazioni: elencare sotto le routine a innesco vocale, dicendo che esistono ma partono solo se chiamate — e' l'informazione che oggi manca del tutto
- [x] Modalita' e Routine, Fonti, Dispositivi, Conoscenza: uno stato vuoto ciascuno, che nomina l'azione successiva
- [x] Guardia: ogni contenitore che puo' restare vuoto ha un ramo che scrive qualcosa

## Criteri di accettazione

- [x] Nessuna delle cinque schermate puo' presentarsi come uno spazio bianco
- [x] Da ciascuno stato vuoto si raggiunge in un clic l'azione che lo riempie
- [x] La guardia fallisce se una lista nuova nasce senza stato vuoto

## Com'e' andata

Fatta con la PR #131.

**La premessa della scheda era sbagliata, ed e' stato misurato.** «Cinque
schermate, cinque silenzi identici» non corrispondeva al vero: tutte le liste
che potevano restare vuote avevano gia' la loro frase, e lo stato vuoto delle
Automazioni aveva gia' una guardia dalla #108. La correzione e' scritta in un
commento sulla issue.

Cio' che mancava davvero era la seconda casella: le routine a innesco vocale
non comparivano da nessuna parte fra le automazioni, ed e' la domanda da cui
la scheda e' nata. Quella e' stata costruita.

La guardia `test_ogni_elenco_che_puo_restare_vuoto_dice_qualcosa` tiene il
resto, con sei eccezioni dichiarate con il loro motivo.
