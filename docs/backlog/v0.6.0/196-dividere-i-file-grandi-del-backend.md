---
title: "refactor(backend): nessun file del backend sopra le cinquecento righe, e un test a dirlo"
issue: 196
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: core"]
---

## Contesto

Nel frontend il tetto delle cinquecento righe e' gia' applicato da un test.
Nel backend tre file lo superano: `skills/registry.py` (circa 850 righe),
`api/routes_admin.py` (circa 850) e `api/app.py` (circa 700). Sono anche i
posti dove gli agenti della `0.6.0` toccheranno di piu': meglio sistemarli
prima, non dopo.

## Cosa fare

- [ ] Dividere `skills/registry.py` per dominio, in modo che il registro degli agenti possa riusare la stessa scomposizione
- [ ] Dividere `api/routes_admin.py` per area
- [ ] Portare `api/app.py` sotto il tetto
- [ ] Un test che fallisce se un file di `src/shinra/` supera il tetto, con eventuali eccezioni elencate una per una come in `test_architettura.py`

## Criteri di accettazione

- [ ] Nessun comportamento cambia: la suite passa senza modifiche ai test funzionali
- [ ] Il test del tetto esiste e le eccezioni, se ce ne sono, hanno un motivo scritto
- [ ] `test_architettura.py` non guadagna nuove eccezioni
