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

- [x] Una scheda «Cervello» nella navigazione, dentro i tre ingressi esistenti (nessun quarto ingresso)
- [x] Grafo a forze, pan e zoom, clic su un nodo per selezionarlo e doppio clic (o Invio) per aprire la scheda vera dell'oggetto (la routine nell'editor, la regola, i dispositivi, la conoscenza) — vedi «Com'e' andata»
- [x] Cluster colorati per tipo, etichette leggibili, legenda
- [x] **Il nome di ogni cluster scritto sul grafo**, grande e sospeso accanto al suo gruppo di nodi (nel riferimento: CONTENUTI, FINANZA, AGENTI, ARCHIVIO...): a colpo d'occhio si legge dove sta cosa, senza aprire la legenda
- [x] Contatori reali: collegamenti, sistemi attivi, agenti pronti
- [x] **Lo stato di ogni sistema, in chiaro e in colore**: attivo, fermo, non raggiungibile. Un sistema spento — una regola disattivata, Home Assistant irraggiungibile, un modello che non risponde — si vede in rosso sul suo cluster, con la ragione al passaggio del mouse o alla tastiera (nel riferimento: «RISPOSTE OUTREACH: FERMO»). Il dato viene dall'endpoint della #185, non si indovina nel browser
- [x] **Un pannello di controllo del grafo**: mostra/nascondi per tipo di nodo, ricerca di un nodo per nome, e le forze (distanza e attrazione) regolabili. Serve a chi ha centinaia di nodi e vuole guardarne un tipo solo; le scelte si ricordano per dispositivo
- [x] **Modalita' a schermo intero**, pensata per un tablet a muro: niente barre, contatori grandi, e il grafo che si aggiorna da solo. E' lo stesso tablet su supporto che l'ADR 0007 indica per la parola di attivazione
- [x] Tema chiaro e scuro, e un modo di ridurre il movimento per chi lo chiede al sistema
- [x] Ogni valore mostrato e' scappato: un dispositivo chiamato `<img onerror=...>` non deve eseguire niente
- [x] Libreria servita dal repository, non da un CDN: la casa non deve dipendere da internet per disegnarsi
- [x] Stato vuoto che insegna la mossa successiva, come le altre liste

## Criteri di accettazione

- [x] Un test dei gesti con browser vero apre la scheda, vede i nodi e ne apre uno
- [x] Un sistema fermo compare in rosso nel grafo e nel registro in chiaro accanto, con il motivo; uno riattivato torna normale senza ricaricare la pagina
- [x] Nascondere un tipo dal pannello toglie i suoi nodi e i loro cavi, e mostrarlo li riporta dove stavano
- [x] Nessun file del frontend supera le cinquecento righe
- [x] La pagina non fa richieste a host esterni
- [x] Funziona con la tastiera: un nodo si raggiunge e si apre senza mouse

## Com'e' andata

Quattro moduli e un pezzo di markup, tutti sotto le cinquecento righe:
`cervello_fisica.js` (il layout, puro), `cervello_stile.js` (colori e limiti),
`cervello_disegno.js` (il canvas, il mouse, la tastiera), `cervello.js` (la scheda) e
`parti/cervello.html`. Sta dietro «Configurazione»: i tre ingressi restano tre.

- **Nessuna libreria.** Il layout e' un piccolo motore a forze (repulsione, molle,
  ammasso per cluster, gravita') di circa duecento righe: 240 nodi si dispongono in 39 ms,
  deterministici, e si provano con `node`. Una libreria sarebbe stata un file di terzi da
  tenere aggiornato per un uso cosi' piccolo, e il vincolo era niente CDN.
- **Decisione: un clic seleziona, il doppio clic (o Invio) apre.** La scheda diceva «clic
  per aprire», ma aprire al primo clic portava fuori dalla scheda ogni volta che si voleva
  solo vedere cosa e' collegato a cosa. La selezione mostra il dettaglio, con un pulsante
  «Apri».
- **Tutto si legge anche senza il canvas.** Sotto il grafo c'e' un elenco di pulsanti, uno
  per nodo; `data-nodi-visibili` dice quanti se ne vedono; l'annuncio per i lettori di
  schermo dice cosa e' selezionato.
- **Il nome di un nodo e' testo.** Nel canvas passa da `fillText`; nell'elenco e nel
  dettaglio da `_html`. Un test nel browser mette un dispositivo chiamato
  `<img onerror=...>` e verifica che non esegua niente.
- **Le etichette dei cluster non si sovrappongono**, e la vista segue il grafo mentre si
  assesta: si e' visto guardando il disegno su un server vero, non dai test.
- Il movimento ridotto (`prefers-reduced-motion`) fa nascere il grafo gia' disposto e fermo;
  a grafo quieto il ciclo di disegno si ferma.

**Non fatto, e va detto:**

- **Le prestazioni su un telefono e su un tablet** non sono misurate: e' la #187. Qui il
  tetto dei 400 nodi, il disegno a richiesta e il movimento ridotto sono le prime difese, ma
  nessuno ha ancora contato i fotogrammi su un dispositivo vero.
- **Il grafo non si illumina** quando Shinra lavora: e' la #189, che aspetta gli eventi
  dell'agente (#188).
- **L'aspetto non copia gli screenshot di riferimento**, e non voleva: l'idea e' la stessa,
  il disegno e' di Shinra. Se lo si vuole piu' vicino, e' un criterio nuovo.
- **La modalita' a schermo intero e' provata in logica, non su un tablet a muro.**
- Un tema chiaro e' coperto dai colori `[scuro, chiaro]` e dal fatto che i test di colore del
  progetto passano; non e' stato guardato a occhio con il tema chiaro acceso.
- **Non guardata su uno schermo di telefono**: il layout e' a una colonna sotto i 1024 pixel e i
  test del browser girano a 1400, ma l'aspetto su un telefono vero e' da vedere con la #187.
