---
title: "refactor(struttura): layout src/shinra e pacchetto installabile"
milestone: "v0.2.0"
labels: ["tipo: attivita'", "area: infra"]
riferimento: "docs/ARCHITECTURE.md §3"
---

## Contesto

Il codice vive in cartelle di primo livello (`core/`, `server/`, `config/`,
`integrations/`). `config` in particolare e' un nome molto comune: un `import
config` puo' risolvere sulla directory di lavoro invece che sul progetto, con
errori difficili da diagnosticare.

Soprattutto, la struttura attuale non ha confini dichiarati fra livelli:
`server/routes_admin.py` importa direttamente `core.tools.ha_tools`, e nulla
impedisce che un tool importi un router. Man mano che i moduli aumentano —
serrature, media, energia, presenza — l'assenza di confini diventa il freno
principale.

La struttura target e le regole di dipendenza sono in
[docs/ARCHITECTURE.md](../../ARCHITECTURE.md).

## Cosa fare

- [ ] Spostare il codice sotto `src/shinra/` con i livelli `domain`, `infra`, `services`, `skills`, `channels`, `api`
- [ ] Aggiornare gli import; verificare che i test passino a ogni passo intermedio
- [ ] `__version__` in `src/shinra/__init__.py`, letto da `pyproject.toml`
- [ ] Punto di ingresso `shinra` come comando da console, mantenendo `run.py` come alias
- [ ] Aggiungere a ruff la regola di divieto import fra livelli (`flake8-tidy-imports`), cosi' che una violazione fallisca in CI
- [ ] Aggiornare `ARCHITECTURE.md` con la struttura effettiva

## Criteri di accettazione

- [ ] `pip install -e .` seguito da `shinra` avvia il servizio
- [ ] `domain/` non importa nulla da `infra/`, `api/` o `channels/`
- [ ] La regola di dipendenza e' verificata automaticamente in CI
- [ ] Nessuna regressione funzionale: tutti i test passano
