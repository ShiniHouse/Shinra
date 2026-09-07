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

- [x] Copertura ≥ 60% su `core/` e `server/` — **80%**, con la soglia
      in CI al 70%: sotto il valore reale perche' non fallisca per un test
      spostato, sopra il 60% chiesto perche' significhi qualcosa
- [x] Test degli endpoint con `TestClient`, incluse tutte le protezioni
- [x] Test del livello di persistenza, inclusa la concorrenza
- [x] Test dello scheduler, inclusa la ripresa dopo riavvio
- [x] Test dell'adattatore Alexa con richieste firmate e non firmate
- [x] Attivare `pre-commit` su tutti i contributi
- [ ] Rendere obbligatoria la CI verde per il merge su `main` — **e' una
      impostazione di GitHub, non del repository**: la deve attivare il
      proprietario. Comando in fondo a CONTRIBUTING.md.
- [x] Rimuovere `continue-on-error` da mypy e tipizzare i moduli, uno alla
      volta — fatto su `config/` e `core/`, dove passano configurazione,
      permessi e dati di casa. Su `server/` e `integrations/` resta
      informativo: dichiararlo obbligatorio senza esserlo sarebbe peggio
      che dirlo.

## Criteri di accettazione

- [x] `pytest --cov` riporta almeno il 60%
- [ ] La protezione del branch `main` e' attiva con CI obbligatoria — da
      attivare a mano su GitHub
- [x] Mypy passa senza `continue-on-error` almeno su `core/` e `config/`
- [x] La suite completa resta sotto il minuto
