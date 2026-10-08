---
title: "feat(distribuzione): l'add-on per Home Assistant OS"
issue: 282
milestone: "Dopo la 1.0.0"
labels: ["tipo: funzione", "area: infra"]
---

## Contesto

Residuo della #37. La strada Docker e' fatta e provata in CI (immagine a due
stadi, compose, GHCR per amd64 e arm64). Resta l'**add-on** per Home Assistant
OS, che si installa dal supervisor senza toccare un terminale.

L'add-on va provato su una installazione vera: chi sviluppa qui usa Home
Assistant Container, non HA OS, quindi serve un'istanza HA OS (anche virtuale)
per non spedire una funzione mai eseguita, il difetto da cui il progetto si e'
gia' dovuto difendere tre volte. In piu' l'*ingress* riscrive il percorso di
base, e oggi la dashboard ha un percorso assoluto in novantadue punti.

**Fuori da questa scheda:** la prova dell'immagine arm64 su un Raspberry Pi 4.
In CI l'immagine si costruisce ma non si esegue su quell'hardware; se ne
parlera' in un altro momento (vedi «Dopo la 1.0.0» in `docs/ROADMAP.md`).

## Cosa fare

- [ ] Togliere l'ostacolo dell'ingress: il percorso di base della dashboard diventa relativo (le richieste, i moduli, il service worker)
- [ ] `config.yaml` dell'add-on, con ingress e scoperta automatica dell'istanza Home Assistant
- [ ] Provarlo su una installazione HA OS vera (anche virtuale)

## Criteri di accettazione

- [ ] L'add-on si installa su Home Assistant OS e rileva l'istanza senza configurazione manuale
- [ ] La dashboard funziona identica dietro ingress e senza
