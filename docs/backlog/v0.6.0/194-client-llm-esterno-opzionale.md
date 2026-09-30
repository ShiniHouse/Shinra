---
title: "feat(llm): un modello esterno opzionale, spento di default"
issue: 194
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: integrazioni", "area: sicurezza", "stato: da valutare"]
---

## Contesto

*Deciso con Alessio:* il progetto resta **locale**, con la possibilita'
di aggiungere collegamenti esterni in seguito. Questa scheda e' quella
possibilita', ed e' in valutazione: si decide dopo aver visto cosa il banco di
prova dice del modello locale.

Il client Ollama e' gia' isolato in `infra/llm/`: un secondo client e' una
sostituzione circoscritta. Quello che pesa non e' il codice, e' la promessa:
la tabella «cosa resta in casa» del README deve restare vera.

## Cosa fare

- [ ] Un'interfaccia comune fra il client locale e quello esterno
- [ ] **Spento di default**; si attiva dalle impostazioni con un consenso esplicito che dice cosa esce
- [ ] Esce il minimo: la richiesta e gli strumenti rilevanti, mai la conoscenza intera ne' i dati personali
- [ ] Le azioni sensibili restano soggette alla conferma della scheda relativa, sempre
- [ ] La chiave sta in `.env`, mai in `config.yaml`, mai nel registro
- [ ] Una riga nuova nella tabella «cosa resta in casa» del README e una in `SECURITY.md`
- [ ] Se il servizio esterno non risponde, Shinra ricade sul modello locale

## Criteri di accettazione

- [ ] Con l'opzione spenta, un test prova che nessuna richiesta esce dalla rete locale
- [ ] Un test prova che la conoscenza non viene inclusa nella richiesta esterna
- [ ] La documentazione dice in chiaro cosa esce, verso chi e quando
