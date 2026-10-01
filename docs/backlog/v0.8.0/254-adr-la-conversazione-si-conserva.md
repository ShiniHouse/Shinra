---
title: "docs(adr): si conserva la conversazione, e in che forma?"
issue: 254
milestone: "v0.8.0"
labels: ["tipo: attivita'", "area: sicurezza"]
---

> **Fase C — La storia compressa.** Dipende da: ADR privacy della memoria.

## Contesto

`ConversationMemory` vive **solo in RAM**: dieci scambi, mezz'ora, persa al riavvio. Per riassumere i
turni vecchi bisogna conservare qualcosa, e conservare conversazioni e' una decisione di privacy, non di
comodita'. Anche il sogno notturno (fase D) non ha altro materiale conversazionale che questo.

## Cosa fare

- [ ] Decidere cosa si conserva: solo i riassunti (proposta) o anche il testo grezzo, e per quanto tempo
- [ ] Decidere per chi: per profilo; mai per gli ospiti; cosa per i minori
- [ ] Dichiarare che il database non e' cifrato a riposo, e cosa significa
- [ ] Decidere cosa succede con «dimentica» e con la scadenza

## Criteri di accettazione

- [ ] L'ADR e' accettato
- [ ] Le schede C ne citano le scelte
