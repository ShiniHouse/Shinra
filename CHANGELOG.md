# Changelog

Tutte le modifiche rilevanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto adotta il [Versionamento Semantico](https://semver.org/lang/it/).

Fino alla `1.0.0` il progetto e' in **beta**: le versioni `0.x` possono
introdurre modifiche incompatibili fra una minor e l'altra. Ogni minor
corrisponde a una fase della [roadmap](docs/ROADMAP.md) ed e' comunque
installabile e utilizzabile.

---

## [Non rilasciato]

### Corretto
- **Il badge della versione diceva `0.1.0` su un server aggiornato da un
  minuto**, con accanto il commit giusto: la piu' insidiosa delle mezze
  verita', perche' sembra informazione. Il numero veniva da
  `importlib.metadata`, che cerca lungo `sys.path` — e il servizio parte
  dalla cartella del progetto, che viene prima di site-packages. Li' era
  rimasto un `shinra.egg-info` di un'installazione precedente allo
  spostamento sotto `src/`, e veniva trovato per primo. Adesso il numero si
  legge da `pyproject.toml` quando il file e' accanto al codice: la stessa
  cartella da cui viene il commit mostrato di fianco, cosi' i due non
  possono contraddirsi. `deploy.sh` rimuove anche i metadati sorpassati
  rimasti nella radice — quelli veri stanno in `src/`.
- **`deploy.sh` senza argomenti poteva riportare il server indietro nel
  tempo, senza dirlo.** Installa l'ultimo tag — voluto: un server di casa
  non deve seguire il ramo di sviluppo. Ma mentre si lavora verso una
  versione nuova il tag piu' recente e' quello *precedente*, e su un server
  gia' aggiornato a `main` la stessa regola diventa una macchina del tempo.
  E' successo davvero: un comando lanciato per aggiornare ha riportato la
  casa alla `v0.1.0`. Adesso lo script confronta i due commit e si ferma,
  spiegando come prendere l'ultimo codice o come tornare indietro apposta
  con `--indietro`. Il codice torna indietro, i dati no: le migrazioni non
  si annullano, e il database resta con lo schema nuovo sotto
  un'applicazione che si aspetta quello vecchio.

### Aggiunto
- **La casa dice cosa succede, invece di rispondere quando le si chiede.**
  Connessione WebSocket a Home Assistant: gli stati arrivano nel momento in
  cui cambiano, anche quando a premere e' l'interruttore a muro — il caso che
  una pagina che interroga a intervalli non vedrebbe mai in tempo. Era il
  vincolo che bloccava l'intera fase `0.4.0`: una regola come «se la porta si
  apre dopo le 23, accendi l'ingresso» non e' scrivibile senza sapere
  **quando** le cose accadono.
- Gli stati stanno in memoria. Il riassunto della casa dato al modello
  costava una chiamata di rete a ogni frase detta all'assistente, e quel
  ritardo si sentiva; adesso la rete si interroga solo quando la cache e'
  vuota. Anche «Scopri dispositivi» diventa immediato.
- La mappa dispositivi mostra lo stato di ogni alias e lo aggiorna da sola.
- Riconnessione con attesa che raddoppia fino a un minuto. Un token rifiutato
  invece ferma i tentativi: riprovare con lo stesso token non porta da
  nessuna parte, e insistere per ore riempirebbe il log senza avvicinare la
  soluzione.

### Modificato
- `services/eventi_casa.py` decide *se* ascoltare, `infra` sa solo *come*.
  La separazione l'ha imposta il test sulle regole di dipendenza fra livelli,
  che ha bocciato la prima versione: `api/app.py` chiamava direttamente
  l'infrastruttura. Il cricchetto ha fatto il suo mestiere al primo giro
  utile.

---

## [0.2.0] - 2026-09-08 — Fondamenta

### Aggiunto
- **I ruoli e i dispositivi fidati si gestiscono dalla dashboard**, nella
  scheda «Gestione Utenti». Le rotte esistevano dalla `0.2.0` e i permessi
  erano gia' applicati — la casa era protetta — ma per cambiare un ruolo
  bisognava chiamare l'API a mano. Adesso i permessi di ogni ruolo sono
  caselle da spuntare, i ruoli propri («Collaboratrice domestica», «Nonno»,
  «Ospite fine settimana») si creano dalla pagina, e i predefiniti si
  modificano ma non si cancellano.
- **Il ruolo di un profilo adesso si sceglie.** Veniva dedotto al
  salvataggio da avatar e fascia d'eta', e la fascia «ragazzo» finiva nel
  ramo degli adulti: un tredicenne riceveva il ruolo `adult`, cioe'
  serrature e allarme. Nel modulo del profilo il ruolo e' un campo suo, e la
  fascia d'eta' torna a fare l'unica cosa che ha sempre fatto — cambiare il
  tono delle risposte. Erano due cose diverse presentate come una sola.
- **Elenco dei dispositivi fidati** con nome, proprietario, ultimo accesso e
  indirizzo; revoca singola e «revoca tutti» per il telefono perso, che
  risparmia il dispositivo da cui la si chiede. Ogni riga dice se e' quella
  da cui si sta guardando: senza, l'elenco e' una fila di nomi identici e
  revocare il proprio e' l'errore piu' facile da fare.
- Il pulsante **«Blocca»** nella barra in alto. `checkAuthStatus` lo cercava
  a ogni caricamento della pagina fin dalla `0.1.0`, ma nessuno l'aveva mai
  messo nel markup: la funzione c'era, il modo di chiamarla no, e l'unico
  blocco possibile era quello automatico per inattivita'. Su un tablet di
  casa con un PIN per persona, potersi togliere di mezzo e' il minimo.
- `/api/auth/status` dice anche **quali permessi ha chi sta guardando**, cosi'
  la pagina puo' nascondere cio' che non porta da nessuna parte. Non e' una
  protezione — a rifiutare e' sempre il server, rotta per rotta — ma un
  pannello che risponde sempre 403 fa sembrare rotta l'applicazione.
- Test sulla dashboard, che finora non ne aveva nessuno: la sintassi degli
  script inline (`node --check`), ogni identificativo cercato da
  `getElementById`, e ogni indirizzo chiamato con `fetch` confrontato con le
  rotte che l'applicazione espone davvero.
- **La versione si legge dalla dashboard**, accanto al nome. Un server di
  casa si aggiorna ogni tanto e si riavvia da solo: a distanza di settimane
  non c'e' modo di ricordare se ha preso l'ultimo aggiornamento o si e'
  fermato due mesi fa, e la domanda merita una risposta guardando la pagina
  invece di entrare in SSH.
- Accanto al numero c'e' il commit — `0.2.0.dev0+489c072` — perche' il
  numero da solo mente: fra un tag e il successivo passano decine di commit,
  e un server aggiornato su `main` mostrerebbe la versione del tag
  precedente pur avendo tutt'altro codice. Su una release taggata compare
  solo il tag. Il suggerimento del badge porta anche ramo e commit per
  esteso, e `/api/status` restituisce tutto.
- La versione del progetto passa a `0.2.0.dev0`: `main` non e' piu' la
  `0.1.0` e non e' ancora la `0.2.0`, ed e' onesto che lo dica.

### Sicurezza
- La versione **non** compare nella pagina di accesso: e' la prima
  informazione utile a chi cerca una vulnerabilita' nota, ed e' inutile a
  chi deve solo digitare il PIN.

### Corretto
- **`deploy.sh --dry-run` rispondeva sempre «gia' aggiornato».** Il `fetch`
  passava da `esegui`, la funzione che durante una simulazione stampa invece
  di eseguire. Ma un fetch non tocca la copia di lavoro: aggiorna solo i
  riferimenti remoti. Saltandolo, lo script confrontava HEAD con se stesso e
  annunciava che non c'era niente da fare mentre sul server mancavano tre
  versioni. Una prova che risponde sempre allo stesso modo non e' una prova,
  ed e' peggio di non averla: fa sembrare informata una decisione presa alla
  cieca.
- `tests/unit/test_deploy.py`: lo script che aggiorna il server non era
  guardato da niente, ed e' gia' costato due aggiornamenti interrotti a
  meta'. Adesso si controlla che sia bash valido — un errore di sintassi si
  scoprirebbe a servizio gia' fermo, perche' bash legge gli script mentre li
  esegue — che nessuna lettura di git passi da `esegui`, e che la
  simulazione esca prima del controllo di salute, che sa riportare da solo
  il server alla versione precedente.
- **I riferimenti alle issue nel codice puntavano nel posto sbagliato.** Le
  schede del backlog diventano issue su GitHub, e il numero lo assegna
  GitHub: finora l'unico riferimento era il numero nel nome del file, che
  pero' e' solo un ordinamento e coincideva per caso. Tre schede scritte dopo
  la prima importazione hanno ricevuto i numeri 46, 47 e 48 pur chiamandosi
  `19-`, `20-` e `34-`. I numeri 19 e 20 erano gia' altre due issue della
  `v0.3.0` — il WebSocket verso Home Assistant e i tool per serrature, media
  player e aspirapolvere — e due commit che scrivevano `Closes #19` e
  `Closes #20` intendendo le schede le hanno chiuse come completate. Sono
  rimaste chiuse per giorni, con la milestone `v0.2.0` che sembrava indietro
  e la `v0.3.0` che sembrava avviata. Le due issue sono state riaperte, i
  riferimenti nel codice corretti, e adesso il numero sta nell'intestazione
  della scheda: `import_backlog.py` ce lo scrive da solo, e
  `tests/unit/test_backlog.py` fallisce se torna a divergere.
- Le date dei dispositivi fidati dichiarano il fuso. Uscivano nude
  (`2026-09-08T20:15:00`) e il browser le leggeva come ora locale: d'estate,
  due ore di scarto sull'«ultimo accesso» di ogni telefono.
- Salvare un profilo o cancellarlo mostra il motivo del rifiuto invece di
  fallire in silenzio. Declassare l'ultimo amministratore e' l'errore che
  chiude fuori di casa: il server lo rifiuta e spiega perche', ma la pagina
  buttava via la risposta e il salvataggio sembrava riuscito.
- `data/*.db-journal` finisce fra i file ignorati. SQLite ci ricade quando
  il filesystem non regge il WAL — una cartella sincronizzata, una
  condivisione di rete — e quel file comparso dal nulla sarebbe finito
  dritto in un commit.
- **L'aggiornamento si fermava al primo tentativo, dopo il backup.** La
  pulizia dei backup vecchi usava `ls` su un modello che al primo
  aggiornamento non trova niente — l'istantanea del database non esiste
  ancora — e `ls` esce con errore: con `set -o pipefail` quell'errore
  fermava tutto. Cioe' falliva esattamente la prima volta, che e' l'unica in
  cui non puo' permetterselo. Ora la pulizia passa da una funzione che regge
  il caso vuoto, provata su quattro casi compreso quello.

### Corretto
- **`scripts/deploy.sh` non si aggiorna piu' sotto i piedi.** Bash legge uno
  script mentre lo esegue, tenendo il segno con una posizione nel file: al
  passo che aggiorna il codice — compreso lo script stesso — quella
  posizione finiva a indicare righe di un file diverso, e l'esecuzione
  proseguiva su testo che non c'entrava piu' niente, nel mezzo di un
  aggiornamento. Fra la v0.1.0 e la v0.2.0 quel file e' cresciuto di ottanta
  righe. Ora si copia da parte in /tmp e riparte dalla copia. Dimostrato con
  una prova: senza la protezione, una riga aggiunta al file a meta'
  esecuzione viene eseguita davvero.
- **Quando non c'e' un tag nuovo, lo script lo dice.** Senza argomenti
  distribuisce l'ultimo tag di release — un server di casa non deve seguire
  il ramo di sviluppo — ma se `main` e' avanti e nessuno lo dice, sembra che
  l'aggiornamento non funzioni. Ora indica quanti commit ci sono e come
  installarli.

### Aggiunto
- **Copertura all'80% e controlli obbligatori** (issue #18). La v0.2.0 ha
  riscritto persistenza, memoria e struttura: senza rete di sicurezza
  sarebbe stata una riscrittura al buio.
- Trentacinque test nuovi sui due moduli che erano quasi scoperti, e non a
  caso i due che contano di piu': `core/tools/ha_tools.py` dal 13% al 55% —
  e' quello che accende le luci, cambia la temperatura e apre le tapparelle —
  e l'adattatore Alexa dal 14% al 91%, l'unica porta affacciata su Internet.
- La CI ora **fallisce** se la copertura scende sotto il 70%, se mypy trova
  un errore in `config/` o `core/`, o se i ganci pre-commit non passano.

### Corretto
- **La CI e i ganci pre-commit usavano due versioni diverse di black.** I
  ganci fissavano `24.8.0`, la CI installava l'ultima disponibile: lo stesso
  file risultava formattato bene per una parte e da riformattare per
  l'altra. Il disallineamento era li' da mesi e nessuno poteva accorgersene,
  perche' i ganci non giravano in CI. Ora le versioni sono fissate in
  entrambi i posti e un test fallisce se tornano a divergere.
- I controlli dei ganci pre-commit sono anche test della suite: a capo
  finale, spazi in coda, file troppo grandi, chiavi private. I ganci veri
  hanno bisogno di scaricare i propri repository e non si possono eseguire
  ovunque; il loro effetto ora si verifica dove gira sempre tutto.
- Dodici errori di tipo in `core/` e `config/`, fra cui due dizionari di
  parametri per Home Assistant il cui tipo veniva dedotto dalla prima chiave
  e non ammetteva i numeri che ci finivano dopo.

### Aggiunto
- **`test_tools.py` diventa test veri** (issue #10, l'ultimo punto rimasto
  aperto della `0.1.0`). Era uno script di `print` nella radice del progetto:
  chiamava Open-Meteo, Wikipedia e i feed ANSA e stampava cio' che tornava,
  senza una sola asserzione. Ora sono due cose distinte: i test che
  chiamano davvero quei servizi stanno in `tests/integration/`, marcati
  `network` ed esclusi dalla CI (`pytest -m network` per eseguirli a mano), e
  dieci test in `tests/unit/` che verificano **il nostro codice** con le
  risposte simulate — compreso cosa succede quando un servizio risponde 403,
  cambia forma o restituisce un feed vuoto. E' la parte che si rompe
  davvero, ed e' l'unica che si puo' verificare a ogni commit.
- **Dispositivi fidati: il telefono non chiede il PIN ogni volta** (issue
  #47, ADR 0004). Un PIN per persona rende i permessi reali, ma su un
  telefono diventa un fastidio quotidiano — e una protezione fastidiosa
  viene disattivata: a quel punto la casa e' aperta come prima, con in piu'
  l'illusione di essere protetta.
- Al primo accesso compare «ricorda questo dispositivo». La credenziale sta
  in un cookie `HttpOnly` che JavaScript non puo' leggere, vale trenta giorni
  e si rinnova a ogni uso: un telefono usato tutti i giorni non chiede mai il
  PIN, uno lasciato in un cassetto per un mese lo richiede.
- **Nel database si conserva solo l'impronta della credenziale**, come per i
  PIN: se un giorno finisse dove non deve, quelle righe non aprirebbero
  nessuna casa.
- Revoca singola, «revoca tutti» per il telefono perso (risparmiando quello
  da cui si chiede), revoca automatica quando si cancella un profilo, e
  revoca degli altri dispositivi quando si cambia il PIN — altrimenti un
  telefono ancora fidato renderebbe inutile il cambio.
- **Un dispositivo fidato identifica, non promuove**: il telefono di un
  ragazzo resta il telefono di un ragazzo.
- **Ruoli e permessi per ogni persona di casa** (issue #46, ADR 0004). Fino a
  ieri il profilo distingueva adulto, ragazzo e bambino, ma quella distinzione
  cambiava **solo il tono delle risposte**: un bambino poteva comandare
  qualunque cosa.
- Cinque ruoli predefiniti — Amministratore, Adulto, Ragazzo, Bambino,
  Ospite — con identificativi che coincidono con i valori gia' presenti nei
  profili: chi aggiorna si ritrova gia' assegnato, senza fare niente. Sono
  modificabili, e se ne possono creare altri («Collaboratrice domestica»,
  «Nonno», «Ospite fine settimana») dalle rotte `/api/ruoli`.
- **`sicurezza.comanda` e' un permesso a parte**: serrature e allarme non
  sono lampadine, e chi puo' accendere una luce non deve per questo poter
  aprire la porta di casa.
- Il controllo sta in `HomeAssistantClient.call_service`, dove passa ogni
  azione — comandi diretti, scenari e le azioni dentro una routine. E' cosi'
  che **una routine si esegue con i permessi di chi la invoca**, non di chi
  l'ha scritta: altrimenti per aggirare il controllo basterebbe scriversi
  una routine.
- Un rifiuto viene spiegato («non hai il permesso di aprire la serratura»)
  invece di essere un 403 muto, e finisce nel registro delle azioni.
- **L'ultimo amministratore non si cancella e non si declassa.** E' il genere
  di errore che si fa una volta sola, di sera, e si paga il giorno dopo.

### Corretto
- **«Acceso» non viene piu' detto quando il comando non e' arrivato.** Il
  percorso rapido annunciava il successo senza guardare l'esito: peggio che
  tacere, perche' chi ascolta se ne va convinto che la luce sia accesa.


### Corretto
- **«Che temperatura c'è in salotto» legge il sensore, non le previsioni**
  (issue #17). Il percorso rapido scattava sulla sola parola «temperatura» e
  interrogava Open-Meteo: alla domanda sulla stanza si rispondeva con la
  temperatura esterna della citta'. Sbagliata, e detta con sicurezza. Nuovo
  tool `get_indoor_temperature`, e se un sensore non c'e' l'assistente lo
  dice invece di ripiegare sul meteo.
- **I nomi di citta' composti non si spezzano piu'.** L'espressione
  catturava una parola sola: «Reggio Emilia» diventava «Reggio». E al posto
  della lista di parole da escludere scritta a mano, una citta' che la
  geocodifica non riconosce fa ripiegare sulla predefinita.
- Il parser capisce i numeri detti a voce («un minuto», «venticinque
  minuti», «mezz'ora») e l'ora tonda senza minuti («alle 18»), che e' come
  si parla davvero. Cadono gli ultimi due xfail del parser.

### Modificato
- **Il codice sta sotto `src/shinra/`**, diviso nei livelli dichiarati da
  `docs/ARCHITECTURE.md`: `config`, `domain`, `infra`, `services`, `skills`,
  `channels`, `api`. Le cartelle di primo livello spariscono — `core/`,
  `server/`, `config/`, `integrations/` — e con loro il rischio che un
  `import config` risolvesse sulla directory di lavoro invece che sul
  progetto: `config` e' un nome che hanno in molti. Sotto `src/` il pacchetto
  si raggiunge solo se installato, quindi i test provano cio' che si
  installa davvero.
- **La regola di dipendenza fra i livelli adesso si verifica.** Era scritta
  in `ARCHITECTURE.md` dalla `0.1.0` e nessuno poteva farla rispettare,
  perche' i livelli non esistevano come cartelle. `tests/unit/test_architettura.py`
  la controlla a ogni esecuzione della suite. Le diciannove violazioni
  ereditate sono elencate li' una per una con il loro motivo: una nuova fa
  fallire i test, e una riparata fa fallire anche lei finche' non si toglie
  dall'elenco. Il debito e' scritto e puo' solo accorciarsi.
- **La radice del progetto si calcola in un posto solo** (`shinra/percorsi.py`),
  invece che in nove moduli ognuno con la sua catena di `.parent`. Sbagliare
  quella catena non solleva niente: la cartella dei dati punta altrove, il
  `mkdir` che segue la crea, e il servizio riparte con un database vuoto —
  nessun errore, solo la casa che ha dimenticato tutto. Era la premessa
  necessaria allo spostamento, che cambia la profondita' di ogni modulo.
- Il servizio si avvia con il comando `shinra`, installato dal pacchetto.
  `run.py` resta come alias, perche' e' da li' che parte `shinra.service` e
  cambiare anche quello avrebbe reso lo spostamento un aggiornamento che non
  riparte.
- `scripts/deploy.sh` rimuove `core/`, `server/` e `integrations/` dal server
  dopo l'aggiornamento. Git le lascia indietro perche' dentro resta il
  `__pycache__`, che non e' tracciato, e un `.pyc` di un modulo che non
  esiste piu' e' il genere di cosa che un giorno spiega un errore assurdo.
  Le cancella solo se git non ci tiene piu' niente.
- **`process_user_input` da 250 righe a un instradamento** (issue #17). Ogni
  intento — apprendimento, timer, modalita', dispositivi, temperatura
  interna, meteo, notizie, enciclopedia — e' un oggetto in `core/intenti/`
  con la sua priorita' e i suoi test. Aggiungerne uno vuol dire scrivere una
  classe e registrarla: l'agente non si tocca. `core/agent.py` passa da 530
  a 260 righe.
- Il riepilogo della casa si chiede solo quando la richiesta arriva al
  modello: prima veniva chiesto a Home Assistant per ogni frase, anche per
  «accendi la luce della cucina» che si risolve senza.

### Aggiunto
- **Registro delle azioni: chi ha fatto cosa in casa, e com'e' andata**
  (issue #15). Shinra comanda luci, prese e clima — e presto serrature e
  allarme — e finora non restava traccia di niente: alla domanda «chi ha
  spento il riscaldamento alle tre di notte?» non c'era risposta.
- Ogni esecuzione di tool, ogni attivazione di modalita', ogni accesso
  riuscito, rifiutato o bloccato e ogni modifica alle impostazioni lascia una
  voce con momento, persona, canale, parametri, esito e durata. L'aggancio e'
  in `execute_tool`, il passaggio obbligato di ogni azione: un tool nuovo
  risulta tracciato senza che nessuno se ne debba ricordare.
- Identificativo di correlazione che segue la richiesta fino ai tool e torna
  al client nell'intestazione `X-Correlazione`: «accendi le luci di sotto»
  produce tre comandi, e senza un filo comune sembrerebbero tre eventi
  scollegati avvenuti nello stesso secondo.
- `GET /api/registro` con filtri, **riservato agli amministratori**. Non e'
  formalita': quelle righe dicono a che ora qualcuno rientra e quando esce.
- **I segreti non entrano mai nel registro**: i campi il cui nome contiene
  token, pin, password, secret o authorization sono sostituiti con `***`,
  a qualsiasi profondita'. Un accesso rifiutato registra quale profilo e'
  stato tentato, mai il PIN provato.
- Log applicativo in JSON con rotazione in `data/log/`, che porta con se' la
  stessa correlazione: dal registro si passa al log e viceversa.
- Conservazione configurabile (`registro.retention_days`, novanta giorni per
  difetto; zero significa conservare tutto), con pulizia giornaliera affidata
  allo scheduler.

### Corretto
- **La configurazione non si rilegge piu' dal disco a ogni domanda**
  (issue #14, REL-06). `base_url`, `model`, `timeout` di Ollama e `token`,
  `headers` di Home Assistant aprivano e analizzavano `config.yaml` **dentro
  la property**, quindi dentro l'event loop asincrono. Misurato: cinque
  letture per una sola chiamata al modello piu' un riepilogo della casa, e il
  ciclo dei tool di un turno puo' ripeterle quattro volte. Ora zero. Le
  impostazioni salvate restano immediate, perche' esiste un solo oggetto
  condiviso aggiornato al suo posto — non una cache da invalidare.
- **Ogni persona ha la sua conversazione** (issue #13, REL-03). C'era
  un'unica memoria globale: la chat del salotto, quella del telefono e ogni
  richiesta ad Alexa scrivevano nella stessa cronologia, quindi il contesto
  di un adulto finiva nella sessione di un bambino e due persone che
  parlavano insieme si confondevano a vicenda. Il parametro `session_memory`
  esisteva gia': non lo passava nessuno.
- **L'assistente ricorda cosa ha appena fatto.** `add_tool_interaction()`
  aveva corpo `pass`, quindi le azioni eseguite non entravano nel contesto:
  «accendi la luce della cucina» seguito da «spegnila» non poteva
  funzionare, perche' quale luce non era scritto da nessuna parte.
- Le conversazioni ferme da mezz'ora vengono liberate, e oltre le cinquanta
  esce quella inattiva da piu' tempo: gli ospiti non registrati creano un
  profilo ciascuno, e un processo che gira per mesi non deve crescere senza
  motivo.

### Aggiunto
- **Un database al posto di sette file JSON** (issue #12, prima parte).
  `data/shinra.db`, SQLite in modalita' WAL, con SQLAlchemy 2 e Alembic per
  le migrazioni di schema. I file JSON restano intatti: sono il backup con
  cui tornare indietro.
- `scripts/migra_da_json.py`: migrazione una tantum che **non tocca gli
  originali**, verifica per conteggio entita' per entita' e si rifiuta di
  scrivere sopra un database gia' popolato.
- `scripts/deploy.sh` fa un'istantanea coerente del database prima di ogni
  aggiornamento, con l'API di backup di SQLite e non con `tar`: copiare un
  database in uso a colpi di archivio produce un file che sembra valido e
  non lo e'. Se l'istantanea non riesce, l'aggiornamento si ferma.
- La tabella `registro_azioni` nasce gia' nello schema iniziale, vuota, per
  la issue #15: crearla dopo sarebbe una seconda migrazione sul database di
  una casa in funzione.
- **I promemoria suonano davvero** (issue #11). Fino alla `0.1.0` un
  promemoria veniva scritto in `data/reminders.json` e nessun processo lo
  rileggeva: non si attivava in nessuna circostanza, mentre l'assistente
  aveva gia' risposto «ti ricordero'». I timer stavano poco meglio — il
  conto alla rovescia viveva in un `setInterval` del browser, quindi
  chiusa la scheda non suonava nulla.
- `core/scheduler.py`: scheduler persistente (APScheduler con archivio
  SQLite in `data/scheduler.db`). **Persistente** significa che un
  promemoria per le 17:30 scatta anche se il servizio e' stato riavviato
  alle 17:00.
- Tolleranze distinte per il recupero dei job persi durante un fermo: mezz'ora
  per i promemoria — «prendi le medicine» resta utile in ritardo — e un
  minuto per i timer, perche' la pasta e' andata comunque.
- `core/eventi.py`: bus interno. Chi produce un fatto non sa chi lo
  consegnera'; un canale che fallisce non zittisce gli altri. Le notifiche
  push (issue #29) si aggiungeranno come canale in piu', senza toccare lo
  scheduler.
- `core/consegna.py`: canale di annuncio su Echo. Collega finalmente
  `speak_on_alexa()`, definita in `ha_client.py` e mai chiamata da nessuno:
  l'assistente ora puo' parlare in casa di sua iniziativa, non solo
  rispondere.
- `GET /ws/eventi`: gli avvisi raggiungono la dashboard nell'istante in cui
  accadono. Verifica la sessione prima di accettare la connessione.
- La dashboard mostra i promemoria in attesa accanto ai timer, con lo stato
  del collegamento agli eventi.
- `TimerEngine.ripristina_job()`, eseguita all'avvio: chi aggiorna da una
  versione senza scheduler ha timer e promemoria in attesa e nessun job
  corrispondente.
- `TimerEngine.pulisci_scaduti()`: i timer completati non si accumulano piu'
  all'infinito in `timers.json`.

### Corretto
- **`pip install -r requirements.txt` installa di nuovo un sistema che parte.**
  Le dipendenze erano dichiarate in due elenchi separati e il secondo era
  rimasto indietro: mancavano `cryptography`, `apscheduler`, `sqlalchemy` e
  `pydantic-settings`. Chi seguiva il README otteneva un'installazione che
  si fermava all'avvio. Ora `requirements.txt` rimanda a `pyproject.toml`,
  che e' l'unica fonte, e un test impedisce che i due elenchi si separino
  di nuovo.
- **Le impostazioni salvate arrivano a tutti i moduli senza riavviare.**
  `reload_settings()` sostituiva l'oggetto di configurazione invece di
  aggiornarlo: i sei moduli che avevano scritto
  `from config.settings import settings` — fra cui `server/sicurezza.py` —
  restavano legati alla vecchia istanza e continuavano a leggere i valori di
  prima fino al riavvio del servizio. Stessa forma di REL-04 (issue #9), in
  un altro punto del codice. Scoperto dal test end-to-end sul WebSocket, che
  falliva su una copia pulita del repository e non su quella di lavoro.

### Modificato
- **`DataStore`, `UserManager` e `TimerEngine` leggono e scrivono nel
  database** (issue #12, seconda parte). I nomi dei metodi e la forma di cio'
  che restituiscono non cambiano: cambia dove stanno i dati.
- La migrazione avviene **da sola al primo avvio**, se il database e' vuoto e
  i file JSON ci sono. Un database gia' popolato non viene mai toccato,
  quindi un riavvio non riporta indietro cio' che era stato cancellato.
- Le rotte di conoscenza, fonti, alias e modalita' scrivono **una riga alla
  volta** invece di riscrivere l'intero elenco. Sparisce con loro un difetto
  che nessuno aveva notato: gli identificativi erano `k_{numero di voci + 1}`,
  quindi dopo una cancellazione il conteggio tornava su un numero gia' usato
  e il salvataggio successivo sovrascriveva un altro record. In silenzio.
- `scripts/esporta_json.py`: il JSON resta il formato di backup — si apre con
  un editor anche fra dieci anni, senza avere Shinra installato.
- I test girano su un database temporaneo, mai su quello di casa.
- Il conto alla rovescia nel browser e' ora solo estetico: chi decide che un
  timer e' scaduto e' il server. Se il collegamento agli eventi manca, la
  scheda torna a suonare da sola — meglio un avviso locale che nessuno.
- Nuove dipendenze: `apscheduler>=3.10`, `sqlalchemy>=2.0`.
- I job della CI hanno un tetto di 10 minuti.

---

## [0.1.0] - 2026-09-04 — Impianto chiuso

### Corretto
- **Cambiare l'indirizzo di Home Assistant ha effetto senza riavviare**
  (issue #9, REL-04). `core/tools/ha_tools.py` costruiva il proprio client
  passando URL e token come valori al momento dell'import, congelandoli: chi
  correggeva l'indirizzo dalle impostazioni vedeva il pannello diagnostico
  diventare verde — quello usa un client dinamico — mentre i comandi ai
  dispositivi continuavano a fallire contro il vecchio indirizzo.
- Un solo client condiviso al posto di quattro, con la connessione riusata
  invece di aprirne una nuova a ogni chiamata, e chiusa allo spegnimento.
- **La Modalita' Apprendimento arriva in fondo** (issue #1 e #2, BLK-01 e
  BLK-02). Era la funzione piu' recente del progetto e non aveva mai
  completato un passo: `interview_engine` chiamava `add_knowledge_item` su
  `DataStore` e `generate` su `OllamaClient`, due metodi che non esistevano.
  Il primo produceva un HTTP 500 a ogni risposta; il secondo, catturato,
  faceva cadere sempre nel ripiego, rendendo codice morto il prompt di
  estrazione dei fatti.
- `DataStore.add_knowledge_item()` con identificativi casuali — quelli basati
  sul conteggio si ripetevano dopo una cancellazione — e senza duplicati:
  durante un'intervista capita di ripetersi, e ogni fatto finisce nel prompt
  di ogni risposta.
- `OllamaClient.genera_json()`, che chiede al modello `format: "json"` e
  regge cio' che un modello piccolo restituisce davvero: JSON avvolto in un
  blocco di codice, preceduto da una frase, o con stringhe al posto di
  oggetti. Le risposte inutilizzabili non fanno cadere l'intervista.
- Un fatto che non si riesce a salvare non interrompe piu' l'intervista.
- **Il prefisso di invocazione Alexa si ricava dalla configurazione.** Prima
  era un elenco scritto nel codice che conosceva solo `kyra`: rinominando la
  skill in «hey kyra» restava appeso un «hey» davanti a ogni comando, e «hey
  accendi la luce» non corrisponde a nessuna frase riconosciuta.

### Sicurezza
- **La dashboard non viene piu' servita a chi non e' entrato** (issue #5,
  SEC-03). La schermata di blocco era un rettangolo disegnato sopra un markup
  gia' arrivato al browser: bastava chiudere l'overlay dagli strumenti
  sviluppatore, o disattivare JavaScript. Ora `GET /` decide sul server e
  serve una pagina di accesso autonoma, senza risorse ne' dati della casa.
- **`X-Forwarded-For` viene letto solo dai proxy dichiarati fidati** (issue #6,
  SEC-04). Fidarsene sempre permetterebbe di azzerare il contatore dei
  tentativi cambiando un valore; non fidarsene mai, dietro reverse proxy,
  faceva si' che il quinto tentativo sbagliato di uno sconosciuto bloccasse il
  proprietario di casa. Si configura in `security.trusted_proxies`.
- I token di sessione sono firmati con `session_secret`, che era dichiarato in
  configurazione e non usato da nessuna riga.
- Intestazioni di sicurezza su ogni risposta: `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- Un errore imprevisto non racconta piu' com'e' fatto il server: la traccia
  resta nel log, al client arriva un messaggio generico.
- **`restricted_topics` viene finalmente applicato** (issue #8). Il campo
  esisteva da sempre e non era letto: il profilo «bambino» cambiava solo il
  tono delle risposte. Il controllo precede il fast-path, altrimenti una
  richiesta vietata potrebbe accendere una luce prima di essere rifiutata.
  E' un limite dichiarato, non un controllo parentale: confronta parole,
  quindi si aggira riformulando, e i ruoli veri sono la issue #46.
- **Un PIN in chiaro rimasto da una versione precedente non chiude piu' fuori
  la famiglia.** `_prepara_accesso` si fermava se un profilo aveva un `pin`
  qualsiasi: con un valore non cifrato, l'autenticazione risultava attiva,
  nessun PIN nuovo veniva generato, e quel valore non poteva essere
  riconosciuto perche' il confronto si aspetta un hash. Nessuno riusciva piu'
  a entrare. Ora i PIN in chiaro vengono cifrati all'avvio conservando il
  valore, e solo un PIN in formato valido conta come «qualcuno puo' accedere».
- `scripts/imposta_pin.py`: elenca i profili e reimposta un PIN da riga di
  comando, per quando il messaggio del primo accesso e' scorso via dal log.
- **La casa non risponde piu' a chi non si e' identificato** (issue #3, SEC-01).
  Prima la protezione era un controllo manuale presente su **un endpoint su
  trentanove**: chiunque fosse sulla rete di casa comandava l'impianto e
  leggeva l'anagrafica della famiglia con una `curl`. Ora e' una dipendenza
  applicata all'intero router: un endpoint nuovo nasce chiuso, e per aprirlo
  bisogna dichiararlo in `ROTTE_PUBBLICHE` scrivendo perche'.
- **Un PIN per persona, non uno per la casa** ([ADR 0004](docs/adr/0004-identita-ruoli-e-permessi.md)).
  All'accesso si sceglie chi si e' e si digita il proprio PIN; la sessione
  porta con se' l'identita' reale, non una scelta da menu a tendina. E' il
  fondamento su cui poggeranno i permessi della `v0.2.0`.
- PIN salvati come hash PBKDF2-SHA256 con sale casuale: `users.json` non
  contiene piu' nulla che apra la porta.
- Sessione in un cookie `HttpOnly`, non leggibile da JavaScript, valida 30
  giorni. Cambiare un PIN chiude le sessioni aperte con quello vecchio.
- Autenticazione **attiva per difetto**. Al primo avvio senza alcun PIN ne
  viene generato uno per l'amministratore e scritto nel log una volta sola:
  un hub che si rifiuta di partire lascerebbe una casa senza controllo.
- `GET /health` pubblico e privo di informazioni, per la sonda di
  `scripts/deploy.sh`; `/api/status` ora richiede una sessione perche' rivela
  modelli e indirizzo di Home Assistant.
- Le operazioni distruttive — cancellare un utente, cambiare la configurazione
  — richiedono il ruolo amministratore. Provvisorio: i ruoli veri sono la
  issue #46 della `v0.2.0`.
- **I segreti non stanno piu' nel repository** (issue #07, SEC-05).
  `config/config.yaml`, `data/users.json`, `data/knowledge.json` e gli altri
  file di stato non sono piu' tracciati da git. Token di Home Assistant, PIN
  amministratore e segreto di sessione si leggono dall'ambiente o da `.env`,
  con precedenza `ambiente > .env > config.yaml`.
- `save_config()` non puo' piu' scrivere un segreto nel file di
  configurazione: e' l'invariante che impediva a un `git commit -a` di
  pubblicare le credenziali di casa.
- Rimosso il segreto di sessione predefinito `shinra-secret-key-salt`, uguale
  per ogni installazione. Ne viene generato uno per installazione al primo
  avvio e scritto in `.env` con permessi `600`.
- I segreti rimasti in `config.yaml` da versioni precedenti vengono spostati
  in `.env` al primo avvio e cancellati da li'. La migrazione e' idempotente.
- Controlli d'avvio: token mancante con Home Assistant attivo, PIN mancante con
  autenticazione attiva, `debug` esposto in rete, skill Alexa senza `skill_id`.
  Vengono segnalati nel log e non impediscono l'avvio — un hub domotico che si
  rifiuta di partire lascia una casa senza controllo.
- Il controllo dei segreti in CI accetta una dichiarazione esplicita per i
  valori deliberatamente finti: `# pragma: allowlist secret` sulla stessa riga.
  Serviva perche' il token di prova nei test — che ha la forma di un JWT
  proprio per somigliare al caso reale — faceva scattare il controllo. La
  dichiarazione e' visibile in revisione; escludere intere cartelle no, e un
  segreto vero puo' finire in un test tanto quanto altrove.
- La configurazione illeggibile non viene piu' ignorata in silenzio: prima un
  file corrotto faceva ripartire dai valori predefiniti senza alcun segnale.

### Aggiunto
- [ADR 0004](docs/adr/0004-identita-ruoli-e-permessi.md): un PIN per persona al
  posto di uno per la casa, ruoli personalizzati invece di flag fissi, e
  dispositivi fidati per non chiedere il PIN a ogni accesso. Passkey e
  riconoscimento di chi parla rimandati alla `v0.4.0`, con il limite
  dichiarato: fino ad allora il canale vocale non distingue chi parla, quindi
  serrature e allarme restano fuori dalla voce.
- Tre issue nuove nel backlog: ruoli e permessi, dispositivi fidati (v0.2.0),
  passkey e voce riconosciuta (v0.4.0). La issue #3 acquisisce l'identita' per
  persona e la sessione di 30 giorni.
- `data/examples/` con i valori iniziali versionati. Al primo avvio ogni file
  mancante in `data/` viene creato copiando il proprio esempio, cosi'
  un'installazione nuova parte pronta e una esistente non viene toccata.
- Impianto di progetto: `pyproject.toml` con dipendenze, dipendenze di
  sviluppo e configurazione di ruff, black, pytest, coverage e mypy.
- Documenti di governance: `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`,
  `CONTRIBUTING.md`, `SECURITY.md`, questo changelog.
- Registro delle decisioni architetturali in `docs/adr/`.
- Backlog completo delle cinque milestone in `docs/backlog/`.
- Integrazione continua GitHub Actions: lint, formattazione, type check e test.
- Template per issue e pull request.
- Suite di test iniziale, con i test di regressione dei difetti bloccanti
  marcati `xfail(strict=True)` finche' non vengono corretti.
- `.env.example` per la migrazione dei segreti fuori dal file di configurazione.
- `scripts/deploy.sh`: aggiornamento del server Debian con backup, distribuzione
  per tag di release, verifica di salute e ritorno automatico alla versione
  precedente se il servizio non risponde.
- `deploy/shinra.service`: unita' systemd irrobustita, con utente dedicato al
  posto di root, segreti da `.env` e filesystem in sola lettura.
- `docs/DEPLOY.md`, che include la messa in sicurezza da eseguire sul server
  **prima** di unire la issue #07: quel commit rimuove `config/config.yaml`
  dall'indice, e il primo `git pull` successivo lo cancellerebbe dal server
  insieme al token di Home Assistant.

### Modificato
- Formattato l'intero codice Python con black (26 file). Il commit e' puramente
  meccanico: nessun cambiamento di comportamento. Elencato in
  `.git-blame-ignore-revs` perche' non sporchi `git blame`.
- Ridotto l'insieme di regole ruff a quello che il codice esistente puo'
  sostenere. Le regole di modernizzazione (`UP`, 186 rilievi) vengono attivate
  durante il riordino della v0.2.0: una regola che nessuno riesce a soddisfare
  viene solo disattivata.
- `.gitignore` ora esclude `config/config.yaml` e i file di stato con dati
  personali. **Attenzione**: `config/config.yaml` risulta ancora tracciato da
  git; la rimozione dall'indice fa parte della v0.1.0.

---

## Versioni pianificate

| Versione | Nome | Obiettivo |
| :--- | :--- | :--- |
| `0.1.0` | Impianto chiuso | Difetti bloccanti risolti, superficie di attacco chiusa, segreti fuori da git |
| `0.2.0` | Fondamenta | Scheduler persistente, database, memoria per sessione, layout a pacchetto, test |
| `0.3.0` | Copertura | Eventi Home Assistant in tempo reale e i domini oggi scoperti |
| `0.4.0` | Proattivita' | Motore di regole, notifiche push, voce interamente locale |
| `0.5.0` | Prodotto | Frontend modulare, backup, internazionalizzazione, distribuzione |
| `1.0.0` | Stabile | Criteri di uscita in `docs/ROADMAP.md` soddisfatti |

Le sette funzioni complementari (consulente energetico, check-in presenza,
registro di casa, briefing per profilo, spiegabilita', contesto cucina, diario
della casa) sono programmate **dopo** la `1.0.0`.
