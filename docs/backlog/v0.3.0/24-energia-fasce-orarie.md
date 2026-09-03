---
title: "feat(energia): consumi, costi e fasce orarie italiane"
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

- [ ] Lettura dei sensori di energia da Home Assistant, per dispositivo dove disponibile
- [ ] Calcolo delle fasce F1, F2 e F3 secondo il calendario italiano, festivi inclusi
- [ ] Tariffa configurabile: monoraria o bioraria, con prezzo per fascia
- [ ] Storicizzazione dei consumi sul database della issue #12
- [ ] Risposte a «quanto ho consumato oggi», «quanto mi costa tenere acceso questo», «in che fascia siamo adesso»
- [ ] Riepilogo giornaliero e mensile con i carichi piu' costosi

## Criteri di accettazione

- [ ] La fascia corrente e' calcolata correttamente, festivi e domeniche inclusi
- [ ] «Quanto ho consumato oggi» risponde con kWh e costo stimato
- [ ] Lo storico e' interrogabile per giorno, settimana e mese
- [ ] Senza sensori di energia il sistema lo dice, invece di inventare un numero
