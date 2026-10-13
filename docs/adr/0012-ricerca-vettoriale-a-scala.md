# 0012 — La ricerca per vettori regge la casa? Si misura prima di cambiare

- **Stato:** Proposto
- **Data:** 2026-10-14
- **Attuazione:** milestone `v0.8.0`, issue #248

> Bozza con **misure vere ma di una sola macchina** (il portatile). Le stesse misure sul server di casa (i5-8500T) mancano e
> vanno aggiunte prima di accettarla: `python scripts/banco_vettori.py --macchina "i5-8500T" --salva`.

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

`numpy`: non installato qui, non misurato. `sqlite-vec`: non provato. Estensioni di SQLite: su questo Python (SQLite 3.45.3) `enable_load_extension`
è disponibile; sul server, nell'immagine Docker e su aarch64 non è verificato.

## Cosa dicono i numeri (e cosa no)

- **Il coseno non è il collo di bottiglia.** Costa meno della **lettura JSON dei vettori**, che oggi si rifà a ogni richiesta
  (`ServizioConoscenza._con_vettori` rilegge tutta la tabella). Cambiare il modo di calcolare il coseno (numpy, estensione) risparmia
  meno di un quarto del tempo totale.
- **Per una casa vera i numeri sono piccoli.** Il recupero scatta sopra 25 ricordi; con 1.000 sono ~0,3 s su questo portatile, contro i
  ~29 s di una risposta del modello (ADR 0008). Il server è più lento del portatile: va misurato, non stimato.
- **Non misurato:** il server, il costo di `numpy`/`sqlite-vec`, la qualità del recupero (la misura il banco della memoria, #269).

## Proposta (da confermare con le misure del server)

1. **Non aggiungere dipendenze né estensioni adesso.** Sotto una soglia dichiarata (proposta: **5.000 ricordi**, ~2 s su questo
   portatile) non si cambia il motore di ricerca.
2. **Tenere i vettori in memoria**, invalidati dall'impronta del testo e dalla scrittura dell'indice, invece di rileggerli e rifare il
   JSON a ogni richiesta. È la modifica che toglie la parte più grande del costo e non cambia nessun risultato.
3. Se un giorno la casa supera la soglia, riaprire questo ADR con le misure del server e provare `numpy` (dipendenza grande ma
   comune) prima di `sqlite-vec` (estensione che può non caricarsi); con un ripiego automatico al Python puro e la CI su entrambi i
   percorsi.

## Alternative

- *`sqlite-vec` subito*: ricerca nel database, ma estensione caricabile non garantita sulle tre piattaforme.
- *`numpy` subito*: dipendenza nuova per un guadagno che oggi non serve.
- *Non fare niente*: il costo di rileggere il JSON cresce linearmente e non c'è motivo di pagarlo a ogni richiesta.

## Conseguenze

- Una scheda piccola per la cache dei vettori, con un test che la invalida quando un ricordo cambia.
- L'ADR si accetta dopo le misure del server.
