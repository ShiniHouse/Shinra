---
title: "test(agenti): un banco dei piani e dei compiti lunghi, per sapere dove il multi-agente aiuta"
issue: 430
milestone: "v0.9.0"
labels: ["tipo: funzione", "area: core"]
---

> **Fase A — La misura.** Va fatta per prima: dice se il resto ha senso. ADR 0013, `docs/proposte/agenti-0.9.0/`.

## Contesto

Un modello da 3 miliardi di parametri sceglie lo strumento giusto nel ~73% dei casi a contesto pieno (ADR 0008), ma nessuno ha misurato
quanto bene **pianifica a piu' passi**. Piu' agenti non vuol dire piu' intelligenza: con lo stesso modello un orchestratore che ne chiama tre costa
tre volte il tempo e puo' sbagliare tre volte. Prima di costruire, si misura.

## Cosa fare

- [ ] Un gruppo di richieste a piu' passaggi («prepara la casa per la sera», «se piove chiudi le tapparelle e avvisami») con l'esito atteso, nel formato del banco esistente (`banco/`)
- [ ] Si misura con il modello locale (e con uno esterno, se acceso): piani validi, passi giusti, tempo, richieste riuscite fino in fondo
- [ ] Si confronta un agente solo contro orchestratore + agenti di dominio, e si scrive dove l'uno batte l'altro
- [ ] I risultati stanno in `banco/` con l'analisi, come per la memoria

## Criteri di accettazione

- [ ] La scheda dice, con numeri, dove il multi-agente aiuta e dove no; dove non aiuta, le schede successive non lo usano
- [ ] Il banco gira senza rete (modello locale) e un test ne prova la forma
