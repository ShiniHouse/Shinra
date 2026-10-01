---
title: "test(memoria): un banco che misura se ricordare meglio e' vero"
issue: 269
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: core"]
---

> **Fase Trasversale.**

## Contesto

Come per la scelta degli strumenti (#183): senza una misura, «ranking migliore» e «riassunto fedele» sono
opinioni. Lo stesso metodo del banco di prova: un corpus, un comando, numeri salvati.

## Cosa fare

- [ ] Corpus di (ricordi, domande, ricordi pertinenti attesi) incluse domande ambigue e senza risposta
- [ ] Conversazioni di prova con i fatti chiave da preservare dopo la compressione
- [ ] Un comando che misura recall@k, MRR e conservazione dei fatti, con il modello configurabile; risultati in una cartella del repository
- [ ] Prova senza Ollama con un finto modello perfetto, come il banco della #183

## Criteri di accettazione

- [ ] Il banco gira in CI senza rete
- [ ] Le schede di ranking e di compressione citano i suoi numeri
