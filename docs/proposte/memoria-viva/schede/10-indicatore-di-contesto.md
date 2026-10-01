---
title: "feat(chat): sotto la risposta, i ricordi che Shinra ha usato"
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: frontend"]
---

> **Fase B — Trasparenza.** Dipende da: Rinforzo, vista dei ricordi.

## Contesto

«Perche' hai risposto cosi'?» comincia da «cosa sapevi». Gli eventi dell'agente (#188) gia' dicono quali
nodi `fatto:<id>` hanno contribuito, ma solo quando il recupero seleziona: sotto i 25 fatti si mandano tutti
e non c'e' niente da raccontare. L'indicatore deve dire **sempre cosa e' entrato nel prompt**.

## Cosa fare

- [ ] La risposta di `/api/chat` porta `ricordi_usati` (identificativo, categoria, estratto) **solo al profilo che ha chiesto** e solo per i ricordi che puo' leggere
- [ ] Sotto la risposta: «Ho usato 3 ricordi», espandibile, con il collegamento alla vista dei ricordi
- [ ] Il grafo del Cervello continua a ricevere solo identificativi, mai testo (regola della #188)

## Criteri di accettazione

- [ ] Prova dei gesti: la risposta mostra i ricordi usati e il collegamento funziona
- [ ] Un altro profilo connesso non riceve gli estratti (come per gli eventi dell'agente)
