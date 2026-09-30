---
title: "docs(adr): agenti specializzati per dominio invece di un modello con tutti gli strumenti"
issue: 184
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: documentazione"]
---

## Contesto

Un modello locale piccolo sbaglia di piu' quando ha davanti tutti gli
strumenti. La proposta e' dividere: un router sceglie un agente di dominio
(clima, sicurezza, energia, agenda, luci) e ogni agente vede solo i propri
strumenti. Va deciso per iscritto prima di costruirlo, come per gli ADR 0001-0007.

## Cosa fare

- [ ] Scrivere l'ADR 0008: contesto, decisione, alternative scartate (un solo agente con tutti gli strumenti; un agente per strumento; planner esterno), conseguenze
- [ ] Dire cosa succede quando il router sbaglia dominio
- [ ] Dire come un agente dichiara i propri strumenti e perche' non puo' vedere quelli degli altri
- [ ] Legare la decisione ai numeri del banco di prova, non a una impressione

## Criteri di accettazione

- [ ] L'ADR e' in `docs/adr/` e indicizzato in `docs/adr/README.md`
- [ ] Cita i risultati del banco di prova
- [ ] Dice cosa cambierebbe nella decisione se il banco desse un altro risultato
