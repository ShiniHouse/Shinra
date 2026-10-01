---
title: "feat(memoria): Ollama riassume la storia vecchia, fuori dal percorso della richiesta"
issue: 256
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase C — La storia compressa.** Dipende da: Riassunti persistenti, banco di valutazione.

## Contesto

Su una CPU senza scheda grafica un riassunto costa secondi: non puo' stare nel percorso della risposta.
Si fa in un compito a parte, dopo che la risposta e' partita; se Ollama non c'e', resta il troncamento di
oggi — la casa risponde come prima, non peggio.

## Cosa fare

- [ ] Dopo K turni usciti dalla finestra, o a inattivita', un compito riassume in «intuizioni di alto livello»: fatti detti, preferenze, richieste in sospeso
- [ ] Il prompt del riassunto vieta di inventare e di conservare segreti; la lingua e' quella del profilo
- [ ] `num_ctx` e modello dedicati (vedi la scheda del budget)
- [ ] Se il modello e' spento o lento, si salta e si riprova: mai un errore all'utente

## Criteri di accettazione

- [ ] Sul banco di valutazione, il riassunto conserva i fatti chiave di N conversazioni di prova e segnala quando ne perde
- [ ] La latenza della risposta e' invariata (misurata prima e dopo)
