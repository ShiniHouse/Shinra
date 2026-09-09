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
      chi c'era in casa al momento. **Nessuno lo ascolta**, nemmeno il
      WebSocket della dashboard: questa scheda diceva il contrario, ed era
      sbagliato. Lo aggancia la #29
- [x] Simulazione di presenza in vacanza. Il piano di ogni sera e' calcolato
      da `domain/simulazione.py` — puro, riproducibile da un seme, e con il
      confronto esplicito con la sera prima. La capacita' sta in
      `skills/simulazione.py`; l'unica parte che reagisce da sola, spegnersi
      appena qualcuno rientra, e' in `services/simulazione.py` e ascolta
      `casa.abitata` senza sapere chi lo pubblica. Il modo di accorgersi che
      la vacanza e' finita e' la presenza (#22): rifiuta di partire con
      qualcuno in casa, e smette da sola al rientro
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
- [x] La simulazione di presenza non ripete lo stesso schema due sere di fila.
      Provato su dodici sere **con lo stesso seme**: e' l'unico caso in cui il
      confronto con ieri deve fare qualcosa, perche' due semi diversi
      darebbero due piani diversi da soli e il test passerebbe anche senza il
      controllo
