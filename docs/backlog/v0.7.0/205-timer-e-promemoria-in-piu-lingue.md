---
title: "feat(i18n): timer e promemoria capiscono piu' di una lingua"
issue: 205
milestone: "v0.7.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

Residuo della #36. Le frasi che Shinra capisce sono in un file per lingua, e
quelle che dice pure, tranne un pezzo: il parser che legge «timer di dieci
minuti» e «ricordami domani mattina di...». Vive in `domain/quando.py` e in
`services/timer_engine.py`, e ha le parole italiane dentro: i numeri, le unita',
i giorni della settimana, «domani», «stasera», «fra due giorni».

In inglese la richiesta arriva al modello, che usa il tool dei promemoria:
funziona, ma e' il percorso lento e meno affidabile per la cosa che si dice
piu' spesso in cucina.

## Cosa fare

- [ ] Portare nei file delle lingue (`intenti/lingue/*.yaml`) i numeri in lettere, le unita' di tempo, i nomi dei giorni, le parole relative («domani», «dopodomani», «stasera», «fra N giorni») e i verbi che introducono un promemoria
- [ ] `domain/quando.py` e `timer_engine.parse_timer_or_reminder` leggono la lingua di chi parla (`richiesta.schemi`), senza importare il caricatore dal dominio: la lingua arriva come argomento
- [ ] L'inglese: «set a timer for ten minutes for the pasta», «remind me tomorrow morning to call the dentist»
- [ ] Le chiavi nuove nell'elenco del caricatore, cosi' una lingua incompleta si dice per nome

## Criteri di accettazione

- [ ] Le stesse due frasi, in italiano e in inglese, producono lo stesso timer e lo stesso promemoria (stesso istante, stessa etichetta)
- [ ] Una lingua inventata da un test capisce le sue parole e **non** quelle italiane, come gia' per gli altri schemi
- [ ] Nessuna parola italiana di tempo resta in `domain/quando.py`
