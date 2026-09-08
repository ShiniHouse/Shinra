---
title: "feat(sicurezza-casa): allarme, aperture e notifiche di intrusione"
issue: 23
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Nessuna gestione dell'allarme, delle serrature come sistema, delle telecamere o
dei sensori di apertura. E' il dominio piu' importante fra quelli scoperti,
perche' e' quello per cui una famiglia installa la domotica.

## Cosa fare

- [x] Tool per `alarm_control_panel`: arma in casa, arma fuori casa, disarma,
      stato. Il codice della centrale si puo' passare e arriva a Home
      Assistant, che lo verifica
- [x] Stato aggregato delle aperture. Home Assistant non ha un dominio
      «aperture»: porte e finestre sono `binary_sensor` con una
      `device_class`, le tapparelle sono `cover`, e `on` per un sensore di
      movimento non vuol dire aperto
- [x] Controllo di coerenza all'armamento: rifiuta, dice quale finestra, e si
      puo' forzare dopo che la persona ha confermato
- [ ] Notifica all'intrusione — **l'evento c'e', il canale no.** Le notifiche
      push verso il telefono sono la issue #29 (v0.4.0) e non esistono
      ancora: fingere il contrario sarebbe la peggiore delle promesse, su
      questo dominio. `casa.intrusione` viene pubblicato sul bus con dentro
      chi c'era in casa al momento, e arriva alla dashboard aperta; quando
      #29 arrivera' bastera' sottoscriverlo
- [ ] Simulazione di presenza in vacanza — **in una PR sua.** Ha bisogno di
      programmare accensioni nel tempo, di una memoria di cio' che ha fatto
      ieri sera per non ripetersi, e di un modo per accorgersi che la vacanza
      e' finita: e' una funzione, non una rifinitura di questa
- [x] Il disarmo passa da `sicurezza.comanda`, imposto dal client di Home
      Assistant su ogni chiamata, e ogni rotta richiede una sessione valida.
      Da Alexa serve una conferma in piu' — con il limite scritto nel codice:
      una conferma parlata non protegge da chi e' gia' nella stanza a
      parlare, e la protezione vera resta il codice della centrale

## Criteri di accettazione

- [x] «Arma l'allarme» con una finestra aperta avvisa invece di armare in silenzio
- [x] «Sono chiuse tutte le finestre?» risponde con l'elenco reale — e senza
      sensori dice che non puo' saperlo, invece di rassicurare a vuoto
- [x] Il disarmo da Alexa richiede una conferma aggiuntiva
- [ ] La simulazione di presenza non ripete lo stesso schema due sere di fila
      — con la simulazione, nella sua PR
