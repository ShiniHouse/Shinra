---
title: "fix(data-store): aggiunge il metodo add_knowledge_item mancante"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: core", "gravita': critica"]
riferimento: BLK-01
---

## Contesto

`core/interview_engine.py:110` chiama `data_store.add_knowledge_item(text=..., category=...)`.
Il metodo **non esiste**: `DataStore` espone solo `get_knowledge()` e `save_knowledge()`.

La chiamata non e' racchiusa in un `try`, quindi l'`AttributeError` risale fino
a FastAPI e diventa un **HTTP 500 a ogni risposta dell'utente**, sia da
`POST /api/learning/answer` sia dalla chat vocale. La Modalita' Apprendimento
non ha mai completato un singolo passo dell'intervista.

## Cosa fare

- [ ] Aggiungere `DataStore.add_knowledge_item(text: str, category: str = "generale", enabled: bool = True) -> dict`
- [ ] Generare un identificativo univoco (non `f"k_{len(items)+1}"`, che collide dopo una cancellazione)
- [ ] Restituire l'elemento salvato, come si aspetta il chiamante
- [ ] Evitare di duplicare un fatto gia' presente con lo stesso testo
- [ ] Rimuovere il marcatore `xfail` da `tests/unit/test_regressioni_bloccanti.py`

## Criteri di accettazione

- [ ] `POST /api/learning/answer` con una risposta valida restituisce `200` e avanza allo step successivo
- [ ] Il fatto estratto compare in `GET /api/knowledge`
- [ ] Un'intervista completa dei sei step si conclude senza errori
- [ ] Due chiamate con lo stesso testo non creano due voci identiche
- [ ] Esiste un test che fallisce senza la correzione
