---
title: "feat(frontend): la scheda Cervello, il grafo interattivo della casa"
issue: 186
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: frontend"]
---

## Contesto

La parte visibile della fase: un grafo interattivo, per cluster, con i
contatori in alto, che mostra quello che Shinra sa. Il riferimento e' l'idea
vista in un video (una base di conoscenza resa come grafo), non l'estetica:
Shinra deve avere la propria.

Vincoli dell'ADR 0006: niente bundler. Il frontend resta in file inclusi sotto
le cinquecento righe, con ESLint e Prettier in CI.

## Cosa fare

- [ ] Una scheda «Cervello» nella navigazione, dentro i tre ingressi esistenti (nessun quarto ingresso)
- [ ] Grafo a forze, pan e zoom, clic su un nodo per aprire la scheda vera dell'oggetto (la stanza, la regola, la routine)
- [ ] Cluster colorati per tipo, etichette leggibili, legenda
- [ ] Contatori reali: collegamenti, sistemi attivi, agenti pronti
- [ ] Tema chiaro e scuro, e un modo di ridurre il movimento per chi lo chiede al sistema
- [ ] Ogni valore mostrato e' scappato: un dispositivo chiamato `<img onerror=...>` non deve eseguire niente
- [ ] Libreria servita dal repository, non da un CDN: la casa non deve dipendere da internet per disegnarsi
- [ ] Stato vuoto che insegna la mossa successiva, come le altre liste

## Criteri di accettazione

- [ ] Un test dei gesti con browser vero apre la scheda, vede i nodi e ne apre uno
- [ ] Nessun file del frontend supera le cinquecento righe
- [ ] La pagina non fa richieste a host esterni
- [ ] Funziona con la tastiera: un nodo si raggiunge e si apre senza mouse
