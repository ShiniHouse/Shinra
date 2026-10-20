# 0012 — La ricerca per vettori regge la casa? Si misura prima di cambiare

- **Stato:** Accettato
- **Data:** 2026-10-14
- **Attuazione:** milestone `v0.8.0`, issue #248

> Le misure del server di casa (i5-8500T) ci sono dal 2026-10-20 e confermano la proposta: il portatile era un buon
> indicatore (il server è circa un quarto più lento). **Accettato** il 2026-10-20 dal proprietario.

## Contesto

I vettori dei ricordi stanno come JSON nella tabella `embedding_fatti`, e il coseno è calcolato in Python puro per ogni ricordo.
Con qualche centinaio di ricordi è invisibile; con migliaia non era detto. L'idea di `sqlite-vec` è ragionevole ma ha un costo:
è un'**estensione caricabile**, e `enable_load_extension` non è disponibile in ogni build di Python (Windows, immagine Docker,
aarch64 da verificare). Prima si misura, poi si sceglie.

## Misure

Portatile i7-1355U, Windows, Python 3.12.8, vettori da 768 numeri (come `nomic-embed-text`), mediana di 5 richieste
(`banco/memoria/risultati/2026-10-14-ricerca-vettoriale.md`). I vettori sono casuali: il tempo del coseno non dipende dal significato.

| Ricordi | Coseno, Python puro (oggi) | Lettura JSON dei vettori (oggi, a ogni richiesta) | Totale |
| ---: | ---: | ---: | ---: |
| 100 | 6 ms | 26 ms | 32 ms |
| 1.000 | 73 ms | 233 ms | ~305 ms |
| 5.000 | 377 ms | 1.331 ms | ~1,7 s |
| 20.000 | 1.478 ms | 5.621 ms | ~7,1 s |

**Server di casa** (i5-8500T, 16 GB, Python 3.11.2, Linux, stessa misura:
`banco/memoria/risultati/2026-10-20-server-ricerca-vettoriale.md`):

| Ricordi | Coseno, Python puro | Lettura JSON dei vettori (a ogni richiesta, senza cache) | numpy |
| ---: | ---: | ---: | ---: |
| 100 | 9 ms | 23 ms | 0,1 ms |
| 1.000 | 91 ms | 232 ms | 0,1 ms |
| 5.000 | 450 ms | 1.153 ms | 0,6 ms |
| 20.000 | 1.826 ms | 4.681 ms | 3,0 ms |

`numpy` c'è nel server (misurato: mille volte più veloce del Python puro) e **non** è una dipendenza di Shinra oggi. `sqlite-vec`:
non provato. Estensioni di SQLite: sul portatile e sul server (SQLite 3.40.1) `enable_load_extension` è disponibile; nell'immagine
Docker e su aarch64 non è verificato.

## Cosa dicono i numeri (e cosa no)

- **Il coseno non è il collo di bottiglia.** Costa meno della **lettura JSON dei vettori**, che oggi si rifà a ogni richiesta
  (`ServizioConoscenza._con_vettori` rilegge tutta la tabella). Cambiare il modo di calcolare il coseno (numpy, estensione) risparmia
  meno di un quarto del tempo totale.
- **Per una casa vera i numeri sono piccoli.** Il recupero scatta sopra 25 ricordi; con 1.000 sono ~0,3 s su questo portatile, contro i
  ~29 s di una risposta del modello (ADR 0008). Il server è più lento del portatile: va misurato, non stimato.
- **Non misurato:** il server, il costo di `numpy`/`sqlite-vec`, la qualità del recupero (la misura il banco della memoria, #269).

## Decisione (confermata dalle misure del server)

1. **Non aggiungere dipendenze né estensioni adesso.** Sotto una soglia dichiarata (proposta: **5.000 ricordi**, ~2 s su questo
   portatile) non si cambia il motore di ricerca.
2. **Tenere i vettori in memoria**, invalidati dall'impronta del testo e dalla scrittura dell'indice, invece di rileggerli e rifare il
   JSON a ogni richiesta. È la modifica che toglie la parte più grande del costo e non cambia nessun risultato. **Fatta**
   (`infra/db/vettori_in_cache.py`): con la cache, sul server una richiesta costa il solo coseno, **~90 ms a 1.000 ricordi e
   ~450 ms a 5.000**. Per una casa vera, con il modello che impiega secondi a rispondere, è invisibile.
3. Se un giorno la casa supera la soglia (5.000 ricordi, ~0,45 s sul server), riaprire questo ADR e provare `numpy` (dipendenza grande ma
   comune) prima di `sqlite-vec` (estensione che può non caricarsi); con un ripiego automatico al Python puro e la CI su entrambi i
   percorsi.

## Alternative

- *`sqlite-vec` subito*: ricerca nel database, ma estensione caricabile non garantita sulle tre piattaforme.
- *`numpy` subito*: dipendenza nuova per un guadagno che oggi non serve.
- *Non fare niente*: il costo di rileggere il JSON cresce linearmente e non c'è motivo di pagarlo a ogni richiesta.

## Conseguenze

- La cache dei vettori è in `main`, con un test che la invalida quando un ricordo cambia.
- Nessuna dipendenza né estensione nuova. `numpy` resta la prima cosa da provare, e non prima di 5.000 ricordi: sul server il
  costo fino a lì è sotto il mezzo secondo.
