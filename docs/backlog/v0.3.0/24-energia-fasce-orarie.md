---
title: "feat(energia): consumi, costi e fasce orarie italiane"
issue: 24
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Nessun monitoraggio dei consumi, nessuna nozione di costo, nessuna conoscenza
delle fasce F1, F2 e F3. E' il caso d'uso domestico italiano piu' concreto e il
meno servito dagli assistenti commerciali, che non conoscono la tariffazione
bioraria.

E' anche il fondamento della funzione «consulente energetico» prevista dopo la 1.0.0.

## Cosa fare

- [x] Lettura dei sensori di energia da Home Assistant, per dispositivo dove
      disponibile. Solo i contatori (`device_class: energy` con `state_class`
      cumulativa): un sensore di potenza dice quanti watt assorbe adesso, e
      sommarlo darebbe un numero senza significato
- [x] Calcolo delle fasce F1, F2 e F3 secondo il calendario italiano, festivi
      inclusi. Pasquetta e' calcolata, non elencata: e' l'unico festivo
      nazionale mobile. E l'ora e' quella di Roma, non UTC — Home Assistant
      scrive in UTC, e una fascia calcolata li' sbaglia di un'ora d'inverno e
      di due d'estate, proprio nelle ore in cui le fasce cambiano
- [x] Tariffa configurabile: monoraria, bioraria o trioraria. La bioraria mette
      F2 e F3 sotto lo stesso prezzo, come i contratti italiani. Senza tariffa
      configurata si risponde lo stesso, ma dichiarando che e' una stima
- [x] Storicizzazione sul database. Si conservano le **letture grezze**, non i
      consumi gia' calcolati: le differenze si ricalcolano, le letture perdute
      no. La fascia invece si scrive, perche' ARERA puo' cambiare gli orari e
      una bolletta di due anni fa deve restare divisa come lo era allora
- [x] Risposte a «quanto ho consumato oggi», «quanto mi costa tenere acceso
      questo», «in che fascia siamo adesso»: `consumo_energia`,
      `costo_dispositivo`, `fascia_corrente`
- [x] Riepilogo per giorno, settimana e mese, con la fascia in cui si e'
      consumato di piu' — che e' l'unica cosa su cui una persona puo' agire.
      Il dettaglio per singolo carico c'e' quando c'e' un contatore per
      dispositivo: senza, si dice invece di ripartire a caso

## Criteri di accettazione

- [x] La fascia corrente e' calcolata correttamente, festivi e domeniche inclusi
- [x] «Quanto ho consumato oggi» risponde con kWh e costo stimato
- [x] Lo storico e' interrogabile per giorno, settimana e mese
- [x] Senza sensori di energia il sistema lo dice, invece di inventare un
      numero. E' il criterio che vale piu' degli altri, ed e' quello a cui
      sono dedicati piu' test: chi chiede quanto ha consumato e sente «zero»
      crede di non aver consumato niente

## Cosa e' rimasto fuori, e perche'

**Il costo di un dispositivo su un periodo.** «Quanto mi e' costata la
lavatrice questo mese» ha risposta solo dove c'e' un contatore dedicato, e in
una casa normale ce n'e' uno solo, generale. Ripartire il totale fra i
dispositivi sarebbe inventare: si risponde per il contatore che esiste, e per
gli altri si dice che non si sa.

**La ripartizione di un'ora a cavallo di un cambio fascia.** Con letture
orarie l'ora finisce tutta nella fascia della sua fine. Dividerla in
proporzione richiederebbe di sapere *quando*, dentro quell'ora, si e'
consumato — che e' esattamente cio' che un contatore cumulativo non dice.
L'errore vale al massimo un'ora al giorno.

**Il consulente energetico** («conviene fare la lavatrice adesso o alle
23?»). E' la funzione prevista dopo la 1.0.0, e adesso ha le fondamenta:
`fascia_corrente` sa gia' dire quando cambia la fascia.
