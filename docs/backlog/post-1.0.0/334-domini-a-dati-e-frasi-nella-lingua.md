---
title: "feat(i18n): i domini restituiscono dati e le skill dicono la frase nella lingua (gli strumenti restanti)"
issue: 334
milestone: "Dopo la 1.0.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Residuo della #207, scoperto lavorandoci (2026-10-12). La #207 ha portato nella lingua di chi parla l'intervista, la serratura, il lettore multimediale, l'aspirapolvere e il ventilatore: la lingua del profilo viaggia nel contesto della richiesta (`contesto.lingua_corrente()`) e lo strumento dice `messaggio("chiave", ...)` da `shinra.infra.lingue`.

Ma le frasi italiane negli strumenti **non sono solo quelle che il test d'inventario conta** (`tests/unit/test_inventario_messaggi.py`: 77 in 14 file). Quasi ogni strumento costruisce la risposta con pezzi che arrivano dai moduli `domain/` — `NOMI`, `riassumi`, `riassunto`, gli errori `NonSaFarlo` — e anche **quelli** sono italiani; in piu' il vocabolario con cui il modello nomina le azioni («spegni», «raffredda») e' scritto nel dominio. Tradurre solo le skill darebbe risposte con pezzi in due lingue.

## Cosa fare

- [ ] I domini (clima, tapparelle, energia, liste, calendario, scadenze, sicurezza, simulazione) restituiscono **dati** — codici e valori — e non frasi; le skill li dicono con le frasi del file della lingua
- [ ] Le parole con cui si nominano modalita', azioni e stati stanno nei file delle lingue, non nei domini (come il lessico del tempo, #205)
- [ ] Le frasi restanti degli strumenti (meteo, notizie, Wikipedia, simulazione, ha_tools, registry) nei file delle lingue
- [ ] L'inventario scende a zero e la regola diventa assoluta (`DEBITO` vuoto)

## Criteri di accettazione

- [ ] Un profilo `it` e uno `en` che comandano lo stesso termostato, la stessa tapparella e la stessa lista ricevono la risposta intera nella propria lingua, senza pezzi dell'altra
- [ ] `test_inventario_messaggi.py` non trova nessuna frase italiana nei valori restituiti dagli strumenti, e un test analogo non ne trova nei domini
- [ ] Il comportamento italiano non cambia: i test esistenti passano invariati

> Dopo la `1.0.0`: le lingue sono per un pubblico futuro e non si provano in casa (decisione del 2026-10-12).
