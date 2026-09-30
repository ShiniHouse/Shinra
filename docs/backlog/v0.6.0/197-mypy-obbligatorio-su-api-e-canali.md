---
title: "ci(tipi): mypy obbligatorio anche su api e channels"
issue: 197
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: infra"]
---

## Contesto

Nella CI mypy e' obbligatorio su `config`, `domain`, `infra`, `services` e
`skills`, e solo informativo su `api` e `channels`: proprio i livelli che
ricevono l'input esterno. Il passaggio a obbligatorio dipende da quanti
errori ci sono oggi, che va misurato prima.

## Cosa fare

- [ ] Contare gli errori di mypy su `api` e `channels`
- [ ] Correggerli, o annotarli uno per uno con il motivo, come si fa per le eccezioni di architettura
- [ ] Togliere `continue-on-error` dal passo della CI

## Criteri di accettazione

- [ ] Il passo della CI per `api` e `channels` e' obbligatorio e verde
- [ ] Gli errori rimasti sono soppressi uno per uno, con la ragione accanto
