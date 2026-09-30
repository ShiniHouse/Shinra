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
- [ ] **Il nome di ogni cluster scritto sul grafo**, grande e sospeso accanto al suo gruppo di nodi (nel riferimento: CONTENUTI, FINANZA, AGENTI, ARCHIVIO...): a colpo d'occhio si legge dove sta cosa, senza aprire la legenda
- [ ] Contatori reali: collegamenti, sistemi attivi, agenti pronti
- [ ] **Lo stato di ogni sistema, in chiaro e in colore**: attivo, fermo, non raggiungibile. Un sistema spento — una regola disattivata, Home Assistant irraggiungibile, un modello che non risponde — si vede in rosso sul suo cluster, con la ragione al passaggio del mouse o alla tastiera (nel riferimento: «RISPOSTE OUTREACH: FERMO»). Il dato viene dall'endpoint della #185, non si indovina nel browser
- [ ] **Un pannello di controllo del grafo**: mostra/nascondi per tipo di nodo, ricerca di un nodo per nome, e le forze (distanza e attrazione) regolabili. Serve a chi ha centinaia di nodi e vuole guardarne un tipo solo; le scelte si ricordano per dispositivo
- [ ] **Modalita' a schermo intero**, pensata per un tablet a muro: niente barre, contatori grandi, e il grafo che si aggiorna da solo. E' lo stesso tablet su supporto che l'ADR 0007 indica per la parola di attivazione
- [ ] Tema chiaro e scuro, e un modo di ridurre il movimento per chi lo chiede al sistema
- [ ] Ogni valore mostrato e' scappato: un dispositivo chiamato `<img onerror=...>` non deve eseguire niente
- [ ] Libreria servita dal repository, non da un CDN: la casa non deve dipendere da internet per disegnarsi
- [ ] Stato vuoto che insegna la mossa successiva, come le altre liste

## Criteri di accettazione

- [ ] Un test dei gesti con browser vero apre la scheda, vede i nodi e ne apre uno
- [ ] Un sistema fermo compare in rosso nel grafo e nel registro in chiaro accanto, con il motivo; uno riattivato torna normale senza ricaricare la pagina
- [ ] Nascondere un tipo dal pannello toglie i suoi nodi e i loro cavi, e mostrarlo li riporta dove stavano
- [ ] Nessun file del frontend supera le cinquecento righe
- [ ] La pagina non fa richieste a host esterni
- [ ] Funziona con la tastiera: un nodo si raggiunge e si apre senza mouse
