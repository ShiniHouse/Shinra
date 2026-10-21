---
title: "feat(apprendimento): il ciclo osserva, proponi, conferma — esteso dal sogno a qualunque cosa non abbia funzionato"
issue: 433
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase D — Imparare proponendo.** ADR 0013, punti 1 e 2. Generalizza il sogno notturno (#258–#263).

## Contesto

Il sogno nota abitudini e ricordi doppi e **propone**. La stessa forma vale per tutto cio' che non ha funzionato: una frase capita male, una routine
che fallisce, un alias mancante. Qui si costruisce il ciclo e il registro, senza ancora nessuna nuova fonte.

## Cosa fare

- [ ] Un tipo di proposta unico (come `proposte_del_sogno`) con: cosa cambia, perche', con quale prova, per quale profilo; stato `nuova`, `accettata`, `scartata`, `annullata`
- [ ] **Elenco chiuso** di cio' che puo' proporre: alias e sinonimi, parole di un dominio, domande dell'intervista, ricordi, routine e regole **spente**. Mai codice, permessi, azioni sensibili
- [ ] Ogni proposta passa dalla prova a secco e dal banco **prima** di comparire; se peggiora una misura non si propone
- [ ] Accettare applica **e** registra come annullare; annullare ripristina lo stato di prima

## Criteri di accettazione

- [ ] Nessuna proposta cambia il comportamento finche' non e' accettata (test)
- [ ] Un tipo non nell'elenco chiuso non si puo' proporre (test)
- [ ] Un'accettazione si annulla e lascia la casa com'era (test)
