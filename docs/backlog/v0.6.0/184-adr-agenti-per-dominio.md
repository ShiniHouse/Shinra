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

- [x] Scrivere l'ADR 0008: contesto, decisione, alternative scartate (un solo agente con tutti gli strumenti; un agente per strumento; planner esterno), conseguenze
- [x] Dire cosa succede quando il router sbaglia dominio
- [x] Dire come un agente dichiara i propri strumenti e perche' non puo' vedere quelli degli altri
- [x] Legare la decisione ai numeri del banco di prova, non a una impressione

## Criteri di accettazione

- [x] L'ADR e' in `docs/adr/` e indicizzato in `docs/adr/README.md`
- [x] Cita i risultati del banco di prova
- [x] Dice cosa cambierebbe nella decisione se il banco desse un altro risultato

## Com'e' andata

L'ADR [0008](../../adr/0008-agenti-per-dominio.md) e' scritto, indicizzato e **Proposto**: diventa
Accettato quando il banco, rifatto con gli agenti di dominio, supera le soglie scritte dentro.
Cita i due giri sull'i5-8500T (strumento giusto 72,8% a contesto 8192, 131 s a richiesta, prompt
tagliato a 514 token in produzione) e dice cosa cambierebbe se il banco desse un altro risultato.
Il router e gli agenti sono la #190; la misura sul banco e' nell'analisi del giro con gli agenti.
