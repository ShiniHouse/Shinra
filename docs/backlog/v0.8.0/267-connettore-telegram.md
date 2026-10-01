---
title: "feat(canali): il primo connettore esterno, spento di default"
issue: 267
milestone: "v0.8.0"
labels: ["tipo: funzione", "area: integrazioni"]
---

> **Fase E — I canali esterni.** Dipende da: Astrazione del canale.

## Contesto

Solo se l'ADR dice di si'. Long polling: nessuna porta da aprire e nessun indirizzo pubblico da difendere.

## Cosa fare

- [ ] Bot configurato in `.env` (token mai in `config.yaml`); spento finche' non lo si abilita
- [ ] Solo chat abbinate; limite di frequenza; messaggi lunghi spezzati
- [ ] Le azioni sensibili chiedono conferma sullo stesso canale (#192), e da una chat non abbinata non partono
- [ ] Modalita' riservata: «hai un avviso, aprilo in dashboard» senza dettagli

## Criteri di accettazione

- [ ] Con il connettore spento, nessun client HTTP verso l'esterno viene creato (guardia)
- [ ] Una conferma di una chat non vale per un'altra
