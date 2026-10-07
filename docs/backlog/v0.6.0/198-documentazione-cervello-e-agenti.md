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

- [x] Una persona che non conosce il progetto segue le guide e arriva a vedere il grafo e a confermare un'azione: **letta e capita** da un familiare (vedi sotto); la conferma di un'azione non e' stata eseguita (in casa non c'e' una serratura)
- [x] Nessuna voce di `PROBLEMI.md` descrive un guasto mai capitato
- [x] `docs/release/v0.6.0.md` esiste dal modello `TEMPLATE.md`

## Com'e' andata

Tre guide (`docs/CERVELLO.md`, `docs/AGENTI.md`, `docs/CONFERME.md`), due guasti veri in `PROBLEMI.md` (il prompt
tagliato e Ollama ucciso per memoria) e due voci fra «cose che sembrano guasti», le note di rilascio in
`docs/release/v0.6.0.md` (marcate *in preparazione* finche' non c'e' il tag), il `CHANGELOG` e il README.

**Il primo criterio e' stato chiuso il 2026-10-07**: un familiare che non ha scritto le guide ha letto `CERVELLO.md`,
`AGENTI.md` e `CONFERME.md` e, riferisce chi vive qui, **ha capito tutto**. E' un giudizio a voce, senza un elenco di frasi
da riscrivere: non ha segnalato punti poco chiari. Due limiti, dichiarati: la persona **ha letto ma non ha eseguito** la
conferma di un'azione sensibile (in casa non c'e' una serratura, un allarme o un garage: vedi la voce 5 di
`docs/VERIFICA-IN-CASA.md`), e il giudizio e' di una persona sola.
**La guida ai piani** non c'e': i piani sono passati alla `0.7.0` (#191).
