---
title: "docs(adr): chi vede e chi puo' cambiare cio' che Shinra ricorda"
issue: 243
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: sicurezza"]
---

> **Fase A — Le fondamenta.**

## Contesto

Oggi la tabella `knowledge` e' **della casa**: un fatto non ha un proprietario, e chi ha il
permesso `conoscenza.leggi` li legge tutti. Va bene per «il wifi e' sul router». Non regge
«cosa sa Shinra di *me*»: la memoria personale di un adulto non deve finire nel prompt di un
bambino ne' nella lista di un ospite, e un profilo deve poter chiedere «dimentica tutto di me».
Tutta la fase poggia su questa decisione: va presa prima, per iscritto.

## Cosa fare

- [ ] Decidere gli **ambiti**: casa (condivisa) e profilo (privata). Cosa e' di default l'uno e l'altro
- [ ] Decidere chi legge e chi scrive ogni ambito, e se l'amministratore vede il privato di un altro profilo (proposta: **no**, salvo scelta esplicita del proprietario)
- [ ] Decidere i **minori** (`restricted_topics`, ruoli `teen`/`child`): cosa possono ricordare e cosa si ricorda di loro
- [ ] Decidere gli **ospiti**: nessuna memoria persistente
- [ ] Decidere cosa **non si ricorda mai**: PIN, token, codici dell'allarme, numeri di carte (si riusa `registro.oscura`)
- [ ] Decidere cosa include il backup e cosa succede ai backup vecchi dopo un «dimentica»
- [ ] Scrivere l'ADR e aggiungere la tabella dei permessi nuovi, se servono

## Criteri di accettazione

- [ ] L'ADR e' accettato e nel registro degli ADR
- [ ] Ogni scheda successiva della fase dice a quale ambito si applica
