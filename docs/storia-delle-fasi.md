# Storia delle fasi 0.1.0 – 0.6.0

Le schede di lavoro delle sei fasi chiuse, in un solo documento. Ogni scheda è stata una
issue su GitHub (il numero è nel titolo) e un file in `docs/backlog/`; a fase chiusa i file
sono stati uniti qui, perché non servivano più come lavoro da importare e facevano rumore
in cartella. Di ciascuna restano il **perché** (contesto), il **cosa** e, dove c'è, **com'è andata**.
I criteri di accettazione sono stati tolti: erano la lista di controllo del lavoro, e il lavoro è finito.

Gli originali completi stanno nella cronologia di Git, al tag della fase (`v0.5.0` per la 0.5.0, `v0.6.0` per la 0.6.0):

```bash
git show v0.5.0:docs/backlog/v0.1.0/07-sec-05-segreti-fuori-da-git.md
```

Il lavoro in corso sta in [`docs/backlog/`](backlog/README.md); le note di rilascio di ogni fase
in [`docs/release/`](release/).

## Indice

- [0.1.0 — Impianto chiuso](#010--impianto-chiuso) — 10 schede
- [0.2.0 — Fondamenta](#020--fondamenta) — 10 schede
- [0.3.0 — Copertura](#030--copertura) — 8 schede
- [0.4.0 — Proattività](#040--proattivita) — 7 schede
- [0.5.0 — Prodotto](#050--prodotto) — 12 schede
- [0.6.0 — Il Cervello](#060--il-cervello) — 13 schede

## 0.1.0 — Impianto chiuso

### #1 — fix(data-store): aggiunge il metodo add_knowledge_item mancante

*tipo: difetto, area: core, gravita': critica*

#### Contesto

`core/interview_engine.py:110` chiama `data_store.add_knowledge_item(text=..., category=...)`.
Il metodo **non esiste**: `DataStore` espone solo `get_knowledge()` e `save_knowledge()`.

La chiamata non e' racchiusa in un `try`, quindi l'`AttributeError` risale fino
a FastAPI e diventa un **HTTP 500 a ogni risposta dell'utente**, sia da
`POST /api/learning/answer` sia dalla chat vocale. La Modalita' Apprendimento
non ha mai completato un singolo passo dell'intervista.

#### Cosa fare

- Aggiungere `DataStore.add_knowledge_item(text: str, category: str = "generale", enabled: bool = True) -> dict`
- Generare un identificativo univoco (non `f"k_{len(items)+1}"`, che collide dopo una cancellazione)
- Restituire l'elemento salvato, come si aspetta il chiamante
- Evitare di duplicare un fatto gia' presente con lo stesso testo
- Rimuovere il marcatore `xfail` da `tests/unit/test_regressioni_bloccanti.py`

### #2 — fix(ollama): l'estrazione dei fatti chiama un metodo inesistente

*tipo: difetto, area: core, gravita': critica*

#### Contesto

`core/interview_engine.py:181` chiama `self.ollama.generate(prompt=..., system=..., temperature=...)`.
`OllamaClient` espone solo `chat()`, `check_health()`, `get_models_detailed()` e
`get_available_models()`.

Qui l'eccezione e' catturata dal `try`, quindi il codice cade **sempre** nel ramo
di fallback e salva la frase grezza dell'utente come fatto. Il prompt di
estrazione JSON — con la proposta automatica di routine — non e' mai stato
eseguito: e' codice morto.

Conseguenza: anche risolvendo BLK-01, l'intervista produrrebbe una knowledge base
di trascrizioni invece che di fatti atomici, e non proporrebbe mai una routine.

#### Cosa fare

- Riscrivere `_extract_knowledge_and_routines` su `OllamaClient.chat()`, che gia' esiste
- Passare `format: "json"` a Ollama per ottenere JSON valido senza post-elaborazione
- Validare la risposta con un modello Pydantic invece che con `json.loads` nudo
- Registrare a livello `warning` quando si ricade sul fallback, invece di farlo in silenzio
- Verificare che il fallback resti valido quando Ollama e' spento

### #3 — security(api): richiede autenticazione su tutti gli endpoint di gestione

*tipo: difetto, area: sicurezza, gravita': critica*

#### Contesto

`is_authenticated()` viene invocata in **un solo endpoint su trentanove**:
`POST /api/settings`.

Restano completamente aperti, fra gli altri:

| Endpoint | Cosa consente |
| :--- | :--- |
| `POST /api/modes/{nome}/activate` | Eseguire una routine domotica |
| `POST /api/chat` | Comandare la casa in linguaggio naturale |
| `GET`/`DELETE /api/users` | Leggere e cancellare l'anagrafica della famiglia |
| `GET /api/knowledge` | Leggere abitudini, orari, dati della casa |
| `GET /api/ha/entities` | Enumerare ogni dispositivo dell'abitazione |
| `POST`/`DELETE /api/aliases`, `/api/modes`, `/api/timers` | Alterare la configurazione |

Con il server in ascolto su `0.0.0.0`, qualunque dispositivo sulla rete di casa
— un ospite sul Wi-Fi, un elettrodomestico compromesso — comanda l'impianto e
scarica i dati della famiglia con una singola `curl`.

#### Cosa fare

- Definire una dipendenza FastAPI `richiedi_autenticazione` e applicarla a livello di router, non endpoint per endpoint
- Elencare esplicitamente i pochi endpoint pubblici: `GET /` (che poi impone il login lato server, vedi SEC-03), `GET /api/auth/status`, `POST /api/auth/login`, `POST /api/alexa` (protetto invece dalla firma Amazon, vedi SEC-02)
- Introdurre il principio **protetto per difetto**: un endpoint nuovo e' privato se non dichiara il contrario
- Distinguere i permessi per ruolo: un profilo `child` non deve poter cancellare utenti ne' modificare le impostazioni
- Aggiungere un test che elenca le rotte registrate e fallisce se una rotta non e' ne' protetta ne' nella lista delle pubbliche
- **Identita' per persona**: l'accesso non chiede piu' un PIN di casa ma chi sei piu' il tuo PIN. Il campo `pin` esiste gia' in `UserProfile` ed e' sempre stato inutilizzato. La sessione porta con se' l'identita' reale, non una scelta da menu a tendina. Vedi [ADR 0004](adr/0004-identita-ruoli-e-permessi.md)
- Durata della sessione a 30 giorni, con il blocco per inattivita' gia' presente a proteggere lo schermo lasciato acceso

### #4 — security(alexa): verifica la firma Amazon e l'applicationId

*tipo: difetto, area: sicurezza, area: integrazioni, gravita': critica*

#### Contesto

`POST /api/alexa` esegue comandi domotici senza alcuna verifica dell'origine:

1. Non controlla gli header `Signature` e `SignatureCertChainUrl` richiesti da Amazon.
2. Non confronta l'`applicationId` della richiesta con `settings.alexa.skill_id`,
   che e' configurabile ma **non viene letto da nessuna riga di codice**.
3. Non verifica il campo `timestamp`, che protegge dai replay.

Il README, inoltre, istruisce a disattivare «Block Common Exploits» sul reverse
proxy e a creare una regola Cloudflare che salta il WAF proprio su quel percorso.

Il risultato: **una POST JSON di dieci righe da qualsiasi punto di Internet
comanda l'impianto di casa.** E' il difetto piu' grave del progetto, perche' e'
l'unico raggiungibile dall'esterno.

#### Cosa fare

- Implementare la verifica della firma secondo la specifica Amazon: scaricare la catena di certificati dall'URL indicato, validarne il dominio (`s3.amazonaws.com/echo.api/`), verificare che il certificato includa `echo-api.amazon.com` nei SAN, controllare la validita' temporale e verificare la firma sul corpo grezzo
- Mettere in cache i certificati per non scaricarli a ogni richiesta
- Confrontare `session.application.applicationId` con `SHINRA_ALEXA_SKILL_ID`; se la variabile non e' impostata, **rifiutare** invece di accettare
- Verificare che il `timestamp` non sia piu' vecchio di 150 secondi
- Leggere il corpo grezzo prima del parsing JSON: la firma si calcola sui byte esatti
- Aggiornare `ALEXA_SETUP_GUIDE.md` e `README.md` rimuovendo il consiglio di disattivare le protezioni del proxy

### #5 — security(web): il blocco della dashboard deve avvenire sul server

*tipo: difetto, area: sicurezza, area: frontend, gravita': alta*

#### Contesto

`checkAuthStatus()` in `web/templates/index.html:1515` mostra la schermata di
blocco impostando `lockModal.style.display = 'flex'`. A quel punto la dashboard
completa e' gia' stata inviata al browser e le chiamate API partono comunque.

Chiudere l'overlay dagli strumenti sviluppatore, o semplicemente disabilitare
JavaScript, restituisce il pannello intero. L'impostazione `protect_dashboard`
comunica una protezione che non esiste.

#### Cosa fare

- `GET /` verifica la sessione lato server: senza sessione valida serve una pagina di login minimale, non la dashboard
- Spostare il token di sessione in un cookie `HttpOnly`, `Secure`, `SameSite=Lax`, invece che in `sessionStorage` dove qualsiasi script lo legge
- Mantenere l'overlay solo come blocco per inattivita' all'interno di una sessione gia' aperta, non come misura di sicurezza
- Redirigere al login quando una chiamata API risponde `401`

### #6 — security(auth): PIN con hash, login corretto e rate limit dietro proxy

*tipo: difetto, area: sicurezza, gravita': alta*

#### Contesto

Tre difetti nello stesso punto, `server/routes_admin.py`.

**Login permissivo (riga 78).** La condizione e'
`if not expected_pin or provided_pin == expected_pin`: se il PIN non e'
configurato, il login restituisce comunque un token valido per sette giorni.
Qualunque stringa entra.

**Rate limit inefficace.** `FAILED_ATTEMPTS` e' indicizzato su
`request.client.host`, che dietro il reverse proxy consigliato nel README vale
`127.0.0.1` per tutti. Il quinto tentativo sbagliato di un attaccante blocca
per cinque minuti il proprietario di casa, e viceversa. `X-Forwarded-For` non
viene mai letto.

**Confronto vulnerabile ai tempi.** Il PIN si confronta con `==`, in chiaro.

#### Cosa fare

- Rifiutare il login quando nessun PIN e' configurato, invece di accettarlo
- Salvare il PIN come hash (`argon2` o `bcrypt`), mai in chiaro
- Migrare automaticamente un PIN in chiaro esistente al primo avvio
- Confronto a tempo costante
- Leggere l'IP reale da `X-Forwarded-For` **solo se la richiesta proviene da un proxy elencato come fidato** in configurazione, altrimenti usare `request.client.host`
- Firmare i token di sessione con `SHINRA_SESSION_SECRET`, che oggi e' dichiarato e mai usato
- Ridurre la durata della sessione da sette giorni a un valore configurabile, con un giorno come predefinito

### #7 — security(config): sposta i segreti fuori dal repository

*tipo: difetto, area: sicurezza, area: infra, gravita': alta*

#### Contesto

`config/config.yaml` **e' tracciato da git**, e `config/settings.py:65`
(`save_config`) ci scrive dentro il token a lungo termine di Home Assistant e il
PIN amministratore ogni volta che si salvano le impostazioni dall'interfaccia.

La cronologia oggi e' pulita: contiene solo il segnaposto. Ma il prossimo
`git commit -a` dopo una modifica dalle impostazioni pubblica le credenziali di
casa su un repository GitHub pubblico. E' una mina gia' armata.

Stesso problema per `data/users.json` e `data/knowledge.json`, che contengono
nomi, abitudini e dati personali della famiglia e sono anch'essi versionati.

> Questa issue va chiusa **per prima**: il controllo «segreti» della CI fallisce
> finche' i file restano tracciati.

#### Cosa fare

- `git rm --cached config/config.yaml data/users.json data/knowledge.json data/timers.json`
- Verificare che `.gitignore` li copra (gia' aggiornato)
- Spostare i dati di seed generici in `data/examples/` e far generare i file runtime al primo avvio se assenti
- Introdurre `pydantic-settings`: i segreti si leggono da `.env` o dall'ambiente, mai da `config.yaml`
- `save_config()` non deve mai scrivere un segreto su disco in chiaro
- Aggiungere alla configurazione un controllo d'avvio che rifiuta di partire se il token Home Assistant e' ancora il segnaposto e `home_assistant.enabled` e' vero
- Documentare la procedura in `README.md` e in `CONTRIBUTING.md`

### #8 — security(server): debug disattivato, header di sicurezza e CORS

*tipo: attivita', area: sicurezza, gravita': media*

#### Contesto

Diverse impostazioni di irrobustimento mancano o sono errate:

- `config.yaml` ha `debug: true`, quindi `run.py` avvia uvicorn con `reload=True`: in produzione ricarica il processo a ogni scrittura su file e mostra tracce di errore complete.
- Nessun header di sicurezza sulle risposte.
- Nessuna politica CORS: il comportamento predefinito e' permissivo per le richieste semplici.
- `restricted_topics` esiste in `UserProfile` e **non e' applicato da nessuna riga**: il profilo `child` cambia solo il tono del prompt, non cio' a cui puo' accedere.
- Le eccezioni non gestite espongono la traccia interna al client.

#### Cosa fare

- `debug: false` come predefinito; il reload si abilita solo con una variabile d'ambiente esplicita di sviluppo
- Aggiungere gli header: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, `Content-Security-Policy` compatibile con la PWA
- CORS chiuso per difetto, con lista di origini configurabile
- Gestore globale delle eccezioni: messaggio generico al client, traccia completa nel log
- Applicare `restricted_topics` come filtro reale prima dell'invio al modello e sulla risposta
- Documentare in `README.md` che il servizio va esposto solo dietro HTTPS
- Aggiungere `GET /health`: endpoint pubblico che risponde `200` se il processo e' vivo, **senza esporre alcuna informazione** (niente modelli, niente URL di Home Assistant, niente stato dei servizi). Serve allo script di distribuzione, che oggi deve interrogare `/api/status` e accettare qualsiasi codice HTTP perche' quell'endpoint diventera' autenticato. Vedi `docs/DEPLOY.md`.

### #9 — fix(home-assistant): un unico client, con configurazione dinamica

*tipo: difetto, area: core, area: integrazioni, gravita': alta*

#### Contesto

`core/tools/ha_tools.py:10` istanzia il client all'import passando i valori:

```python
ha_client = HomeAssistantClient(
    base_url=settings.home_assistant.url,
    token=settings.home_assistant.token,
)
```

Passare i valori esplicitamente **congela** URL e token al momento dell'import,
perche' le property restituiscono `self._base_url` se valorizzato. Ogni altro
punto del progetto costruisce invece `HomeAssistantClient()` senza argomenti,
usando le property dinamiche.

Conseguenza: chi corregge URL o token dalle impostazioni vede il pannello
diagnostico diventare verde — usa il client dinamico — **mentre i comandi ai
dispositivi continuano a fallire** contro il vecchio indirizzo, fino al riavvio.

#### Cosa fare

- Un solo client Home Assistant condiviso, fornito per iniezione di dipendenza
- Nessuna istanza creata a livello di modulo con valori congelati
- Il client riusa una singola `httpx.AsyncClient` con pool di connessioni, invece di aprirne una nuova a ogni chiamata
- Alla modifica delle impostazioni il client aggiorna URL e token senza riavvio
- Chiusura pulita del client alla terminazione dell'applicazione

### #10 — test: rete di regressione sui difetti della revisione tecnica

*tipo: attivita', area: infra, gravita': alta*

#### Contesto

Il progetto non ha test. `test_tools.py` e' uno script di stampe che chiama API
esterne reali: non verifica nulla e non puo' girare in CI.

Entrambi i difetti bloccanti sono chiamate a metodi inesistenti: **qualsiasi
test che avesse eseguito quel percorso li avrebbe intercettati.**

#### Cosa fare

- Struttura `tests/unit/` e `tests/integration/`
- Un test per ogni difetto della revisione, che fallisce prima della correzione
- Finche' un difetto e' aperto, il test porta `@pytest.mark.xfail(strict=True)`: quando la correzione arriva il test diventa rosso, obbligando a togliere il marcatore. Nessun difetto puo' essere dichiarato risolto senza prova.
- Test degli endpoint con `TestClient`, per verificare le protezioni di SEC-01
- Simulare le chiamate HTTP con `respx`: nessuna rete nei test unitari
- Convertire `test_tools.py` in test veri, marcati `network`
- Test del parser dei timer, che e' pura logica e oggi non e' coperto
- Rimuovere `duckduckgo-search` da `requirements.txt`: non e' importato da nessuna parte
      (fatto in v0.2.0: requirements.txt rimanda a pyproject.toml, unica fonte)


## 0.2.0 — Fondamenta

### #11 — feat(scheduler): scheduler persistente per timer, promemoria e automazioni

*tipo: funzione, area: infra, gravita': critica*

#### Contesto

Non esiste alcuno scheduler lato server. Ne derivano due difetti gravi:

**REL-01 — I promemoria non suonano mai.** «Ricordami di prendere le medicine
alle 17:30» viene interpretato correttamente, scritto in `data/reminders.json`,
e l'assistente risponde «Perfetto, ti ricordero'...». Poi non succede nulla:
nessun processo rilegge quel file, e la parola `reminder` non compare in nessuna
delle 4.657 righe del frontend. Per una casa che deve supportare anziani o
terapie, e' la promessa piu' pericolosa che il sistema faccia.

**REL-02 — I timer contano solo col browser aperto.** Il conto alla rovescia
vive in `startTimerTick()` (`index.html:3380`), un `setInterval` lato client. Un
timer impostato dall'Echo in cucina, senza browser aperto, non suona. I timer
scaduti non vengono mai marcati `completed` ne' rimossi: `timers.json` cresce
all'infinito e ogni voce vecchia riappare scaduta al caricamento successivo.

E' il singolo pezzo di infrastruttura mancante che blocca timer, promemoria e
qualunque automazione futura.

#### Cosa fare

- `AsyncIOScheduler` di APScheduler avviato nel `lifespan` di FastAPI
- Job store `SQLAlchemyJobStore` sul database della issue #12: i job sopravvivono al riavvio
- Alla creazione di un timer o promemoria si registra un job; alla cancellazione lo si rimuove
- Alla scadenza il job pubblica un evento interno; i canali in ascolto lo consegnano
- Consegna verso l'interfaccia web tramite WebSocket, non piu' polling
- Consegna vocale su un Echo tramite `notify.alexa_media`: **collegare finalmente `speak_on_alexa()`, oggi definita e mai chiamata, e `alexa_media_player_entity`, oggi configurabile e mai letta**
- `misfire_grace_time` per tipo di job: un promemoria di mezz'ora fa si consegna ancora, un timer della pasta no
- Marcare i timer completati e ripulirli dopo un periodo di conservazione

### #12 — refactor(persistenza): SQLite e SQLAlchemy al posto dei file JSON

*tipo: attivita', area: infra, gravita': alta*

#### Contesto

Tutto lo stato vive in sei file JSON letti e riscritti integralmente a ogni
modifica. Ogni salvataggio e' una sequenza leggi-modifica-riscrivi su file
aperto in `"w"`, senza lock e senza sostituzione atomica.

Due richieste in parallelo — plausibili con dashboard ed Echo attivi insieme —
perdono una modifica. Se il processo si interrompe a meta' scrittura, resta un
file troncato che l'avvio successivo scarta in silenzio restituendo una lista
vuota: **perdita totale dei dati senza alcun errore visibile.**

Manca inoltre qualunque storico, il che blocca registro azioni, spiegabilita' e
diario della casa.

Le motivazioni complete e le alternative scartate sono in
[ADR 0002](adr/0002-sqlite-al-posto-dei-file-json.md).

#### Cosa fare

- SQLAlchemy 2.x in modalita' asincrona, con SQLite in `data/shinra.db`
- Alembic per le migrazioni di schema
- Modelli: utenti, conoscenza, alias, modalita', fonti, timer, promemoria, registro azioni, eventi
- Livello repository che sostituisce `DataStore`, `UserManager` e la parte di persistenza di `TimerEngine`, mantenendo le firme pubbliche dove possibile
- Script di migrazione una tantum dai JSON esistenti — **scrive su un database nuovo e non tocca i file originali**, che restano come backup finche' non si verifica l'esito
- Abilitare la modalita' WAL di SQLite per la concorrenza in lettura
- Esportazione in JSON mantenuta come formato di backup, non come archivio primario

### #13 — fix(memoria): contesto di conversazione separato per utente e canale

*tipo: difetto, area: core, gravita': alta*

#### Contesto

`core/memory.py:30` crea un singleton globale `ConversationMemory`. La chat del
salotto, quella del telefono e ogni richiesta Alexa scrivono nella **stessa**
cronologia: il contesto di un adulto finisce nella sessione impostata come
`child` e viceversa, e due persone che parlano insieme si confondono a vicenda.

Il design e' gia' corretto — `process_user_input` accetta un parametro
`session_memory` — ma **nessun chiamante lo passa**.

C'e' un difetto collegato: `ConversationMemory.add_tool_interaction()` ha corpo
`pass`. Le azioni eseguite non entrano mai nel contesto, quindi l'assistente non
ricorda cosa ha appena fatto: «spegnila» dopo «accendi la luce della cucina» non
puo' funzionare.

#### Cosa fare

- Gestore delle sessioni indicizzato per **utente**, non per
      `(utente, canale)`: i due punti di questa scheda si contraddicevano,
      perche' l'ultimo criterio di accettazione chiede che una conversazione
      iniziata sull'Echo prosegua sul telefono. Vince il criterio: cio' che
      va tenuto separato sono le persone, non i dispositivi.
- `session_memory` passato da `/api/chat` e dal gestore Alexa
- Scadenza delle sessioni inattive, con limite al numero di sessioni in memoria
- Implementare `add_tool_interaction`, cosi' che le azioni eseguite entrino nel contesto
- Continuita' fra canali: una conversazione iniziata sull'Echo prosegue sul telefono per lo stesso utente

### #14 — perf(config): configurazione in cache con invalidazione al salvataggio

*tipo: attivita', area: infra, gravita': media*

#### Contesto

`reload_settings()` apre e analizza `config.yaml` **dentro** le property
`base_url`, `model`, `timeout` (`core/ollama_client.py`) e `token`, `headers`
(`core/ha_client.py`). Un singolo turno di chat produce decine di letture
sincrone dal filesystem **all'interno dell'event loop asincrono**.

Non e' percepibile su un SSD, ma e' esattamente il tipo di blocco che degrada
tutto quando il carico cresce, ed e' invisibile finche' non lo si cerca.

#### Cosa fare

- Caricare la configurazione una volta all'avvio e tenerla in memoria
- Invalidare la cache esplicitamente al salvataggio delle impostazioni,
      notificando i componenti interessati. Non serve una notifica: dalla
      correzione di `reload_settings()` (PR #61) esiste un solo oggetto
      condiviso, aggiornato al suo posto. Chi lo legge vede subito il valore
      nuovo, e non c'e' una cache da invalidare che qualcuno possa scordarsi.
- ~~Passare a `pydantic-settings`~~ — **non fatto, di proposito.** La
      precedenza richiesta (ambiente, poi `.env`, poi `config.yaml`, poi i
      valori predefiniti) esiste gia' in `config/secrets.py` ed e' coperta da
      test. Riscriverla con un'altra libreria cambierebbe il meccanismo senza
      cambiare il comportamento: rischio senza guadagno, proprio nel punto
      dove passano i segreti di casa. Se un giorno servira' per altro, si
      riapre.
- Nessuna lettura da disco durante il ciclo di vita di una richiesta

### #15 — feat(audit): registro delle azioni eseguite in casa

*tipo: funzione, area: sicurezza, area: infra*

#### Contesto

Il sistema comanda luci, prese e clima — e presto serrature e allarme — senza
tenere alcuna traccia. Il logging va solo su standard output, senza rotazione e
senza identificativo di correlazione.

Non e' possibile rispondere a «chi ha spento il riscaldamento alle 3 di notte?».
Per un sistema che controlla una casa e' una lacuna di sicurezza, oltre che il
prerequisito della funzione di spiegabilita' prevista dopo la 1.0.0.

#### Cosa fare

- Tabella del registro: momento, utente, canale, intento, tool, parametri, esito, durata, identificativo di correlazione
- Registrare ogni esecuzione di tool, ogni attivazione di modalita', ogni accesso e ogni modifica alle impostazioni
      (l'aggancio e' in `execute_tool`, il passaggio obbligato di ogni
      azione: un tool nuovo risulta tracciato senza che nessuno se ne
      debba ricordare. L'attivazione di modalita' e' essa stessa un tool.)
- Identificativo di correlazione propagato dalla richiesta fino ai tool
- Log applicativo strutturato in JSON, con rotazione
- Endpoint di consultazione con filtri, riservato al ruolo `admin`
- Politica di conservazione configurabile
- **Mai registrare segreti**: token e PIN vanno oscurati

### #16 — refactor(struttura): layout src/shinra e pacchetto installabile

*tipo: attivita', area: infra*

#### Contesto

Il codice vive in cartelle di primo livello (`core/`, `server/`, `config/`,
`integrations/`). `config` in particolare e' un nome molto comune: un `import
config` puo' risolvere sulla directory di lavoro invece che sul progetto, con
errori difficili da diagnosticare.

Soprattutto, la struttura attuale non ha confini dichiarati fra livelli:
`server/routes_admin.py` importa direttamente `core.tools.ha_tools`, e nulla
impedisce che un tool importi un router. Man mano che i moduli aumentano —
serrature, media, energia, presenza — l'assenza di confini diventa il freno
principale.

La struttura target e le regole di dipendenza sono in
[docs/ARCHITECTURE.md](ARCHITECTURE.md).

#### Cosa fare

- Spostare il codice sotto `src/shinra/` con i livelli `domain`, `infra`, `services`, `skills`, `channels`, `api`
- Aggiornare gli import; verificare che i test passino a ogni passo intermedio
- `__version__` in `src/shinra/__init__.py`, letto da `pyproject.toml`
- Punto di ingresso `shinra` come comando da console, mantenendo `run.py` come alias
- La regola di divieto import fra livelli fallisce in CI — ma con un test
      (`tests/unit/test_architettura.py`) e non con `flake8-tidy-imports`. La
      regola di ruff sa dire «vietato», non «vietato tranne queste diciannove
      che esistevano prima»: o si accettano tutte come eccezioni permanenti,
      o la CI e' rossa dal primo giorno. Il test invece congela l'elenco:
      una violazione nuova fallisce, e una riparata fallisce anche lei
      finche' non la si toglie. Il debito e' scritto e puo' solo accorciarsi.
- Aggiornare `ARCHITECTURE.md` con la struttura effettiva

#### Cosa resta

Le diciannove violazioni delle regole di dipendenza, elencate in
`tests/unit/test_architettura.py`. Ripararle dentro allo spostamento avrebbe
prodotto una modifica illeggibile: sono un lavoro suo, da fare un gruppo
alla volta. Il primo e' `api -> infra` (dodici voci su diciannove).

### #17 — refactor(agent): estrarre l'intent router da process_user_input

*tipo: attivita', area: core*

#### Contesto

`ShinraAgent.process_user_input` e' lungo circa 250 righe e contiene, in
sequenza inline: gestione dell'intervista, parsing di timer e promemoria,
attivazione di modalita', controllo diretto dei dispositivi per alias, meteo,
notizie, Wikipedia, costruzione del prompt e ciclo di tool calling.

Non e' testabile a pezzi, e ogni intento nuovo allunga la stessa funzione.

Ci sono anche due difetti di riconoscimento gia' individuati:

- **Falso positivo sul meteo.** Il fast-path scatta sulla parola `temperatura`,
  quindi «che temperatura c'e' in salotto» interroga Open-Meteo per le previsioni
  esterne invece del sensore interno di Home Assistant.
- **Estrazione della citta' fragile.** L'espressione
  `\b(?:a|ad|per|di)\s+([a-zA-Zaeeiou]+)` cattura una sola parola: «Reggio
  Emilia» e «San Giovanni» si spezzano. Le esclusioni sono una lista scritta a mano.

#### Cosa fare

- Estrarre ogni intento in un handler con interfaccia comune: verifica di applicabilita', priorita', esecuzione
- Registro degli handler ordinato per priorita', al posto della catena di `if`/`elif`
- Un intento nuovo si aggiunge registrando un handler, senza toccare l'agente
- Distinguere temperatura interna (sensore HA) da temperatura esterna (meteo)
- Estrazione della citta' su nomi composti, verificata contro la geocodifica invece che con una lista di esclusioni
- Un test per ogni handler

### #18 — test: portare la copertura al 60% e attivare i controlli automatici

*tipo: attivita', area: infra*

#### Contesto

La v0.1.0 introduce i test di regressione sui difetti noti. Questa issue estende
la copertura al codice esistente e rende i controlli obbligatori, perche' la
fase v0.2.0 riscrive persistenza, memoria e struttura: senza rete di sicurezza
e' una riscrittura al buio.

#### Cosa fare

- Copertura ≥ 60% su `core/` e `server/` — **80%**, con la soglia
      in CI al 70%: sotto il valore reale perche' non fallisca per un test
      spostato, sopra il 60% chiesto perche' significhi qualcosa
- Test degli endpoint con `TestClient`, incluse tutte le protezioni
- Test del livello di persistenza, inclusa la concorrenza
- Test dello scheduler, inclusa la ripresa dopo riavvio
- Test dell'adattatore Alexa con richieste firmate e non firmate
- Attivare `pre-commit` su tutti i contributi
- Rendere obbligatoria la CI verde per il merge su `main` — **e' una
      impostazione di GitHub, non del repository**: la deve attivare il
      proprietario. Comando in fondo a CONTRIBUTING.md.
- Rimuovere `continue-on-error` da mypy e tipizzare i moduli, uno alla
      volta — fatto su `config/` e `core/`, dove passano configurazione,
      permessi e dati di casa. Su `server/` e `integrations/` resta
      informativo: dichiararlo obbligatorio senza esserlo sarebbe peggio
      che dirlo.

### #46 — feat(sicurezza): ruoli personalizzati e permessi per utente

*tipo: funzione, area: sicurezza, gravita': alta*

#### Contesto

Con l'identita' per persona in piedi (issue #3), i permessi diventano
applicabili sul serio. Oggi il profilo distingue adulto, ragazzo e bambino ma
quella distinzione cambia **solo il tono delle risposte**: `restricted_topics`
esiste nel modello e nessuna riga lo applica, e un bambino puo' comandare
qualunque cosa.

I permessi non sono attributi del profilo ma di un **ruolo**, e i ruoli si
creano: oltre ai quattro predefiniti — Amministratore, Adulto, Ragazzo, Ospite
— devono poterne nascere altri, «Collaboratrice domestica», «Nonno», «Ospite
fine settimana», con la propria combinazione di permessi.

Motivazioni e alternative in [ADR 0004](adr/0004-identita-ruoli-e-permessi.md).

#### Cosa fare

- Modello `Ruolo`: nome, descrizione, insieme di permessi. Quattro
      predefiniti, modificabili, piu' quelli creati dall'utente
- Ogni utente ha un ruolo; l'ultimo amministratore non puo' essere
      declassato ne' cancellato
- Insieme minimo dei permessi:
      `dispositivi.comanda`, `sicurezza.comanda`, `modalita.attiva`,
      `modalita.modifica`, `conoscenza.leggi`, `conoscenza.scrivi`,
      `utenti.gestisci`, `impostazioni.gestisci`
- `sicurezza.comanda` separato dagli altri dispositivi: serrature e allarme
      hanno conseguenze diverse da una lampadina
- Verifica dei permessi come dipendenza FastAPI, dichiarata su ogni rotta
- **L'esecuzione di una routine verifica i permessi di chi la invoca**, non
      di chi l'ha scritta: altrimenti il controllo si aggira scrivendo una routine
- Applicare finalmente `restricted_topics` prima dell'invio al modello e
      sulla risposta — gia' fatto nella v0.1.0 (`core/argomenti_vietati.py`,
      issue #5), verificato dai suoi test
- Schermata di gestione ruoli e assegnazione — fatta nella PR di frontend
      che porta anche i dispositivi fidati (issue #47). I permessi di ogni
      ruolo sono caselle da spuntare, i ruoli propri si creano dalla pagina, i
      predefiniti si modificano ma non si cancellano. E il ruolo di un profilo
      **si sceglie**: veniva dedotto da avatar e fascia d'eta', e la fascia
      «ragazzo» finiva nel ramo `adult` — un tredicenne con le serrature.
- Ogni rifiuto finisce nel registro delle azioni (issue #15)
- Un rifiuto si spiega: «non hai il permesso di aprire la serratura»,
      non un 403 muto

### #47 — feat(sicurezza): dispositivi fidati, per non chiedere il PIN ogni volta

*tipo: funzione, area: sicurezza, area: frontend*

#### Contesto

Un PIN per persona rende i permessi reali, ma su un telefono diventa un
fastidio quotidiano. E una protezione fastidiosa viene disattivata: a quel
punto la casa e' aperta come prima, con in piu' l'illusione di essere protetta.

La soluzione e' quella che usano banche e servizi di posta: ricordare il
dispositivo dopo il primo accesso, e permettere di revocarlo.

#### Cosa fare

- Dopo il primo accesso con PIN, offrire «ricorda questo dispositivo» con
      un nome scelto dall'utente («iPhone di Alessio»)
- Credenziale di dispositivo legata all'utente, in un cookie `HttpOnly`,
      `Secure`, `SameSite=Lax`, valida 30 giorni e rinnovata a ogni uso
- Elenco dei dispositivi fidati: rotte `/api/dispositivi` (elenco,
      revoca singola, revoca totale) con nome, ultimo accesso e indirizzo.
      La schermata sta nella scheda «Gestione Utenti», insieme ai ruoli
      (issue #46): sono la stessa pagina e sono state lo stesso lavoro. Ogni
      riga dice anche se e' il dispositivo da cui si sta guardando — senza,
      l'elenco e' una fila di nomi identici e si revoca il proprio.
- «Revoca tutti i dispositivi» in un clic, per il telefono perso
- Revocare un utente revoca i suoi dispositivi
- Cambiare il PIN revoca i dispositivi, tranne quello da cui lo si cambia
- La credenziale identifica il dispositivo, non aumenta i permessi: un
      dispositivo fidato di un profilo bambino resta un profilo bambino


## 0.3.0 — Copertura

### #19 — feat(home-assistant): connessione WebSocket per stato ed eventi in tempo reale

*tipo: funzione, area: integrazioni, gravita': alta*

#### Contesto

Oggi ogni informazione da Home Assistant arriva da `GET /api/states`, cioe' da
una fotografia richiesta su domanda. Il sistema non sa mai **quando** qualcosa
accade: non esiste il concetto di evento.

Questo e' il vincolo che blocca l'intera fase v0.4.0. Una regola come «se la
porta si apre dopo le 23, accendi l'ingresso» e' impossibile senza eventi.

#### Cosa fare

- Client WebSocket verso `/api/websocket` con autenticazione a token
- Sottoscrizione a `state_changed` e mantenimento di una cache locale degli stati
- Riconnessione automatica con attesa progressiva; fallback su REST mentre la connessione e' assente
- Bus eventi interno a cui i servizi si sottoscrivono — esisteva gia' dalla
      v0.2.0 per timer e promemoria (`domain/eventi.py`): qui si e' aggiunto il
      tipo `ha.stato_cambiato` e chi lo pubblica
- `get_relevant_entities_summary` legge dalla cache invece di interrogare la rete.
      Passa dalla stessa funzione anche `/api/ha/entities`: due strade diverse
      per la stessa domanda divergerebbero, e la differenza si noterebbe solo
      quando la connessione cade
- Stato dei dispositivi spinto all'interfaccia via WebSocket, al posto del polling

### #20 — feat(skills): tool per serrature, media player, aspirapolvere e ventilatori

*tipo: funzione, area: core*

#### Contesto

`server/routes_admin.py` elenca `lock`, `media_player`, `vacuum` e `fan` fra i
domini controllabili, e l'interfaccia li mostra nella mappa dispositivi. Ma
`control_device` gestisce solo luci, prese, clima e tapparelle: **nessun tool sa
comandarli**. L'utente li vede e non puo' usarli.

#### Cosa fare

- `lock`: blocca, sblocca, stato. Lo sblocco chiede conferma — una seconda
      richiesta entro un minuto, non un parametro che il modello puo' riempire
      da solo — e il permesso `sicurezza.comanda` e' gia' imposto dal client di
      Home Assistant, quindi vale anche qui. In piu': **dalla voce non si
      apre**, perche' l'ADR 0004 dice che il canale vocale non distingue chi
      parla
- `media_player`: riproduci, pausa, traccia successiva e precedente,
      volume, sorgente. Il multiroom no: e' un raggruppamento di entita' e
      merita una scheda sua, non una riga in fondo a questa
- `vacuum`: avvia, ferma, rientra alla base, pulisci una stanza
- `fan`: acceso/spento, velocita', oscillazione
- Ogni tool valida l'`entity_id` contro le entita' reali prima di inviare
      il comando. Con la cache della issue #19 non costa niente, e l'errore
      propone l'alternativa piu' simile invece di dire solo «no»
- Ogni azione finisce nel registro della issue #15 — passa da
      `execute_tool`, quindi senza che questi tool debbano ricordarsene

### #21 — feat(skills): clima completo e tapparelle con posizione

*tipo: funzione, area: core*

#### Contesto

`control_device` supporta `set_temperature` per il clima e `open`/`close` per le
tapparelle. Manca tutto il resto: modalita', ventola, umidita', posizione
intermedia, orientamento delle lamelle.

«Abbassa la tapparella a meta'» e «metti il condizionatore in deumidificazione»
oggi non sono esprimibili.

#### Cosa fare

- Clima: modalita' (riscaldamento, raffrescamento, automatico, deumidificazione,
      ventilazione), velocita' ventola, umidita' obiettivo, preset. Le parole con
      cui una persona chiede una modalita' — «caldo», «aria condizionata»,
      «secco» — arrivano tutte al codice giusto
- Tapparelle: posizione percentuale, orientamento lamelle, arresto a meta'
      corsa. **Cento e' aperta, zero e' chiusa**, come in Home Assistant e come
      sulla dashboard: e' il verso che si sbaglia piu' spesso, e c'e' un test che
      lo fissa perche' un commento non fallisce
- Lettura dello stato corrente, non solo comando: `stato_clima` e
      `stato_tapparella`. La temperatura **impostata** e quella **misurata** sono
      due numeri diversi e vengono tenuti distinti
- Aggiornare gli schemi dei tool e il prompt di sistema

### #22 — feat(presenza): presenza delle persone e automazioni di arrivo e uscita

*tipo: funzione, area: core*

#### Contesto

`person` e `device_tracker` sono elencati fra i domini visibili, ma nessuna
logica li usa. Il sistema non sa se c'e' qualcuno in casa: e' l'informazione
piu' utile della domotica e oggi e' inutilizzata.

#### Cosa fare

- Servizio di presenza che aggrega `person` in uno stato di casa: qualcuno
      presente, casa vuota, prima persona rientrata, ultima persona uscita
- Eventi di transizione pubblicati sul bus della issue #19. Ha richiesto
      di separare i domini **osservati** da quelli **comandabili**: `person`
      non si comanda, e finche' sul bus finiva solo cio' che si comanda la
      presenza non ci sarebbe mai arrivata
- Collegare la presenza al profilo utente — **non in questa PR.** Sapere
      *chi c'e'* non e' sapere *chi parla*: con due persone in casa non
      disambigua, e con una sola sarebbe un'euristica che sbaglia in silenzio
      proprio quando conta. Il pezzo che serve davvero e' il riconoscimento
      di chi parla (issue #34, v0.4.0); la presenza sara' il suo
      complemento, non il suo sostituto
- Trigger di presenza nell'editor di routine — **appartiene alla issue
      #27.** Oggi una routine non ha nessun tipo di trigger su evento: ha
      `trigger_phrases`, cioe' frasi da dire. Il motore di regole della
      v0.4.0 e' il lavoro che introduce i trigger, e gli eventi di presenza
      lo aspettano gia' pubblicati sul bus
- Ritardo configurabile contro i falsi negativi del GPS
      (`presenza.ritardo_uscita_secondi`, due minuti per difetto). Vale **solo
      per le uscite**: chi torna a casa vuole la luce accesa adesso, e un
      falso rientro non spegne niente a nessuno

#### Cosa resta, e dove

Due caselle non sono state fatte qui perche' appartengono altrove, e
lasciarle mezze fatte sarebbe stato peggio che dichiararlo:

- I **trigger nell'editor di routine** hanno bisogno che i trigger esistano.
  Oggi una routine si attiva a voce o a mano; il motore di regole (issue #27,
  v0.4.0) e' il lavoro che introduce «quando succede X». Gli eventi di
  presenza sono gia' sul bus e lo aspettano.
- Il **collegamento al profilo** — «l'assistente sa con chi parla senza
  chiederlo» — non si ottiene dalla presenza. Sapere chi c'e' in casa non e'
  sapere chi ha parlato: con due persone presenti non disambigua, e con una
  sola sarebbe un'euristica che sbaglia in silenzio proprio quando conta di
  piu'. Serve il riconoscimento di chi parla (issue #34), e la presenza gli
  fara' da complemento.

### #23 — feat(sicurezza-casa): allarme, aperture e notifiche di intrusione

*tipo: funzione, area: core*

#### Contesto

Nessuna gestione dell'allarme, delle serrature come sistema, delle telecamere o
dei sensori di apertura. E' il dominio piu' importante fra quelli scoperti,
perche' e' quello per cui una famiglia installa la domotica.

#### Cosa fare

- Tool per `alarm_control_panel`: arma in casa, arma fuori casa, disarma,
      stato. Il codice della centrale si puo' passare e arriva a Home
      Assistant, che lo verifica
- Stato aggregato delle aperture. Home Assistant non ha un dominio
      «aperture»: porte e finestre sono `binary_sensor` con una
      `device_class`, le tapparelle sono `cover`, e `on` per un sensore di
      movimento non vuol dire aperto
- Controllo di coerenza all'armamento: rifiuta, dice quale finestra, e si
      puo' forzare dopo che la persona ha confermato
- Notifica all'intrusione — **l'evento c'e', il canale no.** Le notifiche
      push verso il telefono sono la issue #29 (v0.4.0) e non esistono
      ancora: fingere il contrario sarebbe la peggiore delle promesse, su
      questo dominio. `casa.intrusione` viene pubblicato sul bus con dentro
      chi c'era in casa al momento. **Nessuno lo ascolta**, nemmeno il
      WebSocket della dashboard: questa scheda diceva il contrario, ed era
      sbagliato. Lo aggancia la #29
- Simulazione di presenza in vacanza. Il piano di ogni sera e' calcolato
      da `domain/simulazione.py` — puro, riproducibile da un seme, e con il
      confronto esplicito con la sera prima. La capacita' sta in
      `skills/simulazione.py`; l'unica parte che reagisce da sola, spegnersi
      appena qualcuno rientra, e' in `services/simulazione.py` e ascolta
      `casa.abitata` senza sapere chi lo pubblica. Il modo di accorgersi che
      la vacanza e' finita e' la presenza (#22): rifiuta di partire con
      qualcuno in casa, e smette da sola al rientro
- Il disarmo passa da `sicurezza.comanda`, imposto dal client di Home
      Assistant su ogni chiamata, e ogni rotta richiede una sessione valida.
      Da Alexa serve una conferma in piu' — con il limite scritto nel codice:
      una conferma parlata non protegge da chi e' gia' nella stanza a
      parlare, e la protezione vera resta il codice della centrale

### #24 — feat(energia): consumi, costi e fasce orarie italiane

*tipo: funzione, area: core*

#### Contesto

Nessun monitoraggio dei consumi, nessuna nozione di costo, nessuna conoscenza
delle fasce F1, F2 e F3. E' il caso d'uso domestico italiano piu' concreto e il
meno servito dagli assistenti commerciali, che non conoscono la tariffazione
bioraria.

E' anche il fondamento della funzione «consulente energetico» prevista dopo la 1.0.0.

#### Cosa fare

- Lettura dei sensori di energia da Home Assistant, per dispositivo dove
      disponibile. Solo i contatori (`device_class: energy` con `state_class`
      cumulativa): un sensore di potenza dice quanti watt assorbe adesso, e
      sommarlo darebbe un numero senza significato
- Calcolo delle fasce F1, F2 e F3 secondo il calendario italiano, festivi
      inclusi. Pasquetta e' calcolata, non elencata: e' l'unico festivo
      nazionale mobile. E l'ora e' quella di Roma, non UTC — Home Assistant
      scrive in UTC, e una fascia calcolata li' sbaglia di un'ora d'inverno e
      di due d'estate, proprio nelle ore in cui le fasce cambiano
- Tariffa configurabile: monoraria, bioraria o trioraria. La bioraria mette
      F2 e F3 sotto lo stesso prezzo, come i contratti italiani. Senza tariffa
      configurata si risponde lo stesso, ma dichiarando che e' una stima
- Storicizzazione sul database. Si conservano le **letture grezze**, non i
      consumi gia' calcolati: le differenze si ricalcolano, le letture perdute
      no. La fascia invece si scrive, perche' ARERA puo' cambiare gli orari e
      una bolletta di due anni fa deve restare divisa come lo era allora
- Risposte a «quanto ho consumato oggi», «quanto mi costa tenere acceso
      questo», «in che fascia siamo adesso»: `consumo_energia`,
      `costo_dispositivo`, `fascia_corrente`
- Riepilogo per giorno, settimana e mese, con la fascia in cui si e'
      consumato di piu' — che e' l'unica cosa su cui una persona puo' agire.
      Il dettaglio per singolo carico c'e' quando c'e' un contatore per
      dispositivo: senza, si dice invece di ripartire a caso

### #25 — feat(casa): liste condivise, calendario e scadenze di manutenzione

*tipo: funzione, area: core*

#### Contesto

Tre entita' semplici che poggiano tutte sul database della v0.2.0 e che oggi
mancano del tutto:

- **Liste condivise.** Nessuna lista della spesa o delle cose da fare, benche' il sistema conosca gia' i profili della famiglia.
- **Calendario.** Nessuna agenda: «cosa ho oggi» non ha risposta.
- **Manutenzione.** Nessuna scadenza: filtri della caldaia, revisione, bollo, garanzie.

#### Cosa fare

- Liste condivise con voci, autore, stato; aggiunta e lettura a voce.
      «Latte, pane e uova» sono tre voci, e una voce gia' presente non si
      aggiunge due volte: al supermercato due righe uguali si comprano due volte
- Integrazione con le entita' `todo` dove presenti — e **delega, non copia.**
      Dove c'e' una lista `todo` si scrive li' e si legge di li'; le tabelle di
      casa restano vuote. Una copia sincronizzata sarebbe due verita' che
      divergono al primo conflitto, e una lista della spesa sbagliata e' peggio
      di nessuna lista
- Calendario: lettura da tutte le entita' `calendar`, sommate agli eventi di
      casa. **Si leggono tutti, si scrive solo su quello di casa:** i calendari
      di Home Assistant sono di Google o iCloud, e una casa che scrive
      nell'agenda di lavoro di qualcuno fa un danno che non sa di fare
- Scadenze ricorrenti con promemoria automatico. La prossima si conta **da
      quando e' stata fatta**, non dalla data prevista: altrimenti ogni ritardo
      si accumula e un cambio filtri fatto in ritardo tiene il calendario
      indietro per sempre
- Documento collegato a una scadenza — **come riferimento, non come file.**
      Dove sta la garanzia, il numero della fattura, un percorso. Conservare gli
      allegati vuol dire caricamento, spazio disco e backup: e' una funzione sua,
      e prometterla qui con un campo di testo sarebbe peggio che non averla

### #26 — fix(config): collegare le impostazioni esposte e mai lette

*tipo: difetto, area: core, gravita': media*

#### Contesto

Nove elementi che l'interfaccia o la configurazione espongono come funzionanti,
e che **nessuna riga di codice consuma**. Non producono errori: producono
silenzio, il che li rende peggiori di un difetto visibile.

| Elemento | Cosa succede davvero |
| :--- | :--- |
| `data/sources.json` | Gestore fonti RSS completo, con catalogo di venti testate e toggle di massa. `news_search.py` usava un dizionario scritto nel codice e non chiamava mai `get_sources()`. Disattivare ANSA Politica non cambiava nulla. *(Risolto da questa issue)* |
| `preferred_news_categories` | Salvato per ogni utente, mai letto. Il briefing notizie era identico per tutti. *(Risolto da questa issue)* |
| `restricted_topics` | Mai letto. Nessun filtro sui contenuti per i minori. *(Risolto in v0.1.0 dalla issue #08)* |
| `alexa.skill_id` | Mai letto. *(Risolto in v0.1.0 dalla issue #04)* |
| `alexa_media_player_entity` e `speak_on_alexa()` | La funzione e' definita in `ha_client.py` e non viene chiamata da nessuno: l'assistente non puo' parlare spontaneamente su un Echo. *(Collegato in v0.2.0 dalla issue #11)* |
| `security.session_secret` | Mai letto. *(Risolto in v0.1.0 dalla issue #06)* |
| `duckduckgo-search` | Dipendenza mai importata. *(Rimossa in v0.1.0 dalla issue #10)* |
| `memory.add_tool_interaction` | Corpo `pass`. *(Implementato in v0.2.0 dalla issue #13)* |
| Domini `lock`, `vacuum`, `fan` | Visibili e non comandabili. *(Risolto dalla issue #20)* |

Questa issue chiude i due elementi rimasti e introduce il controllo che impedisce
che il fenomeno si ripeta.

#### Cosa fare

- `get_latest_news` legge le fonti dal database, rispettando lo stato
      attivo/disattivo e la categoria. `search_web` **no, e non deve**: e' una
      ricerca su una domanda libera, non la lettura di un feed, e non c'e'
      niente da filtrare. Fingere il contrario avrebbe aggiunto un'altra
      opzione senza effetto, che e' il difetto che questa scheda chiude
- Il briefing notizie filtra su `preferred_news_categories` del profilo che ha posto la domanda
- Il test c'e' (`test_ogni_opzione_di_configurazione_ha_un_consumatore`) e alla
      prima esecuzione ha trovato due opzioni che nessun elenco scritto a mano
      aveva notato: `assistant.language` e `security.protect_dashboard`
- Tolte tutte e due. `assistant.language` tornera' con la
      internazionalizzazione (issue #36), che e' il lavoro che la rende vera.
      `security.protect_dashboard` aveva perfino una casella nelle
      impostazioni mentre la rotta rispondeva `True` fisso: prometteva di
      poter *disattivare* la protezione della dashboard, cioe' di riaprire il
      difetto SEC-03 chiuso nella v0.1.0. Un'opzione del genere non va
      collegata, va tolta


## 0.4.0 — Proattività

### #27 — feat(automazioni): motore di regole con trigger su evento, stato e orario

*tipo: funzione, area: core, gravita': alta*

#### Contesto

Il sistema e' puramente reattivo: risponde soltanto quando gli si parla. Le
"modalita'" esistenti sono sequenze di azioni, non automazioni: si attivano solo
con una frase.

Con lo scheduler (issue #11) e gli eventi Home Assistant (issue #19) disponibili,
mancano solo i trigger.

#### Cosa fare

- Modello di regola: trigger, condizioni, azioni. In JSON e non in colonne:
      le forme cambiano a ogni tipo di trigger nuovo, e una tabella che cambia
      forma a ogni tipo nuovo e' una migrazione a ogni tipo nuovo
- Trigger su evento, stato, orario, presenza, alba e tramonto. **Su stato,
      quello che conta e' l'attraversamento, non lo stare sotto:** «avvisami se
      scende sotto i 15» detto a una casa a 12 gradi non deve suonare a ogni
      lettura del sensore. La differenza e' un avviso al giorno contro trecento,
      e trecento avvisi al giorno diventano zero avvisi letti
- Condizioni componibili: fascia oraria, giorni della settimana, presenza,
      stato di un'entita'. La fascia scavalca la mezzanotte, perche' «dalle 23
      alle 6» e' la finestra piu' usata in una casa ed e' quella che un confronto
      ingenuo sbaglia sempre
- Riuso del grafo: un'azione di tipo `modalita` chiama `activate_mode`. Le
      altre due sono un servizio diretto e un avviso — quest'ultimo possibile
      solo dopo la #29
- Protezione contro i cicli. Si guarda **la catena** e non solo un contatore
      di profondita', perche' il messaggio possa dire quali regole formano
      l'anello: «una regola ha creato un ciclo» manda a rileggerle tutte
- Registro di ogni attivazione — **e di ogni rifiuto**, con il motivo. Una
      regola che non scatta mai e una regola rotta si somigliano troppo

#### Tre guardiani, tre cose trovate

**Il ratchet d'architettura** ha bocciato la rotta di prova, che leggeva da
`infra.db`: sarebbe stata la tredicesima voce di `api -> infra`. Adesso passa
dal motore.

**Il test che confronta migrazioni e modelli** ha trovato che le tre colonne
JSON erano `nullable=True` nella migrazione e non-nullable nei modelli. Non e'
un dettaglio: uno schema che diverge dai modelli e' il difetto che si scopre
al primo errore in casa, mesi dopo.

**Il controllo di mutazione** ha trovato due buchi nei test:

- togliendo la guardia su «non so chi c'e' in casa», la funzione rispondeva
  comunque «no» ma con la frase sbagliata — «in casa non c'e' nessuno» detto
  quando non lo si sa e' un'affermazione, non un'ammissione;
- togliendo l'annotazione del rifiuto sulla regola, la suite passava lo
  stesso, perche' l'unico test che la guardava usava la strada
  dell'esecuzione riuscita.

### #28 — feat(canvas): nodi condizione e trigger temporale nell'editor a grafo

*tipo: funzione, area: frontend*

#### Contesto

L'editor visuale a nodi e' il pezzo migliore del progetto, ma supporta solo
quattro tipi di nodo: innesco vocale, dispositivo, ritardo e annuncio vocale.
Il flusso e' quindi sempre lineare: nessuna diramazione, nessuna condizione.

Il motore di esecuzione fa gia' una visita in ampiezza sul grafo con calcolo dei
gradi entranti: la struttura per i rami c'e' gia'.

#### Correzione: l'editor non salvava niente, e i cavi non si potevano tirare

*Aggiunto il 2026-09-10, lavorando alla scheda.*

Prima di aggiungere un nodo qualunque sono venuti fuori **due difetti che
rendevano vano tutto il resto**, ed entrambi erano invisibili perche' il primo
nascondeva il secondo:

1. **Le colonne `nodes` ed `edges` non esistevano nella tabella delle
   routine.** L'editor le mandava al salvataggio, il deposito copiava solo i
   campi che conosceva, e il disegno spariva — senza errori, senza avvisi. Di
   conseguenza l'esecutore non ha **mai** visto un grafo in produzione: le sue
   novanta righe di visita in ampiezza erano codice irraggiungibile.
2. **`port-pin` non aveva nessuna CSS** e non e' una classe di Tailwind: i
   pin dei cavi erano `div` a dimensione zero, quindi invisibili e non
   cliccabili. Nell'editor non si e' mai potuto collegare due nodi.

Il secondo non si notava perche' il primo veniva prima: anche riuscendo a
tirare un cavo, il disegno non sarebbe sopravvissuto al salvataggio.

#### Cosa fare

- Nodo condizione con due uscite (vero e falso)
- Nodo trigger temporale: a un orario, all'alba, al tramonto
- Nodo trigger su evento e su stato, collegato al motore della issue #27
- Nodo notifica, distinto dall'annuncio vocale
- Simulazione che mostri quale ramo viene percorso
- Validazione del grafo prima del salvataggio: nodi scollegati, cicli, rami senza uscita
- **Salvare il grafo** (vedi sopra: non succedeva)
- **Rendere collegabili i nodi** (vedi sopra: i pin erano invisibili)

Un trigger **a intervalli** («ogni venti minuti») non c'e' e non e' una
dimenticanza: il motore della #27 non ha quel tipo di trigger, e aggiungerlo
qui vorrebbe dire aggiungerlo li' — e' lavoro della #27, non di questa scheda.

#### Da verificare in casa

- Aprire l'editor, trascinare due nodi e collegarli: prima di questa
      versione il cavo non partiva.
- Salvare, chiudere, riaprire: il disegno deve essere ancora li'.
- Aggiungere una condizione, collegare entrambe le uscite ed eseguire la
      routine con la condizione vera e poi falsa.
- Premere «Simula Flusso» con una condizione nel mezzo: deve accendersi
      **un ramo solo**, e sotto la condizione deve comparire il perche'.
- Mettere un innesco al tramonto, salvare, e la sera guardare se la
      routine parte. E' l'unica prova che conta.
- Togliere quell'innesco, risalvare, e verificare la sera dopo che **non**
      parte piu'.

### #29 — feat(notifiche): web push verso la PWA

*tipo: funzione, area: frontend, area: infra*

#### Contesto

`web/static/sw.js` esiste e gestisce installazione, attivazione e cache, ma
**non ha alcun handler per l'evento `push`**. Il sistema non puo' raggiungere
l'utente quando l'applicazione non e' aperta: promemoria, allarmi, avvisi
energetici e check-in restano tutti muti.

#### Cosa fare

- Generazione delle chiavi VAPID e gestione delle sottoscrizioni per utente
      e dispositivo. Le chiavi si generano una volta e **non si rigenerano mai da
      sole**: cambiarle invalida in silenzio tutte le sottoscrizioni, e una casa
      che smette di avvisare senza dirlo e' peggio di una che non ha mai avvisato
- Handler `push`, `notificationclick` e **`pushsubscriptionchange`** nel
      service worker. Il terzo non era chiesto ed e' il modo piu' comune in cui
      le notifiche «smettono di funzionare da sole»: il servizio push revoca una
      sottoscrizione, ne da' una nuova, e senza handler il telefono tace
- Servizio di notifica unificato con instradamento per canale. **E qui si e'
      scoperto che `casa.intrusione` non arrivava da nessuna parte** — nemmeno
      alla dashboard aperta, che le note della `v0.3.0` davano per scontata
- Preferenze per utente: quali categorie, quali canali, e un silenzioso
- Priorita'. **Non e' un'etichetta, e' un permesso:** se il silenzioso potesse
      spegnere un allarme, sarebbe un modo per spegnere l'allarme
      dimenticandosene

#### Sulla privacy, perche' «push» suona peggio di com'e'

Il browser si registra presso il **suo** servizio push — Google per Chrome,
Mozilla per Firefox, Apple per Safari — e ci consegna un indirizzo e due
chiavi. Il messaggio viene cifrato **qui** con quelle chiavi: il servizio push
instrada una busta che non puo' aprire. Un promemoria di casa passa da Google
senza che Google sappia cosa dice.

### #31 — feat(voce): riconoscimento vocale locale al posto della Web Speech API

*tipo: funzione, area: core, area: sicurezza, gravita': alta*

#### Contesto

Il riconoscimento vocale usa la Web Speech API del browser, che **invia l'audio
ai server di Google**.

Il README dichiara «Zero Cloud per i Dati Privati» e «100% privata». Oggi il
modello resta in casa e la sintesi vocale passa da Microsoft Edge TTS, ma
**ogni parola pronunciata all'assistente viene inviata a Google**. E' la
contraddizione piu' netta fra cio' che il progetto promette e cio' che fa.

#### Cosa fare

- Integrare faster-whisper lato server, con modello configurabile per bilanciare velocita' e precisione
- Endpoint di trascrizione che riceve l'audio dal browser
- Mantenere la Web Speech API come alternativa esplicita, disattivata per difetto e con un avviso chiaro su cosa comporta
- Valutare Piper come sintesi vocale locale, per chiudere anche l'ultimo servizio esterno — *valutata e rimandata, vedi sotto*
- Aggiornare il README perche' descriva esattamente cosa resta locale e cosa no

#### Da verificare in casa

Il codice e' provato; il modello vero su una CPU vera no.

- Installare il motore sul server:
      `sudo -u shinra /opt/Shinra/.venv/bin/pip install "faster-whisper>=1.0"`
      e riavviare il servizio. Il primo comando parlato scarica il modello e
      puo' volerci qualche minuto.
- Misurare la latenza di una frase breve («accendi la luce della cucina»)
      con il modello `base`. Se e' troppo lenta, provare `tiny`; se sbaglia i
      nomi di casa, provare `small`. La scelta si scrive in `voce.modello`.
- Verificare che il microfono, con il servizio **senza** faster-whisper,
      dica cosa installare invece di non fare niente.
- Verificare che parlare al vuoto non faccia partire una richiesta: la
      dashboard deve rispondere «non ho sentito niente».

### #32 — feat(conoscenza): recupero per similarita' al posto dell'iniezione totale

*tipo: funzione, area: core*

#### Contesto

`get_enabled_knowledge_summary()` concatena **tutti** i fatti abilitati e li
inietta nel prompt di sistema a ogni richiesta. Con la Modalita' Apprendimento
funzionante (v0.1.0) la conoscenza crescera' rapidamente, e il contesto cresce
linearmente con essa: prima si paga in latenza, poi si satura la finestra e i
fatti piu' vecchi vengono silenziosamente troncati.

Il problema e' aggravato dalla configurazione attuale, che imposta `num_ctx` a
1024 o 2048 token.

#### Cosa fare

- Calcolo degli embedding tramite Ollama, quindi **in casa**. Un servizio nel
      cloud sarebbe piu' veloce e migliore, e vorrebbe dire mandare a qualcun
      altro il nome del gatto e dove si nasconde la chiave di scorta
- Recupero dei soli fatti pertinenti, con soglia e numero massimo. **Sotto i
      venticinque fatti si manda tutto**, come si e' sempre fatto: il problema
      esiste a duecento fatti, non a venti, e un recupero imperfetto dove non
      serviva farebbe perdere risposte che prima funzionavano
- Ricalcolo alla modifica, **senza doverlo chiedere**: accanto al vettore si
      salva l'impronta del testo, e se non corrisponde il vettore e' vecchio. Un
      vettore vecchio non da' errore, da' risposte sbagliate
- Ricerca ibrida. I vettori sbagliano proprio dove fa male: avvicinano «la
      password del wifi» a «la chiave della rete» — ed e' cio' che serve — ma
      appiattiscono «4471» e «4417» sullo stesso punto, perche' semanticamente
      sono entrambi «un numero». I numeri pesano doppio nella meta' testuale
- `GET /api/conoscenza/fatti-usati` dice quali fatti hanno contribuito e con
      quale punteggio, semantico e testuale separati. Quando l'assistente dice
      una cosa strana, la prima domanda e' «da dove l'ha presa»

### #33 — feat(canali): satelliti vocali per stanza

*tipo: funzione, area: integrazioni*

#### Contesto

L'unico punto di ascolto vocale distribuito e' Amazon Echo, cioe' un servizio
cloud di terze parti. Con parola di attivazione (issue #30) e riconoscimento
locale (issue #31) disponibili, un dispositivo da poche decine di euro per
stanza diventa l'alternativa aperta.

#### Cosa e' cambiato rispetto al piano

*Aggiunto l'11 settembre 2026, lavorando alla scheda.*

La scheda presupponeva hardware — un Raspberry per stanza — che non c'e'.
Lavorandoci e' venuto fuori che **il pezzo che conta non e' il microfono**:
il telefono e il portatile un microfono ce l'hanno gia'. Quello che manca e'
che la casa sappia **da dove** arriva la frase.

Quindi la dashboard aperta in cucina e' diventata un satellite. Non e' un
ripiego in attesa del Raspberry: e' la stessa cosa con un involucro diverso,
e il giorno in cui arrivera' un dispositivo dedicato parlera' lo stesso
protocollo.

#### Cosa resta, e va in v0.5.0

- **Immagine di riferimento per Raspberry Pi** con microfono e
      altoparlante. Serve l'hardware per scriverla e per provarla: un'immagine
      mai avviata e' un file che sembra una soluzione.
- **Compatibilita' con Wyoming**, il protocollo gia' usato
      dall'ecosistema Home Assistant. Vale la pena farlo *invece* di un
      protocollo proprietario, ma conviene farlo quando c'e' un satellite
      vero con cui provarlo: oggi si scriverebbe contro una specifica, non
      contro un dispositivo.

Il registro dei satelliti sta **in memoria**, e per adesso e' giusto cosi':
un elenco salvato su disco sopravviverebbe ai dispositivi spenti, cioe'
manderebbe risposte in stanze vuote. Quando i satelliti saranno dispositivi
fissi, la scelta andra' rivista.

#### Da verificare in casa

- Apri la dashboard sul telefono, scrivi «Cucina» sotto il microfono, e
      chiedi «accendi la luce»: deve accendersi quella della cucina. Servono
      alias con la stanza compilata nella Mappa Dispositivi.
- Ripeti dal portatile dichiarando «Salotto»: la stessa frase deve
      accendere un'altra luce.
- Senza dichiarare nessuna stanza, «accendi la luce» deve **chiedere
      quale** invece di accenderne una.
- Con due dispositivi aperti nella stessa stanza, mandare la stessa frase
      da entrambi entro un paio di secondi: deve eseguirsi una volta sola.

### #48 — feat(sicurezza): passkey al posto del PIN, e riconoscimento di chi parla

*tipo: funzione, area: sicurezza*

#### Contesto

Due buchi rimasti aperti per scelta, entrambi documentati in
[ADR 0004](adr/0004-identita-ruoli-e-permessi.md).

**Il PIN e' cio' che si puo' digitare.** Un bambino che guarda le dita di un
adulto impara il PIN in due giorni. Una passkey no: la credenziale sta nel
dispositivo e si sblocca con impronta o riconoscimento del volto. Non c'e'
niente da indovinare e nessuno puo' usare il telefono di un altro.

**Il canale vocale non sa chi parla.** Fino a qui, chiunque si rivolga a un
Echo agisce con l'identita' della sessione: i permessi della `v0.2.0` non
proteggono la voce. E' il motivo per cui `sicurezza.comanda` resta fuori dal
canale vocale.

#### Correzione: il buco era piu' largo di come l'avevamo scritto

*Aggiunto il 2026-09-10, dopo averlo misurato invece che ricordato.*

La frase qui sopra e nell'ADR 0004 dice «agisce con l'identita' della
sessione». Non era vero: il canale Alexa non impostava **mai** l'attore, e
`ha_permesso(None, ...)` concede tutto perche' `None` significa «nessuna
identita' in gioco». A voce **nessun permesso e' mai stato verificato**. Due
divieti scritti a mano nelle capacita' erano l'unica cosa che reggeva.

Con lo stesso ceppo sono venuti fuori altri due difetti: `LaunchRequest`
impostava la sessione sul primo profilo dell'elenco (l'amministratore) e lo
salutava per nome a chiunque; «sono Sonia» cambiava profilo senza nessuna
prova. Dettagli e conseguenze nell'[ADR 0004](adr/0004-identita-ruoli-e-permessi.md#aggiornamento--il-buco-vocale-era-piu-largo-di-come-lavevamo-scritto).

#### Cosa fare

- WebAuthn: registrazione e accesso con passkey
- Piu' passkey per utente, una per dispositivo, revocabili singolarmente
- Passkey come metodo consigliato, PIN mantenuto come ricaduta
- Profili vocali Alexa: leggere l'identificativo della persona dalla
      richiesta e risolverlo nel profilo Shinra corrispondente
- Se la voce non e' riconosciuta, si applicano i permessi del profilo
      ospite, non quelli dell'amministratore
- Togliere il cambio di profilo parlato: un'identita' che si ottiene
      dicendola rende priva di senso ogni riga scritta sui permessi vocali
- Estendere il riconoscimento ai satelliti vocali (issue #33)
- Sbloccare `sicurezza.comanda` da voce **solo** con identita' riconosciuta
      e conferma esplicita

#### Da verificare in casa

Il codice e' provato; l'impianto vero no, e le due cose non coincidono.

#### Passkey

- Raggiungere la dashboard con un **nome** e in **HTTPS**: senza, la
      sezione Passkey dice che non sono disponibili, ed e' corretto.
- Impostazioni → Passkey → Aggiungi, e confermare con impronta o volto.
- Uscire e rientrare con «Entra con una passkey», senza digitare il PIN.
- Revocarla e verificare che il pulsante non la offra piu'.
- Verificare che il PIN continui a funzionare in ogni momento.

#### Voce

- Configurare i profili vocali dall'app Alexa (Impostazioni → Il tuo
      profilo → Voce). Shinra non puo' farlo al posto di nessuno: senza,
      **tutte** le voci restano sconosciute — che e' il comportamento giusto,
      ma non e' quello che si vuole tutti i giorni.
- Parlare a un Echo e verificare che la voce compaia in Impostazioni →
      Voci Riconosciute, non associata.
- Associarla al proprio profilo e riprovare ad aprire una serratura a
      voce: dovrebbe chiedere conferma e poi aprire.
- Farla provare a qualcun altro non associato: dovrebbe rifiutare
      spiegando come farsi riconoscere.


## 0.5.0 — Prodotto

### #123 — refactor(interfaccia): la colonna della console racconta adesso, non la diagnostica

*tipo: attivita', area: frontend*

#### Contesto

La console vocale e' la schermata che si apre per prima, e la sua colonna di
destra — un terzo dello schermo, sempre acceso — contiene:

- **Stato Sistema**: il nome del modello (`llama3.2:1b`) e la frase di
  invocazione di Alexa;
- **Tool invocati da Shinra**: l'elenco delle chiamate interne;
- **Timer & Promemoria live**.

Solo l'ultimo riguarda chi abita la casa. Gli altri due sono diagnostica:
utili a chi costruisce l'hub, rumore permanente per chi lo usa. Il modello non
cambia da un'ora all'altra, e la frase di invocazione si legge una volta nella
vita.

#### Cosa fare

- Spostare modello e invocazione Alexa in Impostazioni, dove si va quando si vogliono cambiare
- Rendere i tool invocati una finestra da aprire quando qualcosa non torna, non un pannello acceso
- Lasciare nella colonna cio' che riguarda **adesso**: timer e promemoria attivi, cosa sta facendo la casa, cosa scattera' fra poco (il prossimo scatto lo sa gia' `/api/regole`)
- Mantenere raggiungibile tutto: nessun dato sparisce, cambia dove si guarda

#### Com'e' andata

Fatta con la PR #132.

**Un criterio non e' stato raggiunto, ed e' scritto nella guardia.** Il calo
degli elementi a riposo nella colonna e' del **30%**, non di un terzo: 27 tag
diventati 19. Non poteva esserlo — la scheda chiedeva insieme di *togliere* la
diagnostica e di *aggiungere* i prossimi scatti. Gli altri numeri: titoli da 3
a 1, pannelli accesi da 3 a 2, informazioni di diagnostica da 3 a nessuna.
`test_la_colonna_della_console_resta_leggera` tiene il tetto misurato.

Trovato strada facendo: la frase di invocazione di Alexa nella console era
**scritta a mano** e restava «Kyra» anche dopo averla rinominata. Adesso viene
dal campo.

### #124 — refactor(interfaccia): Impostazioni a sezioni, aperta solo quella che serve

*tipo: attivita', area: frontend*

#### Contesto

La scheda Impostazioni e' **421 righe di markup**: 19 campi, 15 pulsanti, 9
pannelli, 11 titoli, tutti aperti contemporaneamente. Pesa quanto le altre
sette schede messe insieme.

Non e' una schermata da leggere, e' una schermata in cui si cerca — e cercare
in un muro aperto e' piu' lento che aprire la sezione giusta.

#### Cosa fare

- Trasformare i nove pannelli in sezioni richiudibili, chiuse per difetto tranne la prima
- Ogni sezione dice in una riga cosa contiene, anche da chiusa
- Ricordare quale sezione era aperta, per chi torna a sistemare la stessa cosa
- Accogliere qui cio' che arriva dalla console: modello e invocazione Alexa

#### Com'e' andata

Fatta con la PR #138. I pannelli erano otto, non nove.

Misurato a scheda appena aperta: **17 campi visibili diventati 0**, 7 pulsanti
diventati 1 — quello che salva. Lo zero non e' un trionfo: la prima sezione e'
la scelta della palette, che si fa con delle carte e non con dei campi. I
diciassette restano tutti a un clic, e una guardia lo verifica leggendo gli
identificativi che la pagina cerca davvero.

Modello e invocazione Alexa erano gia' arrivati qui con la #123.

Due difetti trovati guardando la schermata: l'icona `house` non esiste in
lucide 0.344.0, e le carte delle palette erano grigio scuro su bianco perche'
`bg-slate-900/50` non era fra le riscritture del tema chiaro — la guardia dei
colori salta apposta la famiglia `slate`. Adesso c'e' anche la sorella per i
grigi.

### #125 — fix(interfaccia): le chiamate all'API partono senza le intestazioni di autenticazione

*tipo: difetto, area: frontend, gravita': alta*

#### Contesto

Ventisette chiamate su settantatre, in `web/templates/index.html`, partono
senza `getAuthHeaders()`. Fra queste: `/api/regole`, `/api/modes`,
`/api/timers`, `/api/reminders`, `/api/aliases`, `/api/sources`,
`/api/settings`, `/api/status`.

Funzionano sul computer di casa perche' quel browser e' un dispositivo fidato
e il riconoscimento passa dal cookie (`sessione_dalla_richiesta` ha quella
seconda strada). Su un browser non ancora fidato — il telefono di un ospite,
una finestra anonima, la PWA appena installata — quelle rotte rispondono 401.

E il 401 non si vede. Il codice fa:

```js
const dati = await res.json();
renderRegole(dati.regole || []);
```

Un corpo `{"detail": "..."}` diventa `[]`, e la schermata mostra «non c'e'
niente» invece di «non ho il permesso di vederlo». Sono due cose diverse che
oggi hanno lo stesso aspetto in una decina di schermate — ed e' la stessa
famiglia del difetto del microfono chiuso con la #113: la rotta era giusta,
mancava un'intestazione.

#### Cosa fare

- Aggiungere `getAuthHeaders()` a tutte le chiamate che ne sono prive, tranne `/api/auth/profili` e `/api/auth/login`, che per definizione precedono la sessione
- Rendere visibile un rifiuto: una chiamata che torna 401 o 403 deve dirlo nella schermata, non lasciare una lista vuota
- Guardia: ogni `fetch` verso `/api/` porta le intestazioni, salvo le due eccezioni dichiarate per nome

#### Com'e' andata

Fatta con la PR #130.

Ventisette chiamate `fetch` verso `/api/` partivano senza intestazioni. La
guardia `test_ogni_chiamata_api_della_pagina_porta_le_intestazioni` dichiara
per nome le due eccezioni che precedono la sessione.

### #126 — feat(automazioni): una scorciatoia per «a quest'ora fai questo»

*tipo: funzione, area: frontend*

#### Contesto

`POST /api/regole` esiste dalla v0.3.0 e **la dashboard non la chiama mai**.
L'unico modo di creare un'automazione e' aprire l'editor a nodi, disegnare una
routine e cambiare il tipo di innesco del primo blocco.

Per «alle 23 spegni tutto» — fra le richieste piu' frequenti di una casa — e'
un giro lungo. Per tutto il resto l'editor e' insostituibile.

#### Cosa fare

- Un modulo breve in «Automazioni e routine»: quando (orario, alba, tramonto, stato, evento), cosa fare, e basta
- Usare `POST /api/regole`, che ha gia' la sua validazione: un innesco sconosciuto viene rifiutato con il motivo
- Il rifiuto del server si legge nella schermata, non in un `alert`
- Un collegamento «serve qualcosa di piu' complicato?» che apre l'editor con quell'innesco gia' impostato
- Le regole nate cosi' sono indistinguibili dalle altre nell'elenco: stessa riga, stesso prossimo scatto, stessa prova

#### Com'e' andata

Fatta con la PR #140.

Il test di accettazione manda alla rotta vera il corpo che il modulo
manderebbe, costruito **eseguendo le sue funzioni** invece di riscriverle, e
controlla che la regola compaia nell'elenco con il prossimo scatto alle 23 e
l'azione sul dispositivo giusto.

**Provando a rompere la scorciatoia e' saltato fuori un difetto del server**:
un'azione su un dispositivo senza entita' veniva accettata, scattava, chiamava
il servizio su una stringa vuota e tornava «riuscita». L'elenco diceva «ultima
volta: riuscita» e la luce restava accesa. `_valida` applica adesso lo stesso
metro di «una regola senza azioni non fa niente» anche alle azioni che non
dicono su cosa agire.

### #127 — feat(interfaccia): ogni lista vuota insegna la mossa successiva

*tipo: attivita', area: frontend*

#### Contesto

La scheda Automazioni, quando non ci sono regole, mostra un titolo, un
pulsante «Aggiorna» e uno spazio bianco. Diciannove righe di markup in tutto,
di cui una e' il contenitore vuoto.

Il proprietario della casa ha guardato quella schermata e ha chiesto: «le
automazioni si creano da sole o no? non so come crearle». La risposta e' che
nascono da una routine con un innesco non vocale — e nessuna delle due
schermate lo dice.

**Una lista vuota che non insegna la mossa successiva e' indistinguibile da
una funzione rotta.** Vale per Automazioni, Modalita', Fonti, Dispositivi e
Conoscenza: cinque schermate, cinque silenzi identici.

#### Cosa fare

- Automazioni: «Non c'e' ancora nessuna automazione. Nascono dalle routine: creane una e dai al primo blocco un innesco che non sia la voce», con il pulsante che porta li'
- Automazioni: elencare sotto le routine a innesco vocale, dicendo che esistono ma partono solo se chiamate — e' l'informazione che oggi manca del tutto
- Modalita' e Routine, Fonti, Dispositivi, Conoscenza: uno stato vuoto ciascuno, che nomina l'azione successiva
- Guardia: ogni contenitore che puo' restare vuoto ha un ramo che scrive qualcosa

#### Com'e' andata

Fatta con la PR #131.

**La premessa della scheda era sbagliata, ed e' stato misurato.** «Cinque
schermate, cinque silenzi identici» non corrispondeva al vero: tutte le liste
che potevano restare vuote avevano gia' la loro frase, e lo stato vuoto delle
Automazioni aveva gia' una guardia dalla #108. La correzione e' scritta in un
commento sulla issue.

Cio' che mancava davvero era la seconda casella: le routine a innesco vocale
non comparivano da nessuna parte fra le automazioni, ed e' la domanda da cui
la scheda e' nata. Quella e' stata costruita.

La guardia `test_ogni_elenco_che_puo_restare_vuoto_dice_qualcosa` tiene il
resto, con sei eccezioni dichiarate con il loro motivo.

### #128 — refactor(interfaccia): da otto ingressi a tre, senza perdere niente

*tipo: attivita', area: frontend*

#### Contesto

Otto schede di primo livello, tutte dello stesso peso, ciascuna con
un'etichetta da due parole: Console Vocale, Conoscenza Casa, Fonti & Notizie,
Mappa Dispositivi, Modalita' & Routine, Automazioni, Gestione Utenti,
Impostazioni. Una riga che riempie tutta la larghezza e chiede di essere letta
per intero ogni volta.

Ma non sono la stessa cosa. Tre si usano ogni giorno; cinque si usano una
volta e poi mai piu'. Trattare «parla alla casa» e «configura le fonti RSS»
come voci gemelle e' la scelta che genera piu' affaticamento di qualunque
altra.

#### Cosa fare

- Primo livello: **Console**, **Automazioni e routine**, **Dispositivi**
- Dietro un solo ingresso di configurazione: Conoscenza, Fonti, Utenti, Impostazioni
- Unire in un ingresso solo l'elenco delle automazioni e il costruttore di routine

#### Com'e' andata

Fatta con la PR #133.

Nessuna funzione si e' allontanata di piu' di **un** clic; il criterio ne
ammetteva due.

Due cose che si sarebbero rotte in silenzio: le vecchie destinazioni
`switchTab('modes')` e `switchTab('regole')`, tradotte in un posto solo invece
di portare a una schermata bianca; e «vai alle routine», che cambiava scheda e
adesso che la scheda e' la stessa scorre.

**Un difetto e' sfuggito a tutte le nove guardie**: `overflow-x-auto` sulla
barra ritagliava il menu di configurazione. Le guardie leggono il sorgente e
nessuna puo' vedere un elemento tagliato dal CSS di un antenato. Trovato
guardando la schermata, riparato con la #134.

### #30 — feat(voce): parola di attivazione locale

*tipo: funzione, area: core*

#### Contesto

Non esiste alcuna parola di attivazione: bisogna premere il pulsante del
microfono oppure passare da Alexa. Un assistente domestico che richiede di
toccare uno schermo perde gran parte della propria ragione d'essere.

#### Cosa fare

- Integrare openWakeWord, che gira su CPU
- Parola personalizzabile, coerente con il nome scelto per l'assistente
- Soglia di sensibilita' regolabile
- Indicatore visivo di ascolto e possibilita' di disattivare il microfono, anche fisicamente
- Nessuna registrazione persistente dell'audio; l'audio prima dell'attivazione non lascia mai il dispositivo

### #34 — refactor(frontend): scomporre index.html in moduli ES

*tipo: attivita', area: frontend*

#### Contesto

`web/templates/index.html` e' un file unico di **4.657 righe** che contiene
markup, tutto il CSS, 126 funzioni JavaScript, l'editor a grafo, il catalogo
RSS, la gestione vocale e i modali. Non c'e' build, non c'e' linting, non c'e'
alcuna separazione.

Ogni modifica al frontend e' rischiosa perche' l'ambito di una variabile e'
l'intero file. E' il freno principale a ogni funzione nuova con interfaccia.

> Quando la scheda e' stata scritta il file era di 4.657 righe. Le sei voci
> dell'interfaccia (#123-#128) l'hanno portato a **7.438** prima che questo
> lavoro cominciasse.

#### Cosa fare

- Separare CSS e JavaScript in file propri — #144
- Separare il markup delle schede in template inclusi, uno per area — #176
- Suddividere il JavaScript per area: autenticazione, chat, voce,
      dispositivi, routine, canvas, timer, impostazioni — #145, #147, #151.
      Sono venti file, uno per area, ma sono ancora copioni classici caricati
      in ordine: **moduli ES veri no, non ancora**
- Sostituire lo stato globale sparso con un contenitore unico — #177
- Sostituire la generazione di HTML per concatenazione di stringhe, che
      oggi e' esposta a injection dai nomi delle entita' — #148, #149, #150,
      #151
- Aggiungere ESLint e Prettier alla CI — #146, #147
- Valutare un bundler leggero (Vite) mantenendo la possibilita' di servire
      senza build — **no**, e il perche' sta nell'[ADR 0006](adr/0006-niente-bundler.md): #178

#### A che punto siamo

Otto PR unite: **#144** (CSS e JS fuori da index.html), **#145** (un file per
area), **#146** (ESLint, che al primo giro ha trovato un difetto vero in
produzione: il pulsante «+ Timer» chiamava un nome che non e' mai esistito),
**#147** (Prettier), **#148** (il modello `_html` che scappa i valori, piu' la
chat), **#149**, **#150** e **#151** (le restanti diciotto aree, fino a
svuotare la lista delle eccezioni).

Misurato adesso:

| | prima | dopo |
| :--- | :-- | :-- |
| `web/templates/index.html` | 7.438 righe | un'ossatura di poche righe |
| File di markup | 1 | 10: l'ossatura e nove pezzi inclusi |
| File JavaScript | 1 (dentro l'HTML) | decine, nessuno oltre le cinquecento righe (con guardia) |
| File CSS | 1 (dentro l'HTML) | 5 |
| Concatenazioni di stringhe non protette | tutte | **zero**, con guardia |

Poi la **#176**, che ha spezzato anche il markup: `index.html` tiene il
`<head>`, l'ossatura e i collegamenti, e include nove pezzi — uno per scheda,
piu' l'intestazione e i modali. La pagina servita e' venuta fuori **identica
byte per byte** a quella di prima, il che era il punto: era un cambio di
struttura e non doveva cambiare niente altro.

Il criterio ancora aperto, e perche':

- **Nessuna regressione.** Due ne sono uscite dalla scomposizione, tutte e due
  trovate in casa e chiuse: il nodo che non si trascinava dall'intestazione
  (#154) e la crocetta che non staccava il cavo (#155). Da li' e' nata la
  #156, che fa girare in CI sette gesti veri dell'editor con un browser vero.
  La #152 e la #153 sono state chiuse (#164, #163), ma c'erano gia' prima.

Poi la **#177**, lo stato in un posto solo. Le variabili globali erano
quarantaquattro, ma solo **undici** attraversavano piu' di un file — e quelle
undici erano il difetto: `activeUserId` girava per cinque file, `_canvasState`
per quattro con ottanta riferimenti. Adesso sono campi di `Stato`, in
`web/static/js/stato.js`, ognuno con scritto accanto chi lo scrive e chi lo
legge. Le altre trentatre' sono rimaste dove stanno: le usa un'area sola, e
portarle li' avrebbe allungato l'elenco senza dire niente a nessuno.

Il contenitore toglie una protezione, e va detto: con le variabili sciolte,
`activeUserIdd` era un nome che nessuno dichiarava e `no-undef` fermava
ESLint; `Stato.utenteAttivoo` invece e' una proprieta' come un'altra, vale
`undefined` e non solleva niente. La rimette
`test_ogni_campo_dello_stato_esiste_davvero`, che i campi li legge dal
contenitore e gli usi da tutto il frontend.

Poi la **#178**, che decide la forma del lavoro rimasto:
[ADR 0006](adr/0006-niente-bundler.md), **niente bundler**. I moduli
saranno nativi, serviti come stanno sul disco. Le tre cose che un bundler
avrebbe dato non servono qui — tutto il JavaScript sta in 68 KB compressi,
ventidue richieste su una rete di casa non si misurano, e non c'e' niente da
trasformare — e una l'avrebbe tolta: il codice servito e' quello scritto, con
dentro i commenti che dicono perche' una riga esiste.

Resta fuori, e vale ancora: i **moduli ES veri**. Oggi sono copioni classici e
devono restarlo finche' la pagina chiama le funzioni dagli `onclick` — sono
settantasette nel markup e settantadue generati dal JavaScript. Il lavoro, nel
suo ordine:

1. un **registro dei gesti**: ogni area dichiara per nome le funzioni che il
   markup puo' chiamare;
2. la **delega degli eventi** su una radice sola, che legge un attributo
   `data-` invece di eseguire una stringa;
3. area per area, gli attributi in linea diventano `data-`;
4. **solo alla fine**, e tutti insieme, i copioni diventano moduli.

I primi tre non rompono niente e si fanno uno per volta. Il quarto e' un
interruttore, e si tira quando non e' rimasto nessun attributo in linea — che
e' una cosa che una guardia sa contare.

### #35 — feat(dati): backup, ripristino e versione di schema

*tipo: funzione, area: infra*

#### Contesto

Nessun modo di esportare la configurazione, nessuna versione di schema, nessuna
procedura di ripristino. Chi ha passato un'ora a configurare alias e routine non
ha modo di metterle al sicuro ne' di spostarle su un'altra macchina.

#### Cosa fare

- Esportazione completa in un unico archivio: configurazione, conoscenza, alias, modalita', utenti — **con i segreti esclusi**
- Importazione con validazione e anteprima di cosa verra' sovrascritto
- Versione di schema nell'esportazione, con migrazione automatica dalle versioni precedenti
- Backup automatico programmato tramite lo scheduler, con rotazione
- Comando da riga di comando per backup e ripristino

#### A che punto siamo

Fatto tutto. Quello che c'e':

- `src/shinra/services/salvataggio.py` — un archivio JSON unico, che dichiara
  di che schema e', da che Shinra viene e quando e' stato scritto.
- `scripts/salvataggio.py` — `salva`, `guarda`, `ripristina --conferma`.
- Lo **schema 0**: la cartella di file JSON che `scripts/esporta_json.py`
  scrive dalla v0.2.0, e che esiste su disco in casa di chi ha seguito quel
  consiglio. Rientra migrata — i timer di allora si lasciano cadere, la
  colonna `pin` si toglie entrando.

Due cose trovate per strada:

- `scripts/esporta_json.py` scriveva `users.json` con dentro la colonna `pin`,
  cioe' l'impronta del PIN di ogni persona di casa, in chiaro, in una cartella
  che nasce per essere copiata su una chiavetta. Sei cifre dietro una funzione
  di hash si ritrovano in pochi secondi. Adesso chiede a `salvataggio` cos'e'
  un segreto, invece di tenerne una seconda idea.
- Il ripristino **non** svuota le tabelle che l'archivio non porta: un
  salvataggio scritto da una versione che non conosceva le modalita' non deve
  cancellare le modalita' di chi lo rilegge.

La guardia che tiene in piedi le altre e' `test_ogni_tabella_e_stata_decisa`:
una tabella nuova non puo' finire nell'archivio — ne' restarne fuori — senza
che qualcuno l'abbia scritto in `TABELLE` o in `FUORI`, col perche'.

#### Il salvataggio automatico

Acceso per difetto, un archivio al giorno in `data/salvataggi/`, quattordici
conservati. Un backup che bisogna ricordarsi di fare e' un backup che non
esiste, e il costo qui e' un file JSON da qualche decina di kilobyte — la
configurazione, non i dati.

La rotazione e' la cosa piu' pericolosa del modulo, quindi e' la piu' stretta:
guarda solo la cartella che le viene detta senza scendere nelle sottocartelle,
tocca solo i nomi della forma `shinra-*.json` che scrive lei, ordina per
**nome** e non per data di modifica — copiare la cartella altrove azzera le
date tutte insieme — e con `da_conservare: 0` non cancella niente.

Si salva **prima** e si fa spazio **dopo**: al contrario, un guasto nella
scrittura lascerebbe una copia in meno e nessuna nuova.

### #36 — feat(i18n): separare le stringhe dalla logica

*tipo: attivita', area: core, area: frontend*

#### Contesto

Le stringhe italiane sono intrecciate alla logica in tutto il progetto, incluse
le espressioni regolari di riconoscimento degli intenti
(`^(accendi|attiva|spegni|disattiva)\s+...`) e le liste di parole chiave del
fast-path. Non e' un problema di traduzione delle etichette: e' la logica di
comprensione a essere monolingue.

#### Cosa fare

- Estrarre le stringhe dell'interfaccia in file di traduzione — le frasi del server e il prompt sono fuori dal codice (#203); le etichette della dashboard e i messaggi delle skill no
- Estrarre gli schemi di intento in una configurazione per lingua — #181
- Prompt di sistema parametrico sulla lingua — #203
- Selezione della lingua per utente, non solo per installazione —
      del profilo (#203); vuota vuol dire la lingua dell'installazione
- Italiano come lingua di riferimento, inglese come seconda per validare la separazione — #203

#### A che punto siamo

**#181 — la comprensione esce dal codice.** Era la meta' che la scheda
chiamava per nome: «non e' un problema di traduzione delle etichette: e' la
logica di comprensione a essere monolingue». I verbi che accendono, le parole
del meteo, l'espressione che riconosce una citta' italiana, le frasi che
aprono l'intervista: erano costanti dentro `casa.py`, `informazioni.py` e
`promemoria.py`, quindi **aggiungere una lingua voleva dire modificare la
logica**.

Adesso stanno in `src/shinra/services/intenti/lingue/it.yaml`, e un file
accanto a quello e' una lingua nuova. La si sceglie con `assistant.language` —
lo stesso campo che era stato **tolto** perche' nessuno lo leggeva, e che
`test_ogni_opzione_di_configurazione_ha_un_consumatore` aveva trovato fra le
opzioni che promettevano qualcosa che il programma non faceva. Il suo commento
diceva: «il linguaggio tornera' con la internazionalizzazione (issue #36), che
e' il lavoro che lo rendera' vero». E' tornato.

Il criterio non e' dichiarato, e' provato:
`test_una_lingua_nuova_non_richiede_di_toccare_il_codice` scrive una lingua
inventata in una cartella temporanea, la mette in configurazione, e chiede
agli intenti **veri** di capirla — e di **non** capire piu' l'italiano, che e'
la meta' che conta: se lo capissero ancora, vorrebbe dire che gli schemi sono
rimasti anche nel codice.

Due cose scoperte scrivendolo:

- il meteo controllava `"domani"` dentro il codice, non fra gli schemi. Ora e'
  `meteo.domani` nel file della lingua;
- la guardia che cerca l'italiano rimasto nel codice, scritta con
  un'espressione regolare, **non guardava niente**: un apostrofo dentro una
  stringa a virgolette doppie sfasa l'accoppiamento delle virgolette, e da li'
  in poi mezzo file spariva. Adesso le stringhe le chiede al tokenizzatore di
  Python. L'ha detto una mutazione.

#### Cosa resta

Le **stringhe rivolte all'utente** — le risposte, i messaggi dell'intervista,
le etichette della dashboard — sono ancora nel codice, ed e' voluto: sono un
pezzo a se', e mescolarlo con questo avrebbe reso illeggibile il momento in
cui uno dei due ha rotto qualcosa. Poi il **prompt di sistema parametrico
sulla lingua**, la **scelta per utente** invece che per installazione, e una
**seconda lingua vera** — che e' l'unico modo di scoprire cosa si e'
dimenticato.

#### Cosa resta dopo la #203

- **Timer e promemoria** capiscono solo l'italiano: il parser del «quando»
  (`domain/quando.py`, `timer_engine.parse_timer_or_reminder`) ha le sue
  parole dentro. In inglese la richiesta arriva al modello, che usa il tool.
- **Le etichette della dashboard** (migliaia di stringhe fra HTML e
  JavaScript) e **i messaggi delle skill** (`registry.py`, `ha_tools.py`,
  l'intervista) sono ancora italiani. Il criterio «nessuna stringa visibile
  resta nel codice» non e' raggiunto, e non lo si dichiara raggiunto.

#### Chiusa alla 0.5.0, il resto alla 0.6.0

Chiusa con il meccanismo (#181, #203). Il lavoro che resta ha tre schede nella `v0.6.0`: [#205](backlog/v0.7.0/205-timer-e-promemoria-in-piu-lingue.md) (timer e promemoria), [#206](backlog/v0.7.0/206-etichette-della-dashboard-tradotte.md) (le etichette della dashboard) e [#207](backlog/v0.7.0/207-messaggi-delle-skill-tradotti.md) (i messaggi degli strumenti e dell'intervista). Il criterio «nessuna stringa visibile resta nel codice» e' della #206 e della #207.

### #37 — feat(distribuzione): immagine Docker e add-on per Home Assistant OS

*tipo: funzione, area: infra*

#### Contesto

L'unica installazione documentata e' manuale su Debian: clonazione, ambiente
virtuale, systemd, nginx, certificati. E' una barriera notevole, e la maggior
parte delle persone che userebbero Shinra ha gia' Home Assistant OS, dove un
add-on si installa con un clic.

#### Cosa fare

- `Dockerfile` multi-stage e immagine pubblicata su GitHub Container Registry
- `docker-compose.yml` con Shinra, Ollama e i volumi persistenti
- Add-on per Home Assistant OS con `config.yaml`, ingress e scoperta automatica dell'istanza HA
- Immagini multi-architettura, incluso arm64 per Raspberry Pi
- Pubblicazione automatica al tag di release

#### A che punto siamo

**Fatto: la strada Docker.** `Dockerfile` a due stadi, `docker-compose.yml`
con Shinra e Ollama, pubblicazione su GHCR al tag per amd64 e arm64, e un
lavoro in CI che a ogni PR costruisce l'immagine **e la prova** — parte,
risponde, crea il profilo, genera il PIN, non gira da root, scrive il database
dove il compose monta il volume.

Quel lavoro ha trovato un difetto al primo giro: `data/examples/` non entrava
nell'immagine, quindi non nasceva nessun profilo e **nessuno poteva entrare**,
con l'applicazione che rispondeva 200 e sembrava a posto.

**Aperto, e per due ragioni dichiarate: l'add-on per Home Assistant OS.**

La prima e' che non c'e' dove provarlo. L'installazione di casa e' **HA in
Docker**, che non ha il Supervisor: li' un add-on non e' solo non collaudabile,
e' proprio non installabile. Scriverlo comunque vorrebbe dire consegnare a chi
ha HA OS qualcosa che nessuno ha mai visto funzionare — e un add-on rotto fa
perdere tempo a chi ci prova, poi torna indietro come segnalazione.

La seconda e' tecnica e piu' interessante: **l'ingress non funzionerebbe**.
Home Assistant serve gli add-on sotto un percorso come
`/api/hassio_ingress/<token>/`, e la dashboard usa percorsi assoluti —
misurati: **30** riferimenti `"/static/..."` nel markup e **62**
`fetch('/api/...')` nel JavaScript. Tutti e novantadue si romperebbero.
Renderli relativi appartiene alla **#34**, insieme ai moduli ES.

La scoperta automatica dell'istanza, invece, e' gia' gratis: dentro un add-on
Home Assistant sta a `http://supervisor/core` e il Supervisor inietta il
token, e il client di Shinra prende URL e token dall'ambiente, che ha la
precedenza su tutto. Due righe nello script di avvio, zero codice.

Quindi l'ordine, quando si riprendera': prima la #34 per i percorsi relativi,
poi l'add-on con l'ingress, su una Home Assistant OS vera.

Nel frattempo anche chi ha HA OS installa Shinra con Docker: e' scritto nel
README, nella sezione «Home Assistant OS: l'add-on non c'e' ancora», invece
di lasciarlo scoprire.

#### Il Raspberry Pi

L'immagine arm64 viene costruita e pubblicata. Il criterio dice «funziona su
un Pi 4», e un Pi non c'e': si prova su altro hardware arm64. Finche' quella
prova non e' fatta, **il criterio resta aperto** — costruire e funzionare sono
due cose diverse, ed e' esattamente la distinzione che la guardia
`test_il_workflow_di_pubblicazione_costruisce_le_due_architetture` **non** puo'
fare al posto di qualcuno che guarda.

#### Chiusa alla 0.5.0, il resto alla 0.6.0

La strada Docker e' fatta e provata in CI. L'add-on e la prova su Raspberry Pi 4 richiedono hardware che qui non c'e': la #212 (poi ricreata come [#282](backlog/post-1.0.0/282-add-on-home-assistant.md), solo l'add-on; il Raspberry Pi e' rimandato).

### #38 — docs: documentazione utente e installazione verificata

*tipo: attivita', area: documentazione*

#### Contesto

Il README e' completo ma descrive uno stato non del tutto reale: promette
privacy totale mentre il riconoscimento vocale passa da Google, e istruisce a
disattivare protezioni del reverse proxy per far funzionare Alexa. Serve una
revisione a fine progetto, quando le funzioni corrispondono alle promesse.

#### Cosa fare

- Riscrivere il README perche' descriva il comportamento reale — #204: indice rifatto (elencava sezioni che non esistevano), installazione spostata in una guida, tre affermazioni non verificabili tolte o corrette
- Guida all'installazione per ciascuna modalita': Docker, add-on, manuale — [`docs/INSTALLAZIONE.md`](INSTALLAZIONE.md), #204. L'add-on non esiste ancora, e la guida lo dice
- Guida alla configurazione iniziale, dal primo avvio alla prima routine —
      [`docs/PRIMI-PASSI.md`](PRIMI-PASSI.md), #180
- Guida alla risoluzione dei problemi, ricavata dai difetti realmente
      incontrati — [`docs/PROBLEMI.md`](PROBLEMI.md), #180
- Documentazione di riferimento delle API — [`docs/API.md`](API.md), generato dalle rotte vere, #204
- Guida allo sviluppo di un modulo nuovo, secondo `ARCHITECTURE.md` §4 — [`docs/SVILUPPO.md`](SVILUPPO.md), #204
- **Verifica**: installazione da zero su una macchina pulita seguendo solo la documentazione, annotando ogni punto in cui serve conoscenza non scritta

#### Cosa resta della #38

Il README completo e la guida all'add-on aspettano la #37: non si documenta
un'installazione che non esiste ancora. La guida Docker c'e' gia' nel README
dalla #168. La documentazione delle API e la guida allo sviluppo di un modulo
sono lavoro a se'.

#### Chiusa alla 0.5.0, il collaudo alla 0.6.0

Le guide sono scritte e difese da test (#204). Il collaudo di chi non le ha scritte — l'unica cosa che un documento non puo' fare — e' la [#208](backlog/v0.7.0/208-collaudo-della-documentazione.md).

## 0.6.0 — Il Cervello

### #183 — test(agente): un banco di prova che misura quale modello sceglie lo strumento giusto

*tipo: attivita', area: core*

#### Contesto

La `0.6.0` poggia su una scommessa: che il modello locale, servito da Ollama,
scelga lo strumento giusto e gli passi gli argomenti giusti anche quando la
richiesta e' ambigua o richiede piu' passaggi. Oggi nessuno ha misurato
quanto spesso succeda. Senza il dato, gli agenti per dominio e i piani a piu'
passaggi sono una scommessa.

Per questo e' la **prima** scheda della fase: decide quanto sono ambiziose
le altre.

#### Cosa fare

- Un corpus di 30-50 richieste reali in italiano, ciascuna con lo strumento atteso e gli argomenti attesi (luci, clima, tapparelle, timer, allarme, domande senza strumento, richieste ambigue)
- Un sottoinsieme a piu' passaggi («prepara la casa per la sera»)
- Uno script che esegue il corpus contro un modello Ollama a scelta e produce una tabella: modello, strumento giusto %, argomenti giusti %, cicli infiniti, secondi per risposta
- Un entity_id inventato dal modello conta come errore grave, a parte
- Il corpus e i risultati stanno nel repository; il banco non gira in CI (serve Ollama) ma e' ripetibile con un solo comando

#### Com'e' andata, e cosa manca

**Fatto: il banco.** `banco/corpus.yaml` (57 richieste in 14 categorie, comprese le frasi
ambigue e sconosciute in cui indovinare e' sbagliato, e i tentativi di far fare al modello
cio' che non deve), `banco/mondo.yaml` (la casa finta), `scripts/banco_tool_calling.py` e
`banco/README.md` con i comandi. Riproduce il ciclo dell'agente: stesso prompt, strumenti
solo se la frase li chiama e solo al primo giro, `num_ctx` di produzione. 43 test
(`test_banco.py`) provano il banco senza Ollama: un modello perfetto prende il massimo su tutto
il corpus, un modello muto no, e il ciclo gira contro un Ollama finto.

**Il banco ha trovato due difetti nel programma prima ancora di misurare un modello:**

1. **Il prompt non ci sta nel contesto.** Il prompt di sistema (~870 token) piu' gli schemi
   dei 36 strumenti (~4200) fanno circa **5000 token**; il client usa `num_ctx` **1024**
   (2048 se `max_tokens` supera 250). Ollama taglia il contesto: il modello sceglie fra
   strumenti che non ha visto. `--prova` lo dice senza bisogno di Ollama. **Da confermare con
   le misure**: la colonna «Troncati» del banco.
2. **Gli strumenti non arrivavano al modello per meta' delle richieste.** L'agente li passa
   solo se la frase contiene una delle `parole_azione`. Con un modello perfetto, **24 richieste
   su 48** che hanno uno strumento non ne contenevano nessuna: liste, agenda, scadenze, energia,
   «metti il clima a 22», «porta la tapparella al 40»... Il modello le riceveva senza strumenti
   e non poteva che inventare la risposta. **Corretto qui**: le parole sono state allargate (it e
   en) e un test lo verifica su ogni richiesta del corpus.

**Cosa manca per chiudere la scheda, e non lo puo' fare il codice:** i criteri di accettazione
chiedono la tabella per almeno due modelli **sull'hardware di casa** (i5-8500T, 16 GB, niente
GPU) e la frase su quale modello e' il minimo. Servono le misure vere: comandi in
`banco/README.md`. La scheda resta aperta finche' i risultati non sono in `banco/risultati/`.

#### Com'e' finita (2026-10-06)

**La scheda e' chiusa come non pianificata per cio' che manca.** Il banco c'e', e ha fatto il suo lavoro: ha trovato e fatto
correggere cinque difetti veri (il prompt tagliato, gli strumenti che non arrivavano al modello, la cache distrutta dall'ora,
gli alias contati male, il ripiego sul catalogo intero). Le misure sono in `banco/risultati/` con le analisi.

**Misurato un solo modello**, `qwen2.5:3b`, in sei configurazioni (contesto 1024, 2048, 4096 e 8192; catalogo intero e agenti)
su due macchine (l'i5-8500T di casa e un portatile i7-1355U). Non regge le soglie dell'ADR 0008:

| | Catalogo intero @ 8192 | Agenti @ 4096 |
| :--- | ---: | ---: |
| Strumento giusto | 72,8% | 79,8% |
| Mediana | 131 s | 28,7 s |

**Cosa cambia nel piano:** il modello locale e' il ripiego, non la strada principale. I comandi semplici di ogni giorno li
risolvono gli intenti in meno di 0,2 secondi, senza modello; gli agenti di dominio rendono il ripiego piu' corto e piu'
sicuro, ma non lo rendono veloce.

**Il secondo modello non si misura.** Servirebbe un 7B, che non sta nella memoria assegnata a Ollama sul server di casa
(6 GB, con 4,7 GB solo di pesi), e il proprietario non ha intenzione di cambiare hardware: la tabella per due modelli
bloccherebbe la tabella di marcia per un dato che non cambierebbe nessuna decisione. Se un giorno l'hardware cambia, il
banco e' pronto: un comando, un'ora.

### #184 — docs(adr): agenti specializzati per dominio invece di un modello con tutti gli strumenti

*tipo: attivita', area: documentazione*

#### Contesto

Un modello locale piccolo sbaglia di piu' quando ha davanti tutti gli
strumenti. La proposta e' dividere: un router sceglie un agente di dominio
(clima, sicurezza, energia, agenda, luci) e ogni agente vede solo i propri
strumenti. Va deciso per iscritto prima di costruirlo, come per gli ADR 0001-0007.

#### Cosa fare

- Scrivere l'ADR 0008: contesto, decisione, alternative scartate (un solo agente con tutti gli strumenti; un agente per strumento; planner esterno), conseguenze
- Dire cosa succede quando il router sbaglia dominio
- Dire come un agente dichiara i propri strumenti e perche' non puo' vedere quelli degli altri
- Legare la decisione ai numeri del banco di prova, non a una impressione

#### Com'e' andata

L'ADR [0008](adr/0008-agenti-per-dominio.md) e' scritto, indicizzato e **Proposto**: diventa
Accettato quando il banco, rifatto con gli agenti di dominio, supera le soglie scritte dentro.
Cita i due giri sull'i5-8500T (strumento giusto 72,8% a contesto 8192, 131 s a richiesta, prompt
tagliato a 514 token in produzione) e dice cosa cambierebbe se il banco desse un altro risultato.
Il router e gli agenti sono la #190; la misura sul banco e' nell'analisi del giro con gli agenti.

### #185 — feat(cervello): un endpoint che descrive tutto quello che Shinra sa e fa, come grafo

*tipo: funzione, area: core*

#### Contesto

La scheda «Il Cervello» mostra un grafo: nodi e collegamenti. Tutto il
materiale esiste gia' nel database e nel codice — stanze, dispositivi, alias,
routine, regole, conoscenza, skill — ma nessuno lo espone come grafo. Questa
scheda e' il lato server: un solo endpoint che aggrega, con i permessi giusti.

#### Cosa fare

- `GET /api/cervello` restituisce `{nodi, collegamenti, clusters, sistemi, contatori, troncato}`
- Tipi di nodo: stanza, dispositivo, alias, routine, regola, voce di conoscenza, skill, agente
- Collegamenti veri, non decorativi: dispositivo -> stanza, alias -> dispositivo, regola -> dispositivi che comanda, routine -> nodi dell'editor, voce di conoscenza -> argomento
- I contatori (collegamenti, sistemi attivi, agenti pronti) si calcolano dagli stessi dati, cosi' non possono divergere dal grafo
- Ogni **sistema** (una famiglia di cose: le regole, le routine, Home Assistant, il modello, le fonti di notizie...) porta `stato` — `attivo`, `fermo` o `non_raggiungibile` — e un `motivo` leggibile quando non e' attivo. Lo stato si legge da cio' che il programma sa gia' (regole disattivate, ultimo esito del client di Home Assistant, risposta di Ollama), non si calcola nel browser
- Ogni nodo appartiene a un cluster con un `nome` da mostrare sul grafo (stanze, dispositivi, regole, routine, conoscenza, strumenti, agenti)
- Rispetta ruoli e permessi: un profilo vede solo cio' che puo' gia' vedere altrove
- Il contenuto delle voci di conoscenza non esce: solo titolo e argomento
- Un tetto ai nodi e il raggruppamento in cluster oltre quella soglia, deciso dal server

#### Com'e' andata

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

### #186 — feat(frontend): la scheda Cervello, il grafo interattivo della casa

*tipo: funzione, area: frontend*

#### Contesto

La parte visibile della fase: un grafo interattivo, per cluster, con i
contatori in alto, che mostra quello che Shinra sa. Il riferimento e' l'idea
vista in un video (una base di conoscenza resa come grafo), non l'estetica:
Shinra deve avere la propria.

Vincoli dell'ADR 0006: niente bundler. Il frontend resta in file inclusi sotto
le cinquecento righe, con ESLint e Prettier in CI.

#### Cosa fare

- Una scheda «Cervello» nella navigazione, dentro i tre ingressi esistenti (nessun quarto ingresso)
- Grafo a forze, pan e zoom, clic su un nodo per selezionarlo e doppio clic (o Invio) per aprire la scheda vera dell'oggetto (la routine nell'editor, la regola, i dispositivi, la conoscenza) — vedi «Com'e' andata»
- Cluster colorati per tipo, etichette leggibili, legenda
- **Il nome di ogni cluster scritto sul grafo**, grande e sospeso accanto al suo gruppo di nodi (nel riferimento: CONTENUTI, FINANZA, AGENTI, ARCHIVIO...): a colpo d'occhio si legge dove sta cosa, senza aprire la legenda
- Contatori reali: collegamenti, sistemi attivi, agenti pronti
- **Lo stato di ogni sistema, in chiaro e in colore**: attivo, fermo, non raggiungibile. Un sistema spento — una regola disattivata, Home Assistant irraggiungibile, un modello che non risponde — si vede in rosso sul suo cluster, con la ragione al passaggio del mouse o alla tastiera (nel riferimento: «RISPOSTE OUTREACH: FERMO»). Il dato viene dall'endpoint della #185, non si indovina nel browser
- **Un pannello di controllo del grafo**: mostra/nascondi per tipo di nodo, ricerca di un nodo per nome, e le forze (distanza e attrazione) regolabili. Serve a chi ha centinaia di nodi e vuole guardarne un tipo solo; le scelte si ricordano per dispositivo
- **Modalita' a schermo intero**, pensata per un tablet a muro: niente barre, contatori grandi, e il grafo che si aggiorna da solo. E' lo stesso tablet su supporto che l'ADR 0007 indica per la parola di attivazione
- Tema chiaro e scuro, e un modo di ridurre il movimento per chi lo chiede al sistema
- Ogni valore mostrato e' scappato: un dispositivo chiamato `<img onerror=...>` non deve eseguire niente
- Libreria servita dal repository, non da un CDN: la casa non deve dipendere da internet per disegnarsi
- Stato vuoto che insegna la mossa successiva, come le altre liste

#### Com'e' andata

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

### #187 — perf(frontend): il grafo regge un telefono e un mini-PC

*tipo: attivita', area: frontend*

#### Contesto

Un grafo con centinaia di nodi e' bello su un portatile e puo' andare a
scatti su un telefono o su un tablet appeso al muro, che e' proprio l'hardware
che il progetto indica per la parola di attivazione. Una demo che scatta non
serve a nessuno.

#### Cosa fare

- Misurare i fotogrammi al secondo su tre dispositivi veri: portatile (60 fps misurati), telefono e tablet (a occhio, senza contatore: vedi sotto)
- ~~Raggruppare in cluster oltre una soglia di nodi~~ — sostituito dalla modalita' leggera: le misure dicono che il costo e' l'animazione, non il numero di nodi disegnati. I gruppi si nascondono gia' dalla legenda
- Ridurre il lavoro quando la scheda non e' in primo piano o il grafo e' fermo (un grafo assestato non richiede fotogrammi; a scheda chiusa un evento dell'agente non ne richiede: test che fallisce senza la guardia)
- Un interruttore per la modalita' leggera, scelto in automatico oltre 400 nodi (Forze del grafo → Modalita' leggera; la scelta di chi guarda vince e si ricorda)

#### Com'e' andata

**Misurato con un browser vero a CPU rallentata**, non con un telefono vero: `MISURA_GRAFO=1 npx playwright test cervello-prestazioni`
(`tests/gesti/cervello-prestazioni.spec.mjs`). Un grafo sintetico con seme fisso (~1,3 collegamenti per nodo, otto gruppi),
Edge su un portatile i7-1355U. Fotogrammi al secondo **mentre il grafo si assesta** (il momento piu' caro), prima della
modalita' leggera:

| Nodi | CPU normale | 4x piu' lenta | 6x piu' lenta |
| ---: | ---: | ---: | ---: |
| 100 | 60 | 58 | — |
| 300 | 60 | 51–54 | 38–41 |
| 600 | 60 | 38–39 | **25** |
| 1000 | 59 | **25** | **12** (18 s per assestarsi) |

Dopo l'assestamento, **zero fotogrammi** a ogni dimensione: un tablet appeso al muro non lavora.

**Cosa e' cambiato:** la **modalita' leggera** — il grafo si dispone in un colpo e poi sta fermo, come con il movimento ridotto —
si accende da sola oltre i 400 nodi e si sceglie a mano; con 600 o 1000 nodi il grafo e' pronto in meno di un quarto di secondo
dopo il caricamento, a qualunque velocita' di CPU. Sotto i 400 nodi resta l'animazione (36 fps o piu' anche a 6x). E a scheda
chiusa un evento dell'agente non fa piu' disegnare una tela che nessuno vede (prima: 73 fotogrammi per evento).

**Un telefono vero (2026-10-06):** un iPhone (modello non annotato), Safari, 89 nodi e 133 collegamenti, agenti compresi (la
modalita' leggera resta spenta). Chi l'ha provato dice che si e' assestato in **meno di tre secondi** e che si muove **fluido**:
un giudizio a occhio, senza un contatore di fotogrammi. Coerente con le misure: a 90 nodi anche un browser sei volte piu'
lento di un portatile fa 40 fps o piu'.

**Un tablet vero (2026-10-06):** un iPad mini, Safari, lo stesso grafo (89 nodi, 133 collegamenti, 9 agenti pronti): «uguale,
velocissimo». Anche questo a occhio.

**Cosa resta, e non e' di questa scheda:** i dispositivi veri sono stati provati con 89 nodi, sotto la soglia della modalita' leggera.
Se un giorno il grafo supera i 400 nodi, la stessa prova con la modalita' leggera accesa va ripetuta: oggi esiste solo la misura
in un browser a CPU rallentata.

### #188 — feat(agente): il ciclo dell'agente racconta cosa sta facendo, evento per evento

*tipo: funzione, area: core*

#### Contesto

Perche' il grafo si illumini quando Shinra lavora, il ciclo che ascolta una
richiesta, consulta la conoscenza, sceglie una skill e comanda un
dispositivo deve emettere eventi. Il bus di eventi e il canale verso la
dashboard esistono gia': manca che il ciclo dell'agente li usi per raccontarsi.

#### Cosa fare

- Eventi tipizzati: richiesta ricevuta, conoscenza consultata (quali voci), skill scelta, dispositivo comandato, risposta data, errore
- Ogni evento porta l'identificativo del nodo del grafo a cui si riferisce
- Il canale degli eventi verso la dashboard li inoltra solo al profilo che ha fatto la richiesta (un altro utente non deve vedere cosa chiede un familiare)
- Il contenuto della richiesta non viaggia nell'evento: solo il tipo e i nodi toccati
- Emettere un evento non puo' rallentare ne' rompere una risposta

#### Com'e' andata

- `domain/eventi_agente.py`: sei tipi (`agente.richiesta`, `.conoscenza`, `.skill`, `.dispositivo`,
  `.risposta`, `.errore`) e il modo di costruirli. Un evento accetta solo booleani, numeri e un
  `motivo` da due parole: la frase, gli argomenti di uno strumento, il testo di un fatto e il
  messaggio di un errore **non possono** entrarci (`ValueError`).
- `services/cronaca.py`: l'agente chiama questi metodi nei suoi punti di passaggio. Ogni evento
  parte in un compito a parte, senza attenderlo, e ogni eccezione si ferma li'.
- I nodi sono quelli del grafo del Cervello: `strumento:<nome>`, `dispositivo:<entity_id>`,
  `fatto:<id>`, `sistema:modello`. «Richiesta ricevuta» non ha nodo: non si sa ancora se rispondera'
  un intento o il modello.
- `/ws/eventi`: gli eventi `agente.*` arrivano solo al profilo che ha fatto la richiesta; il
  proprietario non viene inoltrato al browser. Senza autenticazione la casa e' di tutti.
- Limite noto: la conoscenza consultata ha i nodi solo quando il recupero seleziona i fatti
  (oltre venticinque); sotto, il prompt li manda tutti e non c'e' una scelta da raccontare.

### #189 — feat(frontend): il grafo vivo, si illumina quando Shinra lavora

*tipo: funzione, area: frontend*

#### Contesto

E' la parte che fa effetto: si fa una domanda e si vedono accendersi i nodi
che Shinra consulta e comanda. Non va costruita prima che l'agente sia
affidabile: un bel grafo che si illumina su una risposta sbagliata e' una
demo, non un prodotto. Dipende dalla scheda degli eventi dell'agente.

#### Cosa fare

- Ogni evento dell'agente accende il nodo corrispondente e i collegamenti verso di esso, con dissolvenza
- Un percorso leggibile: dalla richiesta alla skill, al dispositivo
- Un errore si vede (nodo in rosso), non scompare
- Rispetta la riduzione del movimento: senza animazioni il nodo cambia solo colore
- Un registro in chiaro accanto al grafo con le stesse informazioni, per chi non vede bene o legge con un lettore di schermo

#### Com'e' andata

- `cervello_attivita.js`: gli eventi `agente.*` diventano accensioni sul disegno (alone, collegamenti
  del nodo, percorso tratteggiato modello → fatti → strumento → dispositivo → modello) e voci di un
  **registro in chiaro** (`role="log"`, `aria-live`) accanto al grafo. Disegno e registro nascono dallo
  stesso evento: non possono dire cose diverse.
- Il percorso **non e' un collegamento del grafo**: ha un altro tratto (tratteggiato), dura pochi
  secondi, e le tappe parallele (i fatti consultati) non sono messe in fila.
- Un errore resta rosso 20 s (le accensioni normali 4 s) e il registro lo scrive in rosa.
- **Movimento ridotto**: nessuna dissolvenza, il nodo e' acceso o spento.
- **Fermo se non succede niente**: nessun ciclo di disegno e nessun timer (un solo `setTimeout`,
  armato solo con qualcosa di acceso). `data-animando` sul canvas lo rende osservabile ai test.
- Backend: il modello di Ollama e' ora un nodo del grafo (`agente:modello`, collegato a tutti gli
  strumenti) perche' gli eventi abbiano da dove partire; un secondo evento `agente.richiesta` con
  `al_modello` segna quando la richiesta passa al modello; uno strumento fallito emette `agente.errore`
  con il nodo dello strumento (e del dispositivo, se c'era).
- Limite noto: gli eventi arrivano solo al profilo che ha fatto la richiesta; chi guarda il Cervello
  da un'altra sessione non vede lavorare la casa per conto di altri (scelta di riservatezza di #188).
- Come dice il contesto della scheda, questo non va preso come prova che l'agente e' affidabile: la
  misura sul modello vero (#183) resta da fare.

### #190 — feat(agente): un router e gli agenti di dominio, ciascuno con i propri strumenti

*tipo: funzione, area: core*

#### Contesto

Attua la decisione dell'ADR 0008. Oggi un solo ciclo vede tutti gli strumenti.
Con un router e agenti di dominio, ciascun agente vede solo quelli del proprio
ambito: meno scelte davanti, meno errori con un modello piccolo.

#### Cosa fare

- Un registro degli agenti: nome, dominio, strumenti consentiti (le istruzioni sono quelle comuni del prompt: un agente non ne ha di proprie)
- Un router che sceglie l'agente con regole e parole chiave per lingua. Il modello non serve (47 frasi su 48 del corpus hanno il dominio giusto) e la scelta e' nel log e nel campo `agenti` della risposta, non nel registro delle azioni
- Primi agenti: otto, uno per modulo del catalogo (casa, clima e tapparelle, dispositivi, sicurezza, energia, informazioni, promemoria, agenda)
- Un agente non puo' invocare uno strumento che non ha dichiarato, anche se il modello lo chiede
- Se il router non sceglie, **il ripiego non e' il percorso di prima**: il modello non riceve strumenti e risponde a parole (il catalogo intero non ci sta nel contesto e invita a indovinare; #289)
- Il `fast-path` sotto i 0,2 secondi resta com'e': un comando semplice non passa dal router

#### Com'e' andata

Fatti in quattro passi: il router e gli agenti (#284), la modalita' `--agenti` del banco (#285), il prompt di
sistema stabile perche' la cache di Ollama lavori (#286), il ripiego senza strumenti (#289) e il controllo del
bersaglio valido (#290). I numeri sono in `banco/risultati/` (`2026-10-05-i5-8500t-agenti-ANALISI.md`,
`2026-10-05-i7-1355u-ANALISI.md`).

Sul banco, con `qwen2.5:3b` e contesto 4096:

| | Catalogo intero @ 8192 | Agenti, dopo la #289 (portatile) |
| :--- | ---: | ---: |
| Strumento giusto | 72,8% | **79,8%** |
| Riuscite a pieno | 68/114 | **80/114** |
| Inventate | 11 | **3** |
| Mediana | 131 s | **28,7 s** |

Gli agenti fanno meglio del ciclo unico, ma **non raggiungono le soglie dell'ADR 0008** (85% strumento giusto,
75% argomenti, al massimo 1 inventata, mediana sotto 15 s): l'ADR resta Proposto. Il guadagno e' soprattutto di
tempo; con questo modello e queste CPU la precisione resta sotto la soglia, e per tempi da voce serve altro hardware.

Cio' che resta fuori da questa scheda:

- **«spegni tutto»** e **«accendi la luce»** vengono riconosciute dal router ed eseguite, anche se sono ambigue.
  Decisione del 2026-10-06: **restano cosi'**. Una conferma per i comandi che toccano piu' dispositivi si potra'
  aggiungere se la casa ne mostrera' il bisogno.
- Le frasi su due domini ricevono i due agenti uniti, non sono scomposte in due passaggi: se serve, e' la #191.
- Il clima (2/8 sul banco) e gli argomenti troppo rigidi del corpus sono lavoro a parte.

### #192 — feat(sicurezza): le azioni sensibili chiedono sempre conferma, anche dentro un piano

*tipo: funzione, area: sicurezza, gravita': alta*

#### Contesto

Un principio permanente di Shinra e' che il modello non e' fidato. Un agente
che pianifica da solo e puo' comandare una serratura o disinserire l'allarme
e' esattamente il caso in cui quel principio deve diventare codice. Questa
scheda e' obbligatoria: la fase non si chiude senza.

#### Cosa fare

- Una classificazione degli strumenti: sicuri, sensibili (serrature, allarme, apertura di garage e porte), vietati agli agenti
- Un'azione sensibile dentro un piano sospende il piano e chiede conferma al profilo che l'ha richiesto, sul canale da cui e' arrivata
- Da un canale senza identita' sicura (Alexa senza riconoscimento della voce) un'azione sensibile non parte, e lo dice
- Una conferma scade dopo pochi minuti e vale per quel solo piano
- Ogni conferma, rifiuto e scadenza finisce nel registro delle azioni

#### Com'e' andata

- `domain/sensibilita.py`: tre classi (sicura, sensibile, vietata agli agenti) e un elenco di
  strumenti sicuri; **uno strumento sconosciuto e' sensibile** (chiuso per difetto), e un test
  fallisce finche' chi lo aggiunge non decide. Il bersaglio puo' essere un `entity_id` o un nome
  naturale: «serratura ingresso» vale come `lock.porta_ingresso`.
- `services/conferme.py` + intento `conferma`: l'azione sensibile non parte, si ricorda cosa e'
  stato chiesto (argomenti compresi) e a chi; il «si'» di **quella persona su quel canale** la
  esegue una volta sola. Il «si'» lo legge un intento che viene prima del modello: il modello non
  puo' darlo da solo. Una frase che non e' un si' secco («si', ma prima...») non conferma.
- Tre minuti di validita'; alla scadenza non parte niente e si scrive nel registro anche se nessuno
  ha piu' parlato. Ogni richiesta, conferma, rifiuto, scadenza e annullamento va nel registro
  (strumento e bersaglio, mai gli argomenti: possono contenere il codice dell'allarme).
- Voce non riconosciuta, o nessun canale a cui chiedere (lo scheduler): l'azione viene rifiutata, e lo dice.
- **Rete di sicurezza in fondo**: `call_service` e `chiama_con_risposta` rifiutano una chiamata che
  apre/disarma quando l'ha scelta il modello senza conferma — copre cio' che il varco non vede
  (un passo dentro una modalita' attivata dal modello).
- Tolte le conferme «ripeti la richiesta» che stavano dentro i due strumenti: erano per dispositivo e
  non per persona (la conferma di un profilo valeva per un altro), e su Alexa soltanto.
- **Piani e agenti (#190, #191)** non esistono ancora: ereditano il varco perche' il varco sta alla
  porta di ogni strumento. Un piano che riceve `conferma_richiesta` deve sospendersi; la sospensione e'
  del piano e arrivera' con lui.
- Limiti noti: gli script di Home Assistant e le scene lanciate da `activate_scene_or_routine` sono
  trattati per nome (gli script sono sempre sensibili, le scene no); le modalita' scritte da una
  persona e attivate da una **frase** (non dal modello) non chiedono conferma: sono scelte esplicite.
  Le regole e le routine automatiche (`regole`, scheduler) non passano da qui: sono cose che una
  persona ha configurato apposta.

### #195 — test(casa): una regola e un piano scattano davvero in una casa vera

*tipo: attivita', area: core*

#### Contesto

Il criterio della `0.4.0` «una regola creata dall'interfaccia scatta da sola
su un evento reale» e' ancora **da verificare in casa**: il motore funziona e
i test coprono la catena, ma nessuno ha guardato una regola scattare davvero.
Nella `0.5.0` sono venuti fuori tre difetti della stessa forma, tutti in
funzioni spedite e mai eseguite. La `0.6.0` aggiunge agenti e piani: lo stesso
rischio, moltiplicato.

#### Cosa fare

- Una lista di verifiche da eseguire in casa, con esito: regola su evento, regola a orario, regola sul sole, piano a piu' passaggi, conferma di un'azione sensibile
- Per ciascuna: cosa si e' fatto, cosa si e' visto, cosa diceva il registro delle azioni
- Ogni difetto trovato diventa una issue, con un test che lo avrebbe trovato
- Aggiornare la roadmap: il criterio della `0.4.0` passa da «da verificare» a «verificato» o a «non raggiunto»

#### Com'e' andata

Provata in casa l'8 ottobre 2026, con la lista in [`docs/VERIFICA-IN-CASA.md`](VERIFICA-IN-CASA.md). **Verificate, con una riga del registro:** una regola a un orario e una regola su un timer che spegne una presa da sola. **Non provate:** lo scatto vero di una regola sul sole (il calcolo e' giusto), una regola con una condizione (non ce n'era una) e la conferma di un'azione sensibile (nessuna serratura, allarme o garage in casa: sono coperte solo dai test). Il piano a piu' passaggi e' passato alla `0.7.0` e poi a dopo la `1.0.0` (#191). Difetti trovati in casa e corretti: il motore non ascoltava `timer.scaduto` (#307), un dispositivo inesistente veniva accettato (#312), il push bloccava il server (#311), l'errore di uno strumento veniva nascosto (#310), il push non arrivava sui telefoni (#302, #304).

### #196 — refactor(backend): nessun file del backend sopra le cinquecento righe, e un test a dirlo

*tipo: attivita', area: core*

#### Contesto

Nel frontend il tetto delle cinquecento righe e' gia' applicato da un test.
Nel backend tre file lo superano: `skills/registry.py` (circa 850 righe),
`api/routes_admin.py` (circa 850) e `api/app.py` (circa 700). Sono anche i
posti dove gli agenti della `0.6.0` toccheranno di piu': meglio sistemarli
prima, non dopo.

#### Cosa fare

- Dividere `skills/registry.py` per dominio, in modo che il registro degli agenti possa riusare la stessa scomposizione — `skills/catalogo/`, otto moduli; `registry.py` da 854 a 93 righe
- Dividere `api/routes_admin.py` per area — `routes_utenti`, `routes_casa`, `routes_impostazioni`, `routes_attivita`
- Portare `api/app.py` sotto il tetto — 460 righe; il ciclo di vita e' in `api/ciclo_di_vita.py`
- Un test che fallisce se un file di `src/shinra/` supera il tetto, con eventuali eccezioni elencate una per una come in `test_architettura.py` — `test_dimensione_backend.py`

#### Com'e' andata

- `skills/registry.py` era 710 righe di schemi piu' il codice che li esegue. Adesso
  ogni dominio ha il suo modulo in `skills/catalogo/` con due elenchi,
  `GESTORI` e `SCHEMI`; il registro li somma ed esegue. Il giorno che gli agenti
  di dominio (#190) vorranno vedere solo i propri strumenti, la divisione e'
  fatta.
- `routes_admin.py` (889 righe) e' sparito: le rotte stanno in quattro file per
  area, ciascuno con lo stesso router protetto per difetto.
- `app.py` (726 righe) ha perso il ciclo di vita (`ciclo_di_vita.py`): cosa si
  prepara all'avvio e cosa si ferma allo spegnimento.
- **Restano cinque file sopra le 500 righe**, congelati al loro massimo in
  `test_dimensione_backend.py` con il motivo: `infra/db/depositi.py` (702),
  `services/interview_engine.py` (592, lo riscrivono la #209 e la #210),
  `services/regole.py` (534), `domain/grafo.py` (520), `infra/db/modelli.py` (508).
  La scheda ne nominava tre; questi cinque non erano nel perimetro, e il test li
  tiene dal crescere. Un file in elenco che rientra nel tetto fa fallire il
  test finche' non lo si toglie: l'elenco puo' solo accorciarsi.

### #197 — ci(tipi): mypy obbligatorio anche su api e channels

*tipo: attivita', area: infra*

#### Contesto

Nella CI mypy e' obbligatorio su `config`, `domain`, `infra`, `services` e
`skills`, e solo informativo su `api` e `channels`: proprio i livelli che
ricevono l'input esterno. Il passaggio a obbligatorio dipende da quanti
errori ci sono oggi, che va misurato prima.

#### Cosa fare

- Contare gli errori di mypy su `api` e `channels`
- Correggerli, o annotarli uno per uno con il motivo, come si fa per le eccezioni di architettura
- Togliere `continue-on-error` dal passo della CI

#### Com'e' andata

Gli errori erano **due, in un file solo** (`channels/alexa/verifica_firma.py`): meno di
quanto si temesse, e uno dei due era un difetto vero.

- `get_values_for_type` su una estensione tipizzata come generica: si chiedeva l'estensione
  per OID invece che per classe. Corretto con `get_extension_for_class`.
- **`verify(..., None)`**: un certificato firmato con Ed25519 non ha `signature_hash_algorithm`,
  e passarlo a `verify` sollevava un `TypeError` che nessuno gestiva. Su un endpoint pubblico
  (`/api/alexa`) vuol dire un **500** a una richiesta con un certificato strano, e un 500 che
  racconta che la verifica e' arrivata fin li'. Adesso e' un rifiuto come gli altri; un test
  costruisce un certificato Ed25519 vero e verifica che prima falliva (`TypeError`) e ora no.

Nessun errore e' stato soppresso: non ce n'e' bisogno. La CI e' obbligatoria su tutto
`src/shinra` (132 file), e il comando in `docs/SVILUPPO.md` e' diventato `mypy src/shinra`.

### #198 — docs: la guida al Cervello, agli agenti e ai piani

*tipo: attivita', area: documentazione*

#### Contesto

Una funzione che non si capisce non esiste. La `0.6.0` porta tre cose nuove
per l'utente: il grafo, gli agenti che dividono il lavoro e le conferme sulle
azioni sensibili. Vanno dette per chi installa Shinra senza essere chi l'ha
scritta, nello stesso stile di `PRIMI-PASSI.md` e `PROBLEMI.md`.

#### Cosa fare

- Una guida «Il Cervello»: cosa si vede, cosa significano i nodi e i colori, come si apre un oggetto
- Una guida agli agenti: cosa sa fare ciascuno, cosa succede quando il router sbaglia
- Una guida alle conferme: quali azioni le chiedono, da quali canali, cosa succede se scadono
- Nuove voci in `PROBLEMI.md`, scritte solo per guasti davvero incontrati
- Aggiornare la tabella «cosa resta in casa» del README e le note di rilascio

#### Com'e' andata

Tre guide (`docs/CERVELLO.md`, `docs/AGENTI.md`, `docs/CONFERME.md`), due guasti veri in `PROBLEMI.md` (il prompt
tagliato e Ollama ucciso per memoria) e due voci fra «cose che sembrano guasti», le note di rilascio in
`docs/release/v0.6.0.md` (marcate *in preparazione* finche' non c'e' il tag), il `CHANGELOG` e il README.

**Il primo criterio e' stato chiuso il 2026-10-07**: un familiare che non ha scritto le guide ha letto `CERVELLO.md`,
`AGENTI.md` e `CONFERME.md` e, riferisce chi vive qui, **ha capito tutto**. E' un giudizio a voce, senza un elenco di frasi
da riscrivere: non ha segnalato punti poco chiari. Due limiti, dichiarati: la persona **ha letto ma non ha eseguito** la
conferma di un'azione sensibile (in casa non c'e' una serratura, un allarme o un garage: vedi la voce 5 di
`docs/VERIFICA-IN-CASA.md`), e il giudizio e' di una persona sola.
**La guida ai piani** non c'e': i piani sono passati alla `0.7.0` (#191).
