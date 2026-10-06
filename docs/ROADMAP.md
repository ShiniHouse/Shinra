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

## v0.5.0 — Prodotto — rilasciata il 1 ottobre 2026

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
| 30 | Wake word locale (openWakeWord) — spostata dalla `v0.4.0` | **spostata alla `v0.6.0`** (#211): dove gira e' deciso (ADR 0007), il codice non c'e' |
| 34 | Scomporre `index.html` (7.438 righe) in moduli ES | fatta (#144-#151, #176-#178, #200, moduli ES veri) |
| 36 | Internazionalizzazione (stringhe ed espressioni regolari di intent) | chiusa in parte (#181, #203): il meccanismo, l'inglese e la lingua per persona. Il resto alla `v0.6.0` (#205, #206, #207) |
| 37 | Immagine Docker e add-on per Home Assistant OS | chiusa in parte (#168, #169): la strada Docker. L'add-on alla `v0.7.0` (#282); la prova su Raspberry Pi 4 e' rimandata |
| 38 | Documentazione utente e guida all'installazione verificata | chiusa in parte (#167, #204): le guide sono scritte. Il collaudo di chi non le ha scritte alla `v0.6.0` (#208) |
| 170 | L'intervista di apprendimento impara poco | chiusa in parte (#171, #174): dice quando non ha capito e mostra cosa ha capito. Il resto alla `v0.6.0` (#209, #210) |

Quattro voci sono **chiuse in parte**, e vale la pena dire cosa manca a
ciascuna invece di lasciarlo dedurre dal numero. Il resto e' nella `v0.6.0`:

- **#37** — l'immagine Docker, il `docker-compose.yml` e la pubblicazione su
  GHCR per `amd64` e `arm64` ci sono. Manca l'add-on per Home Assistant OS
  (#282, ex #212): chi sviluppa qui usa Home Assistant Container, non HA OS, quindi
  l'add-on va provato su un'istanza HA OS, anche virtuale. L'ostacolo dell'*ingress* — novantadue
  riferimenti assoluti nella pagina — e' adesso lavoro di quella scheda, non
  piu' della #34.
- **#38** — la CI costruisce l'immagine, la avvia e verifica di riuscire
  davvero a entrare: e' cosi' che si e' scoperto che l'immagine partiva senza
  `data/examples/` e nessuno poteva accedere. Con la #204 ci sono la guida
  all'installazione, la guida allo sviluppo e il riferimento delle API
  (generato dal codice). Manca il collaudo (#208): nessuno che non le abbia
  scritte le ha ancora seguite.
- **#36** — gli schemi con cui Shinra **capisce** una frase, le frasi che
  **dice**, il prompt di sistema e la lingua per persona sono fuori dal codice,
  e c'e' l'inglese: due persone della stessa casa ricevono risposta ciascuna
  nella propria. Restano timer e promemoria (#205), le etichette della
  dashboard (#206) e i messaggi degli strumenti (#207).
- **#170** — l'intervista dice quando non ha capito e fa vedere cosa ha capito
  prima di salvarlo. Mancano le domande singole, il non chiedere cio' che e'
  gia' nel database (#209) e la tappa due: gli alias dalle entita' vere di
  Home Assistant e le routine complete (#210).

La **#34** e la **#30** hanno avuto esiti opposti: la prima e' **fatta per
intero** (moduli ES nativi, vedi sotto); la seconda e' **spostata** alla `v0.6.0`
(#211) senza codice, con la decisione su dove gira (ADR 0007).

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

### Il frontend scomposto — fatto

Otto PR unite (#144, #145, #146, #147, #148, #149, #150, #151) hanno tolto CSS
e JavaScript da `index.html` e li hanno divisi per area.

| | prima | dopo |
| :--- | :-- | :-- |
| `web/templates/index.html` | 7.438 righe | un'ossatura di poche righe |
| File di markup | 1 | 10: l'ossatura e nove pezzi inclusi |
| File JavaScript | 1, dentro l'HTML | decine di moduli ES, nessuno oltre le cinquecento righe (con guardia) |
| File CSS | 1, dentro l'HTML | uno per area |
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

Gli **attributi in linea** erano l'ostacolo vero ai moduli: 149 fra il markup
e le stringhe generate dal JavaScript. Sono diventati gesti con nome (#179,
#200), gli argomenti viaggiano come JSON, e solo allora i ventitre copioni sono
diventati **moduli ES nativi** con un punto d'ingresso (#202). Il prezzo non
previsto era la cache: un `import` non porta la versione, e il server risponde
adesso a `/static/` con `Cache-Control: no-cache`.

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

## v0.6.0 — Il Cervello

> Shinra mostra quello che sa e quello che fa, e divide il lavoro fra agenti
> che vedono solo i propri strumenti. Resta locale: i collegamenti esterni
> sono un'opzione, spenta di default.

**Perche' in questo ordine.** La scommessa della fase e' che il modello
locale scelga bene gli strumenti. Si misura prima (#183), e la misura decide
quanto ambiziose sono le schede sugli agenti. Il grafo che si illumina viene
dopo un agente affidabile, non prima: un bel grafo su una risposta sbagliata
e' una demo.

| # | Lavoro | Area |
| :-- | :--- | :--- |
| 183 | Banco di prova: quale modello sceglie lo strumento giusto | misura |
| 184 | ADR: agenti specializzati per dominio | decisione |
| 185 | Endpoint che descrive la casa come grafo | grafo |
| 186 | La scheda Cervello, il grafo interattivo | grafo |
| 187 | Il grafo regge un telefono e un mini-PC | grafo |
| 188 | Il ciclo dell'agente racconta cosa sta facendo | grafo vivo |
| 189 | Il grafo vivo: si illumina quando Shinra lavora | grafo vivo |
| 190 | Router e agenti di dominio | agenti |
| 192 | Le azioni sensibili chiedono sempre conferma | sicurezza |
| 195 | Una regola e un piano scattano davvero in una casa vera | verifica |
| 196 | Nessun file del backend sopra le cinquecento righe | debito |
| 197 | mypy obbligatorio anche su api e channels | debito |
| 198 | Guida al Cervello, agli agenti e ai piani | documentazione |

**Criteri di uscita**
- Il banco di prova (#183) ha numeri per il modello di casa, con e senza agenti, e
  gli agenti di dominio fanno meglio del ciclo unico, o la scheda dice il contrario.
  *Un secondo modello non e' richiesto (decisione del 2026-10-06): il 7B non sta nella
  memoria del server di casa e non e' previsto di cambiarlo.*
- Nessun percorso, nemmeno un piano o un agente, raggiunge una serratura o
  l'allarme senza conferma (#192).
- Con l'opzione esterna spenta nessuna richiesta esce dalla rete locale.
- Il grafo regge il dispositivo piu' lento della casa (#187).
- Il criterio della `0.4.0` sulle regole che scattano in casa e' verificato o
  dichiarato non raggiunto (#195).

---

## v0.7.0 — Rifinitura

> Si finisce quello che la `0.6.0` ha lasciato aperto — le lingue, l'intervista,
> la voce, i plugin — e si prepara il terreno alla fase che viene dopo: Shinra
> impara a usare un **server di inferenza dedicato** (un'altra macchina della rete
> locale) e si misura se piccoli agenti locali possono fare il lavoro ripetitivo
> dello sviluppo. Resta locale.

**Perche' in questo ordine.** La `0.8.0` aggiunge al prompt ricordi e riassunti, e
un modello su una CPU senza scheda grafica e' gia' al limite (la `#183` lo ha
misurato). Prima si decide *dove* gira il modello e *con che velocita'*, poi si
costruisce sopra. Il residuo della `0.6.0` — lingue, intervista, voce — non ha
dipendenze fra loro e si fa in parallelo. I tre lavori nuovi, con la ricerca sull'hardware
e le schede, stanno in [`docs/proposte/v0.7.0/`](proposte/v0.7.0/README.md).

| # | Lavoro | Area |
| :-- | :--- | :--- |
| 193 | Manifesto e permessi dei plugin | plugin |
| 194 | Modello esterno opzionale, spento di default — *da valutare* | integrazioni |
| 205 | Timer e promemoria capiscono piu' di una lingua — *residuo della #36* | i18n |
| 206 | Le etichette della dashboard escono dal codice — *residuo della #36* | i18n |
| 207 | I messaggi degli strumenti e dell'intervista nella lingua di chi parla — *residuo della #36* | i18n |
| 208 | Collaudo della documentazione da parte di chi non l'ha scritta — *residuo della #38* | documentazione |
| 209 | Intervista: una domanda per volta, niente domande su cio' che la casa sa — *residuo della #170* | apprendimento |
| 210 | Intervista: dalle entita' vere alle routine complete — *residuo della #170* | apprendimento |
| 211 | La parola di attivazione nel browser — *residuo della #30* | voce |
| 191 | Piani a piu' passaggi, con correzione — *spostata dalla `0.6.0`: il «piu' passaggi» del banco e' a 5/10 con gli agenti, e il piano e' il lavoro piu' grosso per un guadagno incerto* | agenti |
| 282 | L'add-on per Home Assistant OS — *residuo della #37 (ex #212, ricreata dopo la cancellazione). La prova su Raspberry Pi 4 e' rimandata* | distribuzione |
| 240 | Ollama su un'altra macchina della rete: configurazione, protezione, misura | infrastruttura |
| 241 | Il banco di prova sull'hardware candidato, misurato e non stimato | misura |
| 242 | Aiutanti locali per il lavoro di sviluppo, con il guadagno misurato | strumenti |

**Criteri di uscita**
- Shinra usa un Ollama su un'altra macchina della rete locale, scelto da
  configurazione; l'endpoint **non** e' raggiungibile da fuori la rete di casa e la
  guida dice come proteggerlo (Ollama non ha autenticazione).
- Il banco della `#183` ha numeri sull'hardware attuale e su **almeno un
  candidato**, misurati; la guida dice quale hardware serve per quale modello.
- Le etichette della dashboard e i messaggi degli strumenti sono in due lingue, con
  la guardia di parita' (`#206`, `#207`, `#205`).
- L'intervista fa una domanda per volta e produce routine complete (`#209`, `#210`).
- La documentazione e' stata seguita da una persona che non l'ha scritta (`#208`).
- Gli aiutanti locali hanno un esito **per tipo di compito** — si usano, oppure la
  scheda dice che non convengono — e nessun loro output si applica senza una
  verifica meccanica (test, linter, confronto).

---

## v0.8.0 — Memoria viva

> Shinra ricorda, e chi abita la casa puo' vedere cosa ricorda, correggerlo e
> farglielo dimenticare. La storia vecchia diventa un riassunto invece di sparire,
> e di notte la casa «ci ripensa» — **proponendo**, mai decidendo. Resta locale:
> un canale esterno e' un'opzione, spenta di default, e puo' non nascere.

**Perche' in questo ordine.** Prima si sistema il contesto (oggi il prompt supera
la finestra e Ollama taglia in silenzio), poi si decide la privacy della memoria e
si costruisce lo schema, poi si rende visibile, poi si comprime la storia. Il sogno
viene dopo perche' ha bisogno di materiale e di fiducia: tutto cio' che scrive nasce
**proposto**. I canali esterni vengono per ultimi e dopo una decisione scritta, perche'
toccano la promessa della `0.6.0` sulla rete locale. La proposta completa, con le
ventinove schede (issue `#243`–`#271`), sta in [`docs/proposte/memoria-viva/`](proposte/memoria-viva/README.md).

| # | Lavoro | Area |
| :-- | :--- | :--- |
| 243 | ADR: chi vede e chi puo' cambiare cio' che Shinra ricorda | decisione |
| 244 | Misura e budget del contesto | contesto |
| 245 | Un ricordo ha proprietario, origine, importanza e storia | memoria |
| 246 | Il recupero pesa importanza, recenza e uso | memoria |
| 247 | Quali ricordi hanno contribuito, per richiesta | memoria |
| 248 | ADR: la ricerca per vettori regge la casa? (misura) | decisione |
| 249 | API della memoria per profilo | memoria |
| 250 | La memoria in chiaro nell'interfaccia | trasparenza |
| 251 | Esporta e importa i ricordi in Markdown | trasparenza |
| 252 | «Ho usato questi ricordi» sotto la risposta | trasparenza |
| 253 | Cancellare e' cancellare, dappertutto | privacy |
| 254 | ADR: si conserva la conversazione? | decisione |
| 255 | Riassunti persistenti e finestra mobile | storia |
| 256 | Compressione in background con Ollama | storia |
| 257 | Finestra adattiva al budget | storia |
| 258 | Materiali della giornata | sogno |
| 259 | Il compito notturno | sogno |
| 260 | Fusione dei ricordi in proposte | sogno |
| 261 | Abitudini contate dal codice, raccontate dal modello | sogno |
| 262 | Da intuizione a bozza di regola, spenta | sogno |
| 263 | Interfaccia delle intuizioni | sogno |
| 264 | Guardie contro l'avvelenamento della memoria | sicurezza |
| 265 | ADR: canali esterni | decisione |
| 266 | Astrazione del canale bidirezionale | canali |
| 267 | Il primo connettore esterno, spento di default | canali |
| 268 | Interfaccia dei canali e dell'abbinamento | canali |
| 269 | Banco di valutazione della memoria | misura |
| 270 | Guardie di CI della fase | verifica |
| 271 | Guida alla memoria | documentazione |

**Criteri di uscita**
- Il banco della `#183` riporta **«Troncati = 0»** con il `num_ctx` di produzione: nessun prompt
  supera la finestra senza traccia.
- Il ranking a tre fattori **migliora** recall@k e MRR sul banco di valutazione, oppure la scheda dice
  che non migliora e i pesi restano a zero.
- Ogni ricordo e' visibile, correggibile e cancellabile dal suo proprietario; **un profilo non legge,
  non modifica e non cancella i ricordi privati di un altro** (guardia su tutte le rotte).
- Dopo una cancellazione il testo non e' piu' in nessuna tabella ne' nel backup successivo.
- La compressione della storia conserva i fatti chiave sul banco, e la latenza della risposta e' invariata.
- Il compito notturno gira entro il tetto di tempo sull'hardware della casa, **non scrive mai** un ricordo
  attivo, una regola attiva o un'azione, e due esecuzioni nella stessa notte non duplicano niente.
- Un corpus di almeno venti tentativi di iniezione non produce nessuno stato attivo.
- Con i canali esterni spenti, nessuna richiesta esce dalla rete locale; con uno acceso, una chat non
  abbinata non fa niente e una conferma di una chat non vale per un'altra.

---

## v1.0.0 — Stabile

Si arriva qui dalla `0.8.0`, **se non ci sono intoppi**: nessuna fase nuova in mezzo. Se la `0.8.0`
sposta troppo, i trenta giorni di esercizio (punto 4) la riconoscono prima di un utente.

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
| Briefing personale per profilo — *il riepilogo del mattino e' in parte nella `0.8.0`* | v0.2.0 (scheduler) + v0.3.0 (config collegata) |
| Spiegabilita': «perche' l'hai fatto?» — *«che ricordi hai usato» e' nella `0.8.0`; resta il perche' di un'azione* | v0.2.0 (registro azioni) |
| Cucina come contesto (ricette, timer, lista) | v0.2.0 (scheduler) + v0.3.0 (liste) |
| Diario della casa — *le proposte del sogno sono un primo pezzo, nella `0.8.0`* | v0.2.0 (database) + v0.3.0 (eventi) |

**Rimandata, senza data:** la prova dell'immagine `arm64` su un Raspberry Pi 4 (era nella #212, ora divisa dall'add-on #282). In CI l'immagine si costruisce ma non si esegue su quell'hardware; se ne parlera' quando ci sara' un Pi da provare.
