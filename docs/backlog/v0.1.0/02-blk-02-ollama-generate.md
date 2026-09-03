---
title: "fix(ollama): l'estrazione dei fatti chiama un metodo inesistente"
milestone: "v0.1.0"
labels: ["tipo: difetto", "area: core", "gravita': critica"]
riferimento: BLK-02
---

## Contesto

`core/interview_engine.py:181` chiama `self.ollama.generate(prompt=..., system=..., temperature=...)`.
`OllamaClient` espone solo `chat()`, `check_health()`, `get_models_detailed()` e
`get_available_models()`.

Qui l'eccezione e' catturata dal `try`, quindi il codice cade **sempre** nel ramo
di fallback e salva la frase grezza dell'utente come fatto. Il prompt di
estrazione JSON — con la proposta automatica di routine — non e' mai stato
eseguito: e' codice morto.

Conseguenza: anche risolvendo BLK-01, l'intervista produrrebbe una knowledge base
di trascrizioni invece che di fatti atomici, e non proporrebbe mai una routine.

## Cosa fare

- [ ] Riscrivere `_extract_knowledge_and_routines` su `OllamaClient.chat()`, che gia' esiste
- [ ] Passare `format: "json"` a Ollama per ottenere JSON valido senza post-elaborazione
- [ ] Validare la risposta con un modello Pydantic invece che con `json.loads` nudo
- [ ] Registrare a livello `warning` quando si ricade sul fallback, invece di farlo in silenzio
- [ ] Verificare che il fallback resti valido quando Ollama e' spento

## Criteri di accettazione

- [ ] Con Ollama attivo, una risposta come «mi sveglio alle 7 e accendo la luce in cucina» produce piu' di un fatto atomico
- [ ] Un JSON malformato dal modello non fa fallire l'intervista
- [ ] Con Ollama spento, l'intervista prosegue usando il fallback e lo scrive nel log
- [ ] Esiste un test che simula la risposta del modello, senza rete
