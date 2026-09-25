# Roadmap — da 0.1.0 a 1.0.0

Ogni versione minor corrisponde a una fase. Ogni fase e' **rilasciabile**: al
tag il sistema deve essere installabile da zero, avviabile e utilizzabile.
Nessuna fase inizia prima che la precedente sia taggata.

Il principio che ordina le fasi: **quasi tutto cio' che manca dipende da due
pezzi di infrastruttura che oggi non esistono — uno scheduler e un database.**
Costruire funzioni prima di quelli significa riscriverle dopo.

---

## v0.1.0 — Impianto chiuso

> Nessuna funzione nuova. Solo cio' che oggi va in errore certo o e' pericoloso.

**Perche' per prima.** Due funzioni non hanno mai potuto funzionare, e
trentotto endpoint su trentanove accettano comandi senza autenticazione. Finche'
questo e' vero, ogni funzione nuova nasce sopra una superficie di attacco aperta.

| # | Lavoro | Riferimento |
| :-- | :--- | :--- |
| 01 | `DataStore.add_knowledge_item()` mancante | BLK-01 |
| 02 | `OllamaClient.generate()` mancante | BLK-02 |
| 03 | Autenticazione come dipendenza su tutto il router | SEC-01 |
| 04 | Verifica firma Alexa e `applicationId` | SEC-02 |
| 05 | Blocco della dashboard lato server | SEC-03 |
| 06 | PIN con hash, login corretto, rate limit su proxy | SEC-04 |
| 07 | Segreti fuori da git e in variabili d'ambiente | SEC-05 |
| 08 | `debug: false`, header di sicurezza, CORS | SEC-06 |
| 09 | Client Home Assistant unico e dinamico | REL-04 |
| 10 | Test di regressione sui difetti bloccanti | — |

**Criteri di uscita**
- I test di regressione dei due bloccanti passano senza marcatore `xfail`.
- Una richiesta non autenticata a `/api/modes/{nome}/activate` risponde `401`.
- Una POST su `/api/alexa` senza firma valida risponde `400`.
- `git ls-files` non elenca `config/config.yaml` ne' alcun file con dati personali.
- CI verde su lint, formattazione e test.

---

## v0.2.0 — Fondamenta

> I due pezzi mancanti, piu' la rete di sicurezza che permette di modificare il
> codice senza paura.

**Perche' adesso.** Timer, promemoria, automazioni, storico, spiegabilita' e sei
delle sette funzioni complementari poggiano tutte su scheduler e database.
Sono un investimento unico che sblocca l'intero resto della roadmap.

| # | Lavoro | Sblocca |
| :-- | :--- | :--- |
| 11 | Scheduler persistente (APScheduler con job store) | REL-01, REL-02, tutte le automazioni |
| 12 | SQLite + SQLAlchemy al posto dei file JSON, con migrazione | Storico, transazioni, diario |
| 13 | Memoria di conversazione per sessione | REL-03, multiutente reale |
| 14 | Configurazione in cache con invalidazione al salvataggio | REL-06 |
| 15 | Registro delle azioni (chi, cosa, quando, da quale canale) | Sicurezza, spiegabilita' |
| 16 | Layout `src/shinra/` e pacchetto installabile | Aggiunta pulita di moduli |
| 17 | Intent router estratto da `process_user_input` | Testabilita', nuovi intent |
| 18 | Suite di test, copertura ≥ 60%, pre-commit | Tutto il resto |

**Criteri di uscita**
- Un promemoria impostato a voce suona a server riavviato e senza browser aperto.
- Un timer scaduto viene marcato completato e non riappare.
- Due utenti in due schede diverse non condividono il contesto.
- `pytest --cov` riporta almeno il 60%.
- Uno script di migrazione porta i JSON esistenti nel database senza perdita.

---

## v0.3.0 — Copertura

> Riempire la matrice dei domini. A questo punto ogni voce e' un modulo nuovo,
> non un'impresa architetturale.

| # | Lavoro |
| :-- | :--- |
| 19 | WebSocket Home Assistant: stato in tempo reale ed **eventi** |
| 20 | Tool `lock`, `media_player`, `vacuum`, `fan` |
| 21 | Clima esteso (modalita', ventola, umidita') e tapparelle con posizione |
| 22 | Presenza e geofencing su `person` |
| 23 | Sicurezza domestica: allarme, aperture, notifica intrusione |
| 24 | Energia con fasce orarie italiane F1/F2/F3 |
| 25 | Liste condivise, calendario, scadenze di manutenzione |
| 26 | Collegare la configurazione fantasma (fonti RSS, categorie per profilo, argomenti vietati) |

**Criteri di uscita**
- Ogni dominio elencato come controllabile nell'interfaccia ha un tool che lo comanda.
- Nessuna impostazione esposta nell'interfaccia e' priva di un consumatore nel codice.
- Un evento Home Assistant (porta aperta) e' osservabile dall'applicazione.

---

## v0.4.0 — Proattivita'

> Shinra smette di aspettare la domanda. E' qui che si chiude anche la promessa
> sulla privacy.

| # | Lavoro |
| :-- | :--- |
| 27 | Motore di regole con trigger su evento, stato e orario |
| 28 | Nodi condizione e trigger temporale nell'editor a grafo |
| 29 | Notifiche web push (VAPID, handler `push` nel service worker) |
| 31 | Riconoscimento vocale locale (faster-whisper) al posto della Web Speech API |
| 32 | RAG con embedding sulla knowledge base |
| 33 | Satelliti vocali per stanza |

**Criteri di uscita**
- ~~Nessun audio della casa lascia la rete locale.~~ — soddisfatto per il
  microfono di Shinra; **non** per Alexa, dove l'audio va ad Amazon per
  costruzione. Vedi la tabella nel README.
- Una regola creata dall'interfaccia scatta da sola su un evento reale. —
  **da verificare in casa**: il motore funziona e i test coprono la catena,
  ma nessuno ha ancora guardato una regola scattare davvero.
- ~~Il contesto inviato al modello non cresce linearmente con la knowledge
  base.~~ — soddisfatto dalla #32.

La **#30**, la parola di attivazione, e' stata spostata alla `v0.5.0`: il suo
criterio sui falsi positivi si misura solo con un microfono acceso per giorni,
e non c'era hardware su cui farlo. Vedi la scheda.

---

## v0.5.0 — Prodotto

> Quello che serve perche' lo installi qualcuno che non sei tu.

| # | Lavoro | Stato |
| :-- | :--- | :--- |
| 125 | Le chiamate all'API partono senza intestazioni di autenticazione | fatta (#130) |
| 127 | Ogni lista vuota insegna la mossa successiva | fatta (#131) |
| 123 | La colonna della console racconta adesso, non la diagnostica | fatta (#132) |
| 128 | Da otto ingressi a tre, senza perdere niente | fatta (#133) |
| 134 | La barra della navigazione ritagliava il menu di configurazione | fatta (#135) |
| 136 | Tre test delle scadenze dipendevano dal giorno in cui giravano | fatta (#137) |
| 124 | Impostazioni a sezioni, aperta solo quella che serve | fatta (#138) |
| 126 | Una scorciatoia per «a quest'ora fai questo» | fatta (#140) |
| 139 | Un nome di icona sbagliato non da' errore, da' un buco | fatta (#142) |
| 118 | Lo spegnimento del servizio si pianta: 90 secondi e poi SIGKILL | fatta (#157) |
| 152 | Il fondo ambientale resta scuro in tema chiaro su quattro schede | fatta (#164) |
| 153 | `switchTab` con una scheda che non esiste lascia la pagina vuota | fatta (#163) |
| 159 | Il canale degli eventi rifiuta i dispositivi fidati | fatta (#160) |
| 161 | Una sessione scaduta non viene detta: ritenta in silenzio | fatta (#162, #173) |
| 35 | Backup e restore della configurazione, con versione di schema | fatta (#165, #166) |
| 30 | Wake word locale (openWakeWord) — spostata dalla `v0.4.0` | da fare |
| 34 | Scomporre `index.html` (7.438 righe) in moduli ES | in corso (#144-#151, #176-#178) |
| 36 | Internazionalizzazione (stringhe ed espressioni regolari di intent) | in corso (#181) |
| 37 | Immagine Docker e add-on per Home Assistant OS | in corso (#168, #169) |
| 38 | Documentazione utente e guida all'installazione verificata | in corso (#167) |
| 170 | L'intervista di apprendimento impara poco | in corso (#171, #174) |

Tre voci sono **in corso** e vale la pena dire cosa manca a ciascuna, invece
di lasciarlo dedurre dal numero:

- **#37** — l'immagine Docker, il `docker-compose.yml` e la pubblicazione su
  GHCR per `amd64` e `arm64` ci sono. Manca l'add-on per Home Assistant OS, ed
  e' fermo per una ragione: chi sviluppa qui usa Home Assistant Container, non
  HA OS, quindi l'add-on non sarebbe provabile in casa; e l'ingress
  riscriverebbe il percorso di base, che oggi novantadue riferimenti assoluti
  della pagina non sopportano — cioe' e' lavoro della **#34**, non di questa.
- **#38** — la CI costruisce l'immagine, la avvia e verifica di riuscire
  davvero a entrare: e' cosi' che si e' scoperto che l'immagine partiva senza
  `data/examples/` e nessuno poteva accedere. Manca la documentazione utente
  vera e propria.
- **#36** — gli schemi con cui Shinra **capisce** una frase stanno in un file
  per lingua, e aggiungerne una non richiede di toccare il codice: lo prova un
  test che ne inventa una. Restano le stringhe rivolte all'utente, il prompt
  di sistema parametrico, la scelta per utente e una seconda lingua vera.
- **#170** — l'intervista adesso dice quando non ha capito e fa vedere cosa ha
  capito prima di salvarlo. Mancano le domande singole al posto di quelle
  triple, il non chiedere cio' che e' gia' nel database, e tutta la tappa due:
  gli alias dalle entita' vere di Home Assistant e le routine complete.

### L'interfaccia, prima della 1.0.0 — fatta

Le sei voci da **#125** a **#126** sono state fatte in quest'ordine, e non era
casuale: le prime due erano difetti — una lista vuota per mancanza di permessi
e una lista vuota che non spiega niente hanno lo stesso aspetto, e finche' e'
cosi' non si sa nemmeno quali schermate siano davvero vuote. Le altre quattro
erano scelte di struttura, e una scelta di struttura si fa dopo aver smesso di
guardare dati sbagliati.

I due vincoli sono stati rispettati e hanno una guardia ciascuno: **nessuna
funzione e' sparita** — al massimo un clic piu' lontana — e **l'editor a nodi
e' rimasto al primo livello**, dentro «Automazioni e routine».

#### Cosa dicono i numeri, misurati

| | prima | dopo |
| :--- | :-- | :-- |
| Ingressi di primo livello | 8 | 3 + configurazione |
| Colonna della console: tag a riposo | 27 | 19 (**-30%**, non il terzo promesso) |
| Colonna della console: diagnostica a vista | 3 | 0 |
| Impostazioni: campi visibili all'apertura | 17 | 0 |
| Impostazioni: pannelli aperti insieme | 8 | 1 |
| Clic in piu' per la funzione piu' lontana | — | 1 (il criterio ne ammetteva 2) |

Il **-30%** della #123 e' l'unico criterio non raggiunto, ed e' scritto nella
guardia insieme al tetto: la scheda chiedeva insieme di togliere la
diagnostica e di aggiungere i prossimi scatti, e le due cose non stavano nello
stesso conto.

#### Quello che si e' imparato per strada

Tre difetti non erano in nessuna scheda e **nessuna guardia poteva vederli**,
perche' leggono il sorgente e nel sorgente erano tutti corretti:

- un menu ritagliato da `overflow-x-auto` su un antenato (#134);
- due nomi di icona che in lucide non esistono — da qui la #139;
- fondi grigi senza riscrittura per il tema chiaro, nella famiglia che la
  guardia dei colori salta apposta.

Tutti e tre trovati **guardando la schermata renderizzata**. Da qui in avanti
ogni modifica all'interfaccia si guarda prima di aprire la PR.

Due difetti sono invece emersi **provando a rompere il codice apposta**: il
server accettava un'azione che non diceva su cosa agire (#126), e tre test
prendevano meta' del tempo dal calendario vero e meta' da una costante (#136).

La **#34** (frontend modulare) era la sorella maggiore di tutte: `index.html`
e' passato da 6.600 a **7.438 righe** proprio facendo queste sei. Su un file
cosi' ogni modifica all'interfaccia costa piu' del dovuto. E' per questo che e'
stata la prima cosa affrontata dopo — ed e' a meta' strada.

### Il frontend scomposto — a meta' strada

Otto PR unite (#144, #145, #146, #147, #148, #149, #150, #151) hanno tolto CSS
e JavaScript da `index.html` e li hanno divisi per area.

| | prima | dopo |
| :--- | :-- | :-- |
| `web/templates/index.html` | 7.438 righe | **160** |
| File di markup | 1 | 10: l'ossatura e nove pezzi inclusi |
| File JavaScript | 1, dentro l'HTML | 23, il piu' lungo di **460** righe |
| File CSS | 1, dentro l'HTML | 5 |
| ESLint e Prettier | non esistevano | in CI, obbligatori |
| HTML costruito concatenando stringhe | ovunque | **zero**, con guardia |

Il pezzo piu' importante non e' la divisione, e' il modello `_html`: ogni
valore che finisce nella pagina viene scappato, e l'unico modo per disattivarlo
e' un marcatore esplicito su cui c'e' una guardia a parte. Prima bastava un
dispositivo chiamato `<img onerror=...>` in Home Assistant.

ESLint, al primo giro, ha trovato un difetto vero gia' in produzione: il
pulsante «+ Timer» chiamava un nome che non e' mai esistito.

Lo **stato condiviso** sta in un contenitore solo dalla #177: undici
variabili che attraversavano le aree — `activeUserId` girava per cinque file —
adesso sono campi di `Stato`, in `web/static/js/stato.js`. Le altre
trentatre' sono rimaste dove stanno: le usa un'area sola, e portarle li' non
direbbe niente a nessuno.

Il **bundler** e' stato valutato e scartato: [ADR 0006](adr/0006-niente-bundler.md).
I moduli saranno nativi, serviti come stanno — l'aggiornamento in casa resta
`deploy.sh` e basta, senza node sul server.

Restano i **moduli ES veri**: i ventidue file sono ancora copioni classici
caricati in ordine, e devono restarlo finche' la pagina chiama le funzioni
dagli `onclick` — 149 fra attributi nel markup e stringhe generate. Vedi la
scheda della #34 per l'ordine in cui si toglieranno.

La scomposizione ha prodotto **due regressioni**, tutte e due trovate in casa e
chiuse (#154, #155). Da li' e' nata la **#156**: sette gesti dell'editor a nodi
girano in CI con un browser vero, perche' una guardia che legge il sorgente non
puo' sapere se un clic arriva o se se lo mangia un antenato.

### Lo spegnimento — fatto

La **#118** e' chiusa dalla #157. Il servizio aspettava all'infinito su una
websocket aperta e si fermava solo col SIGKILL di systemd, novanta secondi
dopo. Ora la lettura e la coda si aspettano insieme, e c'e' un tetto di dieci
secondi. Il test spegne un uvicorn vero con una websocket aperta e cronometra,
**senza** la rete di sicurezza: con la rete il difetto costava dieci secondi e
il test sarebbe restato verde lo stesso.

---

## v1.0.0 — Stabile

Criteri di uscita, tutti obbligatori:

1. Nessun difetto aperto di gravita' critica o alta.
2. Copertura dei test ≥ 70% su `src/shinra/`.
3. Installazione da zero eseguita e verificata su una macchina pulita seguendo
   solo la documentazione.
4. Trenta giorni di esercizio reale senza regressioni.
5. Nessuna impostazione esposta senza un consumatore nel codice.
6. `SECURITY.md` senza difetti noti non risolti.
7. Changelog completo dalla `0.1.0`.

---

## Dopo la 1.0.0 — funzioni complementari

Sette direzioni in cui un hub locale e italiano con un LLM a bordo ha un
vantaggio strutturale. **Nessuna inizia prima della `1.0.0`**, e ognuna
poggia su infrastruttura costruita nelle fasi precedenti.

| Funzione | Dipende da |
| :--- | :--- |
| Consulente energetico a fasce F1/F2/F3 | v0.3.0 (energia) |
| Modalita' presenza e check-in per anziani | v0.3.0 (presenza) + v0.4.0 (push) |
| Registro di casa (scadenze, garanzie, contatori) | v0.2.0 (database) |
| Briefing personale per profilo | v0.2.0 (scheduler) + v0.3.0 (config collegata) |
| Spiegabilita': «perche' l'hai fatto?» | v0.2.0 (registro azioni) |
| Cucina come contesto (ricette, timer, lista) | v0.2.0 (scheduler) + v0.3.0 (liste) |
| Diario della casa | v0.2.0 (database) + v0.3.0 (eventi) |
