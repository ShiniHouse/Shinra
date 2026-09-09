---
title: "feat(skills): clima completo e tapparelle con posizione"
issue: 21
milestone: "v0.3.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

`control_device` supporta `set_temperature` per il clima e `open`/`close` per le
tapparelle. Manca tutto il resto: modalita', ventola, umidita', posizione
intermedia, orientamento delle lamelle.

«Abbassa la tapparella a meta'» e «metti il condizionatore in deumidificazione»
oggi non sono esprimibili.

## Cosa fare

- [x] Clima: modalita' (riscaldamento, raffrescamento, automatico, deumidificazione,
      ventilazione), velocita' ventola, umidita' obiettivo, preset. Le parole con
      cui una persona chiede una modalita' — «caldo», «aria condizionata»,
      «secco» — arrivano tutte al codice giusto
- [x] Tapparelle: posizione percentuale, orientamento lamelle, arresto a meta'
      corsa. **Cento e' aperta, zero e' chiusa**, come in Home Assistant e come
      sulla dashboard: e' il verso che si sbaglia piu' spesso, e c'e' un test che
      lo fissa perche' un commento non fallisce
- [x] Lettura dello stato corrente, non solo comando: `stato_clima` e
      `stato_tapparella`. La temperatura **impostata** e quella **misurata** sono
      due numeri diversi e vengono tenuti distinti
- [x] Aggiornare gli schemi dei tool e il prompt di sistema

## Criteri di accettazione

- [x] «Abbassa la tapparella del salotto al 40%» funziona
- [x] «Metti il clima della camera in deumidificazione a 50%» funziona — sono due
      servizi distinti in Home Assistant, la modalita' e l'umidita' obiettivo
- [x] «A che temperatura e' impostato il termostato?» risponde con il valore reale,
      e non con la temperatura misurata in stanza

## Come e' stato fatto

Il principio che tiene insieme le due meta': **si chiede al dispositivo cosa
sa fare prima di chiedergli di farlo.** Home Assistant non ha «il clima»: ha
entita' `climate` che dichiarano negli attributi quali modalita' accettano, e
`cover` che dichiarano in una maschera di bit se sanno posizionarsi. Un
condizionatore da finestra e una caldaia a condensazione sono la stessa
entita' con capacita' diversissime.

Senza quel controllo il difetto non e' un errore: e' il silenzio. Un
termostato che non deumidifica, a cui si manda `dry`, non risponde «non so
farlo» — non fa niente. La persona sente «fatto», va a dormire, e la mattina
l'umidita' e' la stessa. Per questo ogni rifiuto porta con se' l'elenco di
cio' che il dispositivo sa fare davvero.

C'e' una sola eccezione alla regola, ed e' voluta: sulle **modalita'** un
dispositivo che non dichiara niente viene provato lo stesso, perche' il
rischio e' negare una funzione che c'e'. Sull'**umidita' obiettivo** il
silenzio vale come no, perche' `set_humidity` a un termostato che non la
regola e' un errore secco di Home Assistant e la persona si becca un guasto
invece di una frase che spiega.
