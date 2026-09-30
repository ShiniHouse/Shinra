---
title: "feat(cervello): un endpoint che descrive tutto quello che Shinra sa e fa, come grafo"
issue: 185
milestone: "v0.6.0"
labels: ["tipo: funzione", "area: core"]
---

## Contesto

La scheda «Il Cervello» mostra un grafo: nodi e collegamenti. Tutto il
materiale esiste gia' nel database e nel codice — stanze, dispositivi, alias,
routine, regole, conoscenza, skill — ma nessuno lo espone come grafo. Questa
scheda e' il lato server: un solo endpoint che aggrega, con i permessi giusti.

## Cosa fare

- [x] `GET /api/cervello` restituisce `{nodi, collegamenti, clusters, sistemi, contatori, troncato}`
- [x] Tipi di nodo: stanza, dispositivo, alias, routine, regola, voce di conoscenza, skill, agente
- [x] Collegamenti veri, non decorativi: dispositivo -> stanza, alias -> dispositivo, regola -> dispositivi che comanda, routine -> nodi dell'editor, voce di conoscenza -> argomento
- [x] I contatori (collegamenti, sistemi attivi, agenti pronti) si calcolano dagli stessi dati, cosi' non possono divergere dal grafo
- [x] Ogni **sistema** (una famiglia di cose: le regole, le routine, Home Assistant, il modello, le fonti di notizie...) porta `stato` — `attivo`, `fermo` o `non_raggiungibile` — e un `motivo` leggibile quando non e' attivo. Lo stato si legge da cio' che il programma sa gia' (regole disattivate, ultimo esito del client di Home Assistant, risposta di Ollama), non si calcola nel browser
- [x] Ogni nodo appartiene a un cluster con un `nome` da mostrare sul grafo (stanze, dispositivi, regole, routine, conoscenza, strumenti, agenti)
- [x] Rispetta ruoli e permessi: un profilo vede solo cio' che puo' gia' vedere altrove
- [x] Il contenuto delle voci di conoscenza non esce: solo titolo e argomento
- [x] Un tetto ai nodi e il raggruppamento in cluster oltre quella soglia, deciso dal server

## Criteri di accettazione

- [x] Un test crea una casa di esempio e verifica che ogni oggetto compaia come nodo, una volta sola
- [x] Nessun collegamento punta a un nodo che non esiste
- [x] Senza autenticazione risponde `401`; con un profilo limitato non compaiono i nodi vietati
- [x] La risposta per una casa grande resta sotto un secondo
- [x] Con una regola disattivata e Home Assistant irraggiungibile, i due sistemi risultano `fermo` e `non_raggiungibile` con il loro motivo; riattivati, tornano `attivo`

## Com'e' andata

- Il grafo lo costruisce `domain/cervello.py` (puro: elenchi in, grafo fuori); lo
  raccoglie `services/cervello.py` (database, catalogo degli strumenti, stato dei
  sistemi); lo serve `api/routes_cervello.py`.
- **Il contenuto dei fatti non esce**: un nodo di conoscenza porta l'argomento, mai
  il testo, e un test cerca la frase segreta in tutta la risposta. Chi non ha il
  permesso `conoscenza.leggi` non vede nemmeno i nodi.
- **Lo stato dei sistemi viene dal programma**: Home Assistant dal canale degli
  eventi, il modello da Ollama (con quattro decimi di secondo di attesa e venti
  secondi di cache, cosi' un modello spento non blocca la scheda), le regole dal
  database, le notizie dalle fonti, le notifiche dalle iscrizioni. Un modello
  configurato ma non scaricato dice quale comando serve.
- **«Fermo» per le regole e' letterale**: basta una regola disattivata perche' il
  sistema «Regole» risulti fermo, col nome di chi e' spenta. Se risultasse troppo
  rumoroso, la soglia si cambia in un punto solo (`_stato_delle_regole`).
- **Gli agenti non esistono ancora** (#190): `agenti_noti()` ritorna una lista
  vuota e il contatore dice zero. Il grafo e i contatori sono gia' pronti a
  riceverli.
- Misurato su un server vero con Home Assistant e Ollama spenti: 0,46 s la prima
  volta, 11 ms con la cache. Su una casa di 500 alias e 300 fatti, sotto il secondo.
