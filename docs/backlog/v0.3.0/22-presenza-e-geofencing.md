---
title: "feat(presenza): presenza delle persone e automazioni di arrivo e uscita"
issue: 22
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`person` e `device_tracker` sono elencati fra i domini visibili, ma nessuna
logica li usa. Il sistema non sa se c'e' qualcuno in casa: e' l'informazione
piu' utile della domotica e oggi e' inutilizzata.

## Cosa fare

- [x] Servizio di presenza che aggrega `person` in uno stato di casa: qualcuno
      presente, casa vuota, prima persona rientrata, ultima persona uscita
- [x] Eventi di transizione pubblicati sul bus della issue #19. Ha richiesto
      di separare i domini **osservati** da quelli **comandabili**: `person`
      non si comanda, e finche' sul bus finiva solo cio' che si comanda la
      presenza non ci sarebbe mai arrivata
- [ ] Collegare la presenza al profilo utente — **non in questa PR.** Sapere
      *chi c'e'* non e' sapere *chi parla*: con due persone in casa non
      disambigua, e con una sola sarebbe un'euristica che sbaglia in silenzio
      proprio quando conta. Il pezzo che serve davvero e' il riconoscimento
      di chi parla (issue #34, v0.4.0); la presenza sara' il suo
      complemento, non il suo sostituto
- [ ] Trigger di presenza nell'editor di routine — **appartiene alla issue
      #27.** Oggi una routine non ha nessun tipo di trigger su evento: ha
      `trigger_phrases`, cioe' frasi da dire. Il motore di regole della
      v0.4.0 e' il lavoro che introduce i trigger, e gli eventi di presenza
      lo aspettano gia' pubblicati sul bus
- [x] Ritardo configurabile contro i falsi negativi del GPS
      (`presenza.ritardo_uscita_secondi`, due minuti per difetto). Vale **solo
      per le uscite**: chi torna a casa vuole la luce accesa adesso, e un
      falso rientro non spegne niente a nessuno

## Criteri di accettazione

- [x] L'uscita dell'ultima persona produce un evento «casa vuota»
- [ ] Una routine attivata dal rientro di una persona — aspetta i trigger
      della issue #27. L'evento c'e' gia', con dentro chi e' rientrato
- [x] Una breve perdita di segnale GPS non genera un falso «casa vuota»

## Cosa resta, e dove

Due caselle non sono state fatte qui perche' appartengono altrove, e
lasciarle mezze fatte sarebbe stato peggio che dichiararlo:

- I **trigger nell'editor di routine** hanno bisogno che i trigger esistano.
  Oggi una routine si attiva a voce o a mano; il motore di regole (issue #27,
  v0.4.0) e' il lavoro che introduce «quando succede X». Gli eventi di
  presenza sono gia' sul bus e lo aspettano.
- Il **collegamento al profilo** — «l'assistente sa con chi parla senza
  chiederlo» — non si ottiene dalla presenza. Sapere chi c'e' in casa non e'
  sapere chi ha parlato: con due persone presenti non disambigua, e con una
  sola sarebbe un'euristica che sbaglia in silenzio proprio quando conta di
  piu'. Serve il riconoscimento di chi parla (issue #34), e la presenza gli
  fara' da complemento.
