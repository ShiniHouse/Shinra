# Banco della memoria — server-soglie

> Misurato sul **server di casa** (i5-8500T, senza GPU) il 2026-10-20, con i vettori di `nomic-embed-text`. La parte sopra
> è identica a `2026-10-20-server-ablazione.md`; qui conta la tabella della soglia.

## Soglia di punteggio (con i vettori)

| Soglia | recall@3 | recall@8 | MRR | Silenzio |
| ---: | ---: | ---: | ---: | ---: |
| 0.28 (era) | 83% | 88% | 0.74 | 0% |
| 0.35 | 83% | 88% | 0.74 | 0% |
| **0.40 (scelta)** | 83% | 88% | 0.74 | 20% |
| 0.45 | 79% | 83% | 0.72 | 60% |
| 0.50 | 74% | 74% | 0.69 | 100% |
| 0.55 | 69% | 69% | 0.64 | 100% |
| 0.60 | 62% | 62% | 0.57 | 100% |
| 0.65 | 57% | 57% | 0.52 | 100% |

**Scelta: 0.40**, l'ultimo punto in cui non si perde nessun ricordo giusto. Da 0.45 si perdono ricordi (recall@3 79%) per
guadagnare silenzio; a 0.50 il silenzio è pieno (100%) ma il recall@3 scende al 74%. Un ricordo mancato costa più di un ricordo
di troppo (otto ricordi in più sono circa 250 token su 4096). Il corpus ha 5 domande senza risposta: il silenzio si muove a
scatti del 20%, quindi 0.40 → 20% non vuol dire «un quinto delle volte» in una casa vera, ma che la soglia comincia a lavorare.
Senza vettori resta 0.28 (somiglianza testuale).
