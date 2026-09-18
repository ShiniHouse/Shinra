---
title: "docs: documentazione utente e installazione verificata"
issue: 38
milestone: "v0.5.0"
labels: ["tipo: attivita'", "area: documentazione"]
---

## Contesto

Il README e' completo ma descrive uno stato non del tutto reale: promette
privacy totale mentre il riconoscimento vocale passa da Google, e istruisce a
disattivare protezioni del reverse proxy per far funzionare Alexa. Serve una
revisione a fine progetto, quando le funzioni corrispondono alle promesse.

## Cosa fare

- [ ] Riscrivere il README perche' descriva il comportamento reale
- [ ] Guida all'installazione per ciascuna modalita': Docker, add-on, manuale
- [ ] Guida alla configurazione iniziale, dal primo avvio alla prima routine
- [ ] Guida alla risoluzione dei problemi, ricavata dai difetti realmente incontrati
- [ ] Documentazione di riferimento delle API
- [ ] Guida allo sviluppo di un modulo nuovo, secondo `ARCHITECTURE.md` §4
- [x] **Verifica**: installazione da zero su una macchina pulita seguendo solo la documentazione, annotando ogni punto in cui serve conoscenza non scritta

## Criteri di accettazione

- [ ] Una persona che non conosce il progetto installa e configura Shinra seguendo solo la documentazione
- [ ] Ogni affermazione del README e' verificabile
- [ ] La guida allo sviluppo permette di aggiungere un modulo senza leggere il codice dell'agente

## Il collaudo, fatto

Macchina pulita, Debian, niente Shinra e niente Ollama. Seguito **solo** il
README, passaggio per passaggio, annotando dove serviva sapere qualcosa che
non c'era scritto.

Quello che ha funzionato al primo colpo, e vale la pena dirlo:

- `git clone` + `python3 -m venv` + `pip install -e .` — nessuna dipendenza di
  sistema mancante oltre a `python3-venv`, nessun compilatore, nessuna ruota
  da costruire a mano;
- l'applicazione **si migra il database da sola** al primo avvio: non c'e'
  nessun comando da lanciare, e infatti il README non ne parlava — ma non
  diceva nemmeno che non serve, e questo manda a cercarlo;
- senza Ollama e senza Home Assistant parte lo stesso e **dice nel log cosa
  manca**, invece di rompersi;
- il profilo amministratore viene creato, il PIN generato, l'accesso funziona.

I sei punti in cui serviva conoscenza non scritta:

| # | Cosa mancava |
| :-- | :--- |
| 1 | **Il modello sbagliato.** Il README diceva `ollama pull qwen2.5:3b` in quattro punti; il codice e `config.example.yaml` configuravano `gemma2:9b`. Chi seguiva le istruzioni scaricava un modello e ne configurava un altro: la chat non risponde e il motivo non compare da nessuna parte |
| 2 | **Ollama non veniva mai installato.** La sezione si chiamava «Installazione e Download Modello Ollama» e conteneva solo `ollama pull` |
| 3 | **Il PIN del primo accesso** era nominato solo dentro il riquadro «Aggiornando dalla versione precedente», che chi installa da zero salta |
| 4 | **Dove puntare il browser** non era scritto da nessuna parte |
| 5 | **`python3-venv`** su Debian e' un pacchetto a parte: senza, ci si ferma al secondo comando |
| 6 | **I parametri di configurazione** documentavano uno schema che non esiste: `llm.provider` (mai esistito), `llm.base_url` (rinominato `ollama_url`), e il token dentro `config.yaml`, da dove la #7 lo aveva tolto |

Il primo e il sesto sono gli unici che fanno perdere davvero tempo: gli altri
si superano indovinando, quelli no.

### Cosa impedisce che tornino

Tre guardie in `test_coerenza_configurazione.py`:

- il modello che il README dice di scaricare deve essere il predefinito del
  codice **e** quello di `config.example.yaml`;
- ogni chiave mostrata nel blocco dei parametri deve esistere in `AppConfig`;
- quel blocco non puo' mostrare un campo dichiarato segreto in
  `config/secrets.py`.

La seconda e' nata da un errore mio: riscrivendo il blocco ho messo
`voce.trascrizione` al posto di `voce.motore`. Rileggere non basta.

### Cosa resta della #38

Il README completo, la guida Docker e quella all'add-on aspettano la #37: non
si documenta un'installazione che non esiste ancora. La documentazione delle
API e la guida allo sviluppo di un modulo sono lavoro a se'.
