---
title: "feat(llm): ogni parte del prompt ha un budget, e tagliare non e' piu' silenzioso"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase A — Le fondamenta.** Dipende da: #183 (le misure sul modello vero).

## Contesto

Il banco di prova della #183 ha mostrato che il prompt di sistema piu' gli schemi degli strumenti
pesano circa **5000 token**, e il client usa `num_ctx` 1024 (2048 se la risposta e' lunga): Ollama
taglia il contesto **in silenzio**. Aggiungere ricordi e riassunti a quel prompt prima di averlo
risolto peggiora le risposte invece di migliorarle. Questa scheda e' la precondizione di tutte le altre.

## Cosa fare

- [ ] Contare i token per componente a ogni richiesta: sistema, schemi, ricordi, storia, domanda
- [ ] Derivare il budget da `num_ctx` del modello in uso, e renderlo configurabile per scopo (chat, sogno, riassunto)
- [ ] Dichiarare l'ordine in cui si taglia quando non ci sta (storia grezza, poi ricordi meno pertinenti, mai la domanda), e **dirlo** nel log e in un evento
- [ ] Misurare sul i5-8500T con i modelli del banco della #183

## Criteri di accettazione

- [ ] Il banco della #183 riporta «Troncati = 0» sul modello scelto, con il `num_ctx` di produzione
- [ ] Un test mostra che un prompt oltre il budget viene ridotto nell'ordine dichiarato, e che nessun taglio avviene senza traccia
