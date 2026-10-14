# Banco della memoria — solo-testo-con-storia

Data: 2026-10-14 · solo testo · 31 ricordi, 21 domande con risposta, 5 senza.

| Misura | Valore |
| :--- | ---: |
| recall@1 | 48% |
| recall@3 | 67% |
| recall@8 | 67% |
| MRR | 0.57 |
| Silenzio (senza risposta, non esce niente) | 100% |

| Tipo | Domande | recall@3 | MRR |
| :--- | ---: | ---: | ---: |
| conflitto | 2 | 100% | 0.50 |
| delicata | 2 | 100% | 0.75 |
| diretta | 6 | 100% | 0.92 |
| doppia | 2 | 0% | 0.00 |
| numero | 3 | 100% | 1.00 |
| parafrasi | 6 | 17% | 0.17 |

## Ricordi mancati

- `d07` «Come mi collego a internet?»: attesi ['r01'], trovati []
- `d08` «A che ora va a letto il ragazzo?»: attesi ['r05'], trovati ['r13', 'r26']
- `d10` «Chi chiamo se perde un tubo?»: attesi ['r14'], trovati []
- `d11` «Quanto e' calda la casa la notte?»: attesi ['r12'], trovati []
- `d12` «Quando si ricarica l'auto?»: attesi ['r15'], trovati []
- `d16` «Cosa devo portare fuori il giovedi?»: attesi ['r09', 'r27'], trovati []
- `d17` «Quando viene qualcuno a occuparsi del giardino o delle pulizie?»: attesi ['r23', 'r19'], trovati []

## Ablazione della storia (peso 0.1 per fattore)

| Pesi | recall@3 | MRR | Silenzio |
| :--- | ---: | ---: | ---: |
| nessuno (oggi) | 67% | 0.57 | 100% |
| solo importanza | 67% | 0.67 (+0.10) | 100% |
| solo recenza | 67% | 0.67 (+0.10) | 100% |
| solo uso | 67% | 0.67 (+0.10) | 100% |
| tutti e tre | 67% | 0.67 (+0.10) | 100% |
