---
title: "feat(distribuzione): l'add-on per Home Assistant OS e la prova su Raspberry Pi 4"
issue: 212
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: infra", "stato: da valutare"]
---

## Contesto

Residuo della #37. La strada Docker e' fatta e provata in CI (immagine a due
stadi, compose, GHCR per amd64 e arm64). Restano due cose che non si possono
provare senza l'hardware giusto, ed e' per questo che la scheda e' «da valutare»:

- **l'add-on** per Home Assistant OS. Chi sviluppa qui usa Home Assistant
  Container, non HA OS: un add-on non provato in casa sarebbe una funzione
  spedita e mai eseguita, il difetto da cui il progetto si e' gia' dovuto
  difendere tre volte. In piu' l'*ingress* riscrive il percorso di base, e oggi
  la dashboard ha un percorso assoluto in novantadue punti;
- **l'immagine arm64** su un Raspberry Pi 4: in CI si costruisce, non si esegue
  su quell'hardware.

## Cosa fare

- [ ] Togliere l'ostacolo dell'ingress: il percorso di base della dashboard diventa relativo (le richieste, i moduli, il service worker)
- [ ] `config.yaml` dell'add-on, con ingress e scoperta automatica dell'istanza Home Assistant
- [ ] Provarlo su una installazione HA OS vera (anche virtuale)
- [ ] Avviare l'immagine arm64 su un Raspberry Pi 4 e fare il giro di accesso e chat

## Criteri di accettazione

- [ ] L'add-on si installa su Home Assistant OS e rileva l'istanza senza configurazione manuale
- [ ] L'immagine arm64 funziona su Raspberry Pi 4, con lo stesso controllo che fa la CI per amd64
- [ ] La dashboard funziona identica dietro ingress e senza
