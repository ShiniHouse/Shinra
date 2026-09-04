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
  quindi si aggira riformulando, e i ruoli veri sono la issue #19.
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
  issue #19 della `v0.2.0`.
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
