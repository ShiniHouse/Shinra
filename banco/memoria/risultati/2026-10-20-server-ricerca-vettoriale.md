# Ricerca vettoriale — i5-8500T, 16 GB

Data: 2026-10-20 · Python 3.11.2 su Linux x86_64 · vettori da 768 numeri, mediana di 5 richieste.

| Ricordi | Coseno, Python puro (oggi) | Lettura JSON dei vettori (oggi) | numpy |
| ---: | ---: | ---: | ---: |
| 100 | 9.1 ms | 22.9 ms | 0.1 ms |
| 1,000 | 91.4 ms | 231.9 ms | 0.1 ms |
| 5,000 | 449.5 ms | 1,152.6 ms | 0.6 ms |
| 20,000 | 1,825.9 ms | 4,681.3 ms | 3.0 ms |

Estensioni di SQLite: si': enable_load_extension disponibile (SQLite 3.40.1); sqlite-vec da provare a parte
