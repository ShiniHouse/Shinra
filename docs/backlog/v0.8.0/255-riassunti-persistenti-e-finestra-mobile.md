---
title: "feat(memoria): la storia vecchia diventa un riassunto che sopravvive al riavvio"
issue: 255
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase C — La storia compressa.** Dipende da: ADR conversazione, budget del contesto.

## Contesto

Oggi i turni oltre i dieci scambi **spariscono**. Una finestra mobile li sostituisce con un riassunto
breve davanti ai turni recenti, e lo conserva.

> **Misurato il 2026-10-13 (qwen2.5:3b):** una sola risposta sbagliata nella storia fa imitare il modello invece di
> chiamare lo strumento (0 su 3, contro 3 su 3 a storia pulita). Un riassunto che ricopia una risposta inventata la rende
> permanente: il riassunto va scritto dal codice dai fatti verificati (strumenti chiamati, esiti), non dalle frasi del modello.

## Cosa fare

- [ ] Tabella `riassunti_conversazione` (profilo, periodo, testo, turni coperti, modello usato, creato)
- [ ] `memory.py` compone: riassunti recenti, poi gli ultimi turni grezzi, dentro il budget del contesto
- [ ] Il riassunto si ricarica al riavvio; scadenza e dimenticanza come da ADR
- [ ] Il ritorno degli strumenti resta compatto (`[azione eseguita: ...]`, com'e' oggi)

## Criteri di accettazione

- [ ] Dopo un riavvio la conversazione riprende col suo riassunto
- [ ] Un profilo non vede mai il riassunto di un altro
