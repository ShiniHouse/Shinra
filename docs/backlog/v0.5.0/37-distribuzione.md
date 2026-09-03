---
title: "feat(distribuzione): immagine Docker e add-on per Home Assistant OS"
milestone: "v0.5.0"
labels: ["tipo: funzione", "area: infra"]
---

## Contesto

L'unica installazione documentata e' manuale su Debian: clonazione, ambiente
virtuale, systemd, nginx, certificati. E' una barriera notevole, e la maggior
parte delle persone che userebbero Shinra ha gia' Home Assistant OS, dove un
add-on si installa con un clic.

## Cosa fare

- [ ] `Dockerfile` multi-stage e immagine pubblicata su GitHub Container Registry
- [ ] `docker-compose.yml` con Shinra, Ollama e i volumi persistenti
- [ ] Add-on per Home Assistant OS con `config.yaml`, ingress e scoperta automatica dell'istanza HA
- [ ] Immagini multi-architettura, incluso arm64 per Raspberry Pi
- [ ] Pubblicazione automatica al tag di release

## Criteri di accettazione

- [ ] `docker compose up` produce un'installazione funzionante
- [ ] L'add-on si installa su Home Assistant OS e rileva l'istanza senza configurazione manuale
- [ ] L'immagine arm64 funziona su Raspberry Pi 4
