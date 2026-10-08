---
title: "docs: collaudo della documentazione da parte di chi non l'ha scritta"
issue: 208
milestone: "v0.7.0"
labels: ["tipo: attivita'", "area: documentazione"]
---

## Contesto

Residuo della #38. Le guide d'installazione, di sviluppo e il riferimento delle
API sono scritti e difesi da test (#204), ma un test non sa se una pagina si
capisce. Il collaudo della #180 l'ha fatto una volta, sul README di allora;
le pagine di adesso non le ha seguite nessuno che non le abbia scritte.

E' un criterio che nessun documento puo' chiudere da solo: serve una persona e
una macchina pulita.

> **Ridotta (2026-10-08).** Alla `0.7.0` si chiude il collaudo delle **guide d'uso** (`PRIMI-PASSI`, `PROBLEMI`,
> `CERVELLO`, `AGENTI`, `CONFERME`, `VERIFICA-IN-CASA`) con un familiare, come per la #198. L'installazione da
> zero su una macchina pulita (Docker e Debian) e la guida allo sviluppo richiedono un secondo PC e un'altra
> persona: sono il criterio 3 della `1.0.0`, non di questa fase.

## Cosa fare

- [ ] *(alla `1.0.0`)* Una persona che non ha scritto le pagine, su una macchina senza Shinra ne' Ollama, segue **solo** `docs/INSTALLAZIONE.md` (Docker) e poi `docs/PRIMI-PASSI.md`, e annota ogni punto in cui serve sapere qualcosa che non c'e'
- [ ] *(alla `1.0.0`)* Lo stesso per l'installazione a mano su Debian
- [ ] *(alla `1.0.0`)* Una seconda persona segue `docs/SVILUPPO.md` per aggiungere uno strumento inventato, senza leggere il codice dell'agente
- [ ] Ogni punto annotato diventa una correzione alle pagine, con la tabella «cosa mancava» come nella #38
- [ ] Il README e le guide nominano solo cose che il collaudo ha visto funzionare

## Criteri di accettazione

- [ ] Una persona che non ha scritto le guide d'uso le segue da sola e annota cosa non capisce *(l'installazione da zero: `1.0.0`)*
- [ ] La tabella dei punti mancanti e' nella scheda, e le pagine sono corrette
