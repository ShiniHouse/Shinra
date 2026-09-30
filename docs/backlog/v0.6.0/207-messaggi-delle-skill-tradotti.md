---
title: "feat(i18n): i messaggi degli strumenti e dell'intervista nella lingua di chi parla"
issue: 207
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Residuo della #36. Gli strumenti che il modello chiama (`skills/`) e il motore
dell'intervista restituiscono frasi italiane scritte nel codice: «Non trovo un
sensore...», «Fatto: serratura bloccata», le domande e i riepiloghi
dell'apprendimento. Il modello le rilegge e di solito le traduce da solo, ma
quando una frase va alla persona cosi' com'e' (il messaggio di un tool
mostrato dalla dashboard, l'intervista, un rifiuto) resta italiana.

## Cosa fare

- [ ] Inventario: elencare i messaggi che arrivano alla persona senza passare dal modello (un test che cerca le stringhe italiane nei valori restituiti dagli strumenti)
- [ ] Portarli nei file delle lingue, sotto `messaggi`, con le chiavi dichiarate nel caricatore
- [ ] L'intervista: i testi dei passi, delle domande e dei riepiloghi (`interview_engine.py`) leggono la lingua del profilo
- [ ] I tool leggono la lingua di chi ha chiesto (`contesto.profilo_corrente()`) senza che il dominio la importi

## Criteri di accettazione

- [ ] Due profili, `it` e `en`, che comandano la stessa serratura ricevono il messaggio di esito ciascuno nella propria lingua
- [ ] L'intervista si svolge per intero in inglese per un profilo inglese
- [ ] L'inventario non trova piu' frasi italiane nei valori restituiti dagli strumenti
