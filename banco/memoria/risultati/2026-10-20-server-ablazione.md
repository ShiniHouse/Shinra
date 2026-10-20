# Banco della memoria — server-ablazione

> Misurato sul **server di casa** (i5-8500T, senza GPU) il 2026-10-20, con i vettori del modello di embedding configurato
> (`nomic-embed-text`). I numeri sono quelli stampati dallo script, copiati dall'output del server.

Data: 2026-10-20 · testo + vettori · 31 ricordi, 21 domande con risposta, 5 senza.

| Misura | Valore |
| :--- | ---: |
| recall@1 | 60% |
| recall@3 | 83% |
| recall@8 | 88% |
| MRR | 0.74 |
| Silenzio (senza risposta, non esce niente) | 0% |

| Tipo | Domande | recall@3 | MRR |
| :--- | ---: | ---: | ---: |
| conflitto | 2 | 100% | 1.00 |
| delicata | 2 | 100% | 0.75 |
| diretta | 6 | 100% | 0.92 |
| doppia | 2 | 75% | 0.75 |
| numero | 3 | 100% | 1.00 |
| parafrasi | 6 | 50% | 0.34 |

## Ricordi mancati

- `d07` «Come mi collego a internet?»: attesi ['r01'], trovati ['r02', 'r25', 'r17', 'r28', 'r21', 'r00', 'r20', 'r26']
- `d10` «Chi chiamo se perde un tubo?»: attesi ['r14'], trovati ['r30', 'r11', 'r08', 'r17', 'r13', 'r20', 'r25', 'r21']
- `d17` «Quando viene qualcuno a occuparsi del giardino o delle pulizie?»: attesi ['r23', 'r19'], trovati ['r23', 'r26', 'r08', 'r05', 'r13', 'r25', 'r30', 'r11']

## Rumore (non c'era nulla da trovare)

- `d18` «Che tempo fa domani?»: trovati ['r08', 'r17', 'r05', 'r30', 'r07', 'r28', 'r26', 'r20']
- `d19` «Raccontami una barzelletta»: trovati ['r06', 'r13', 'r11', 'r08', 'r03', 'r30', 'r26', 'r12']
- `d20` «Quanto fa 12 per 12?»: trovati ['r07', 'r08', 'r12', 'r14', 'r24', 'r30', 'r29', 'r11']
- `d21` «A che ora e' la cosa?»: trovati ['r08', 'r17', 'r20', 'r06', 'r03', 'r15', 'r16', 'r26']
- `d22` «Dov'e' quello?»: trovati ['r28', 'r30', 'r17', 'r29', 'r20', 'r08', 'r14', 'r26']

## Ablazione della storia (peso 0.1 per fattore)

| Pesi | recall@3 | MRR | Silenzio |
| :--- | ---: | ---: | ---: |
| nessuno (oggi) | 83% | 0.74 | 0% |
| solo importanza | 83% | 0.80 (+0.06) | 0% |
| solo recenza | 83% | 0.80 (+0.06) | 0% |
| solo uso | 83% | 0.80 (+0.06) | 0% |
| tutti e tre | 74% | 0.72 (-0.02) | 0% |

## Cosa si è concluso

- **I pesi della storia restano a zero.** Un fattore da solo sposta l'MRR di +0.06 senza cambiare il recall@3; tutti e tre
  insieme peggiorano (recall@3 da 83% a 74%, MRR -0.02). Non c'è un guadagno chiaro, e la storia del corpus è sintetica.
- **I vettori aiutano** (recall@3 da 67% a 83%, MRR da 0.57 a 0.74; le parafrasi da 17% a 50%) **ma il silenzio crolla da 100% a 0%**:
  con il modello vero ogni frase somiglia un po' a ogni altra, e la soglia di oggi (0.28), scelta sul solo testo, lascia passare
  otto ricordi anche per «raccontami una barzelletta». Con più di 25 ricordi (sotto si manda tutto) il prompt si riempie di rumore.
  Da misurare: la scansione della soglia (`--soglie`).
