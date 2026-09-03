---
title: "test: portare la copertura al 60% e attivare i controlli automatici"
milestone: "v0.2.0"
labels: ["tipo: attivita'", "area: infra"]
---

## Contesto

La v0.1.0 introduce i test di regressione sui difetti noti. Questa issue estende
la copertura al codice esistente e rende i controlli obbligatori, perche' la
fase v0.2.0 riscrive persistenza, memoria e struttura: senza rete di sicurezza
e' una riscrittura al buio.

## Cosa fare

- [ ] Copertura ≥ 60% su `core/` e `server/`
- [ ] Test degli endpoint con `TestClient`, incluse tutte le protezioni
- [ ] Test del livello di persistenza, inclusa la concorrenza
- [ ] Test dello scheduler, inclusa la ripresa dopo riavvio
- [ ] Test dell'adattatore Alexa con richieste firmate e non firmate
- [ ] Attivare `pre-commit` su tutti i contributi
- [ ] Rendere obbligatoria la CI verde per il merge su `main` (protezione del branch)
- [ ] Rimuovere `continue-on-error` da mypy e tipizzare i moduli, uno alla volta

## Criteri di accettazione

- [ ] `pytest --cov` riporta almeno il 60%
- [ ] La protezione del branch `main` e' attiva con CI obbligatoria
- [ ] Mypy passa senza `continue-on-error` almeno su `core/` e `config/`
- [ ] La suite completa resta sotto il minuto
