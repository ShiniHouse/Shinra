---
title: "refactor(struttura): layout src/shinra e pacchetto installabile"
issue: 16
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

- [x] Spostare il codice sotto `src/shinra/` con i livelli `domain`, `infra`, `services`, `skills`, `channels`, `api`
- [x] Aggiornare gli import; verificare che i test passino a ogni passo intermedio
- [x] `__version__` in `src/shinra/__init__.py`, letto da `pyproject.toml`
- [x] Punto di ingresso `shinra` come comando da console, mantenendo `run.py` come alias
- [x] La regola di divieto import fra livelli fallisce in CI — ma con un test
      (`tests/unit/test_architettura.py`) e non con `flake8-tidy-imports`. La
      regola di ruff sa dire «vietato», non «vietato tranne queste diciannove
      che esistevano prima»: o si accettano tutte come eccezioni permanenti,
      o la CI e' rossa dal primo giorno. Il test invece congela l'elenco:
      una violazione nuova fallisce, e una riparata fallisce anche lei
      finche' non la si toglie. Il debito e' scritto e puo' solo accorciarsi.
- [x] Aggiornare `ARCHITECTURE.md` con la struttura effettiva

## Criteri di accettazione

- [x] `pip install -e .` seguito da `shinra` avvia il servizio
- [x] `domain/` non importa nulla da `infra/`, `api/` o `channels/`
- [x] La regola di dipendenza e' verificata automaticamente in CI
- [x] Nessuna regressione funzionale: tutti i test passano

## Cosa resta

Le diciannove violazioni delle regole di dipendenza, elencate in
`tests/unit/test_architettura.py`. Ripararle dentro allo spostamento avrebbe
prodotto una modifica illeggibile: sono un lavoro suo, da fare un gruppo
alla volta. Il primo e' `api -> infra` (dodici voci su diciannove).
