---
title: "docs: la guida al Cervello, agli agenti e ai piani"
issue: 198
milestone: "v0.6.0"
labels: ["tipo: attivita'", "area: documentazione"]
---

## Contesto

Una funzione che non si capisce non esiste. La `0.6.0` porta tre cose nuove
per l'utente: il grafo, gli agenti che dividono il lavoro e le conferme sulle
azioni sensibili. Vanno dette per chi installa Shinra senza essere chi l'ha
scritta, nello stesso stile di `PRIMI-PASSI.md` e `PROBLEMI.md`.

## Cosa fare

- [x] Una guida «Il Cervello»: cosa si vede, cosa significano i nodi e i colori, come si apre un oggetto
- [x] Una guida agli agenti: cosa sa fare ciascuno, cosa succede quando il router sbaglia
- [x] Una guida alle conferme: quali azioni le chiedono, da quali canali, cosa succede se scadono
- [x] Nuove voci in `PROBLEMI.md`, scritte solo per guasti davvero incontrati
- [x] Aggiornare la tabella «cosa resta in casa» del README e le note di rilascio

## Criteri di accettazione

- [ ] Una persona che non conosce il progetto segue le guide e arriva a vedere il grafo e a confermare un'azione
- [x] Nessuna voce di `PROBLEMI.md` descrive un guasto mai capitato
- [x] `docs/release/v0.6.0.md` esiste dal modello `TEMPLATE.md`

## Com'e' andata

Tre guide (`docs/CERVELLO.md`, `docs/AGENTI.md`, `docs/CONFERME.md`), due guasti veri in `PROBLEMI.md` (il prompt
tagliato e Ollama ucciso per memoria) e due voci fra «cose che sembrano guasti», le note di rilascio in
`docs/release/v0.6.0.md` (marcate *in preparazione* finche' non c'e' il tag), il `CHANGELOG` e il README.

**Resta aperto il primo criterio**: che una persona che non conosce il progetto segua le guide e arrivi a vedere il
grafo e a confermare un'azione. Lo puo' dire solo chi le legge senza averle scritte (come la #208 per l'installazione).
**La guida ai piani** non c'e': i piani sono passati alla `0.7.0` (#191).
