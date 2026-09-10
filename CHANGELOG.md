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

### Sicurezza
- **Quello che dici al microfono non va più a Google.** Il riconoscimento
  vocale della dashboard usava la Web Speech API del browser, che invia
  l'audio ai server del suo produttore: ogni parola detta all'assistente
  usciva di casa. Adesso la registrazione arriva al **tuo** server e la
  trascrive Whisper.
- **Il README diceva il contrario di quello che il codice faceva.** «Zero
  Cloud per i Dati Privati» e «100% privata» convivevano con l'audio che
  usciva a ogni frase. Al loro posto c'è ora una tabella che dice, riga per
  riga, cosa resta in casa e cosa no — compreso ciò che continua a uscire: il
  testo delle risposte lette a voce (Microsoft), meteo, notizie, e i comandi
  detti a un Echo, che è un dispositivo Amazon e resta tale.
- Il README annunciava «beta `0.1.0`» mentre il progetto era alla `0.4.0`, con
  la `0.2.0` e la `0.3.0` rilasciate nel frattempo. Ora un test fa fallire la
  suite se torna indietro.

### Aggiunto
- **`faster-whisper` va installato a parte** (`pip install faster-whisper`).
  Finché non c'è, il microfono della dashboard **non funziona e lo dice**, con
  il comando da eseguire. È voluto: ripiegare in silenzio sul browser sarebbe
  rimettere il problema dov'era, scritto apposta questa volta. Nel frattempo
  si scrive con la tastiera.
- Chi preferisce la velocità del browser può sceglierlo con `voce.motore:
  browser`, e la configurazione dice cosa comporta. Una configurazione
  scritta male non ci porta: un motore sconosciuto ripiega su quello locale,
  non sul browser.
- **Le frasi che Whisper inventa sul silenzio vengono scartate.** Il modello è
  stato addestrato anche su sottotitoli e sul silenzio produce i loro titoli
  di coda — *«Sottotitoli e revisione a cura di…»*. Passarle all'agente
  significherebbe che un microfono aperto per sbaglio fa partire una richiesta
  che nessuno ha fatto.
- Il testo trascritto non finisce nel log: è ciò che una persona ha detto in
  casa sua. Nel log resta che una trascrizione c'è stata, e quanto era lunga.
- **Si entra con impronta o volto, senza digitare niente.** Una passkey si
  aggiunge dal proprio profilo (Impostazioni → Passkey) e da quel momento
  l'accesso non chiede piu' il PIN: il browser sa gia' quale credenziale
  proporre, quindi non serve nemmeno dire prima chi si e'.
- **Il PIN resta, e non e' una gentilezza.** Le passkey **non funzionano su
  `http://192.168.1.50:8000`**, cioe' nel modo in cui la maggioranza delle
  case raggiunge la propria dashboard: WebAuthn vuole un contesto sicuro e un
  nome di dominio, e un indirizzo numerico non e' ne' l'uno ne' l'altro. Dove
  non si puo', il pulsante non compare e al suo posto c'e' la ragione e il
  rimedio — un pulsante che fallisce con un errore del browser fa credere che
  il server sia rotto.
- Piu' passkey per persona, una per dispositivo, revocabili singolarmente. Chi
  perde il telefono revoca quella e basta.
- **Una passkey che sembra copiata non entra.** Se una credenziale dichiara
  meno firme di quante ne aveva gia' dichiarate, quella chiave esiste in due
  posti e non e' piu' una prova di chi sei. La riga non viene cancellata: e'
  l'unico segnale che la persona ha che qualcosa non va.
- La libreria `webauthn` e' trattata come facoltativa: se manca, si entra con
  il PIN e la sezione lo dice.

### Sicurezza
- **Il canale vocale ora verifica i permessi. Prima non li verificava mai.**
  L'ADR 0004 dichiarava un buco — «chiunque parli a un Echo agisce con
  l'identita' della sessione» — e misurandolo si e' rivelato piu' largo: il
  canale Alexa non impostava **mai** l'attore della richiesta, quindi
  `profilo_corrente()` restituiva `None`, e `None` significa «nessuna
  identita' in gioco», cioe' tutto concesso. A trattenere qualcosa restavano
  due divieti scritti a mano — niente serrature da Alexa, una conferma in piu'
  per l'allarme — e nient'altro.
- **Chi parla si riconosce dai profili vocali di Alexa**, non da cio' che
  dice. L'identificativo che Amazon manda (`context.System.person.personId`)
  si associa una volta sola a un profilo di casa, dalle impostazioni.
- **Una voce non riconosciuta comanda come un ospite**, non come nessuno:
  niente serrature, niente allarme, nemmeno ripetendo la conferma. Il ruolo di
  ricaduta si configura (`alexa.ruolo_voce_sconosciuta`), e un ruolo che non
  esiste non da' permessi.
- **L'apertura della skill non saluta piu' per nome l'amministratore.**
  Diceva a un ospite come si chiama il padrone di casa, e faceva credere a chi
  ascoltava di essere stato riconosciuto.
- **Una voce sconosciuta non riceve piu' la memoria di conversazione
  dell'amministratore.** Senza un profilo, l'agente ripiegava sul primo
  dell'elenco.
- Anche un attore che non corrisponde a nessun profilo — succede cancellando
  una persona mentre qualcosa la nomina ancora — vale come identita' ignota.
  Prima diventava `None`, cioe' cancellare un profilo restituiva tutti i
  permessi a chi lo usava.

### Modificato
- **Serrature e allarme si comandano da voce, a tre condizioni**: che si sappia
  chi parla, che quella persona abbia `sicurezza.comanda`, e che confermi
  ripetendo la richiesta. Il divieto in blocco non sparisce, si stringe
  attorno al caso che lo giustificava — non so chi sei.

### Rimosso
- **Il cambio di profilo parlato.** «sono Sonia» impostava la sessione su
  Sonia senza nessuna prova; «sono stanco» creava al volo un profilo per un
  signor Stanco. Un'identita' che si ottiene dicendola non e' un'identita'.
  Al suo posto c'e' una spiegazione di come farsi riconoscere davvero.

### Aggiunto
- **La conoscenza di casa si recupera invece di essere riversata.** Prima ogni
  fatto abilitato finiva nel prompt di ogni richiesta: con la conoscenza che
  cresce, prima si paga in latenza, poi si satura la finestra e i fatti piu'
  vecchi vengono troncati **in silenzio** — la casa dimentica senza dirlo.
  Adesso con cinquecento fatti il contesto resta della stessa dimensione.
- **Sotto i venticinque fatti si manda tutto, come prima.** Il problema esiste
  a duecento fatti, non a venti, e un recupero imperfetto dove non serviva
  farebbe perdere risposte che prima funzionavano. E' anche il motivo per cui
  la latenza non peggiora.
- **La ricerca e' ibrida.** Gli embedding avvicinano «la password del wifi» a
  «la chiave della rete» — ed e' cio' che serve — ma appiattiscono «4471» e
  «4417» sullo stesso punto, perche' semanticamente sono entrambi «un
  numero». Nomi propri e cifre li recupera il confronto testuale, dove i
  numeri pesano doppio.
- **Gli embedding si calcolano su Ollama, quindi in casa.** Un servizio nel
  cloud sarebbe piu' veloce e vorrebbe dire mandare a qualcun altro il nome
  del gatto e dove si nasconde la chiave di scorta.
- Se Ollama e' spento o il modello non e' installato, il recupero resta
  testuale: la casa risponde peggio, non smette di sapere. E lo dice, invece
  di lasciar credere che la ricerca semantica funzioni male.
- L'indice si aggiorna da solo quando un fatto viene modificato, e non lascia
  in giro i vettori dei fatti cancellati.
- Si puo' chiedere **quali fatti hanno contribuito** a una risposta, con i
  punteggi semantico e testuale separati.
- **La casa smette di aspettare la domanda.** «Se la porta si apre dopo le 23,
  accendi l'ingresso» funziona senza intervento. I trigger sono su evento,
  stato, orario, presenza, alba e tramonto; le condizioni si compongono, e la
  fascia oraria scavalca la mezzanotte — «dalle 23 alle 6» e' la finestra piu'
  usata in una casa, ed e' quella che un confronto ingenuo sbaglia sempre.
- **Un trigger su soglia scatta quando si attraversa, non mentre si sta
  sotto.** «Avvisami se scende sotto i 15» detto a una casa a 12 gradi non
  suona a ogni lettura del sensore: la differenza e' un avviso al giorno
  contro trecento, e trecento avvisi al giorno diventano zero avvisi letti.
- **Ogni scatto e' registrato, e anche ogni rifiuto, con il motivo.** E'
  l'unica risposta possibile alla domanda «perche' si e' accesa la luce?», e
  l'unico modo per distinguere una regola che non deve scattare da una rotta.
- **Due regole che si innescano a vicenda vengono fermate e raccontate**, con
  i nomi in ordine su un avviso vero: senza quelli, «una regola ha creato un
  ciclo» manda a rileggerle tutte.
- Un'azione di regola puo' attivare una modalita' esistente, chiamare un
  servizio, o mandare un avviso — quest'ultimo possibile solo dopo le
  notifiche.
- **Le notifiche arrivano sul telefono anche con l'applicazione chiusa.** Il
  service worker gestiva installazione e cache e non aveva alcun handler per
  l'evento `push`: promemoria, allarmi e avvisi restavano muti. Adesso c'e' un
  canale vero, con le chiavi VAPID generate al primo avvio.
- **Le priorita' decidono chi puo' essere zittito.** Un'intrusione suona anche
  a silenzioso attivo; un avviso energetico no. Se il silenzioso potesse
  spegnere un allarme, sarebbe un modo per spegnere l'allarme
  dimenticandosene.
- Si puo' silenziare una categoria senza silenziarle tutte. La sicurezza no, e
  il rifiuto arriva dall'API: mostrare un interruttore che poi non si rispetta
  e' peggio che non mostrarlo.
- Un'intrusione **non** viene annunciata ad alta voce: avviserebbe chi e' in
  casa — eventualmente il ladro — e non chi e' fuori. Va al telefono.
- Toccare una notifica apre il punto giusto dell'applicazione, riusando la
  finestra gia' aperta invece di aprirne una seconda.

### Corretto
- **`casa.intrusione` non arrivava da nessuna parte.** L'allarme lo pubblicava
  sul bus dalla `v0.3.0` e non lo ascoltava nessuno: non il WebSocket della
  dashboard, non i canali di consegna, niente nell'interfaccia. Le note della
  `v0.3.0` dicevano che almeno a una dashboard aperta arrivava, e non era
  vero; la riga e' stata corretta.
- Non si puo' piu' togliere il telefono di un altro conoscendone l'endpoint.

---

## [0.3.0] - 2026-09-09 — Copertura

### Aggiunto
- **Liste della spesa e delle cose da fare.** «Aggiungi il latte alla lista
  della spesa» funziona da chat e da Alexa, e «latte, pane e uova» sono tre
  voci, non una. Una cosa gia' in lista non si aggiunge due volte: al
  supermercato due righe uguali si comprano due volte.
- **Se in Home Assistant c'e' una lista `todo`, si scrive li'.** Non se ne
  tiene una copia: due liste che si sincronizzano divergono al primo
  conflitto, e una lista della spesa sbagliata e' peggio di nessuna lista.
  Le liste di casa esistono per chi non ha `todo` configurato.
- **«Cosa ho oggi»** elenca gli impegni veri, presi da tutti i calendari
  messi insieme — quelli di Home Assistant e quelli segnati in casa. Gli
  eventi di giornata intera restano tali: letti come un orario risulterebbero
  gia' passati per tutte le ore in cui accadono. Una vacanza cominciata la
  settimana scorsa e' un impegno anche oggi.
- Gli impegni si **leggono** da tutti i calendari ma si **scrivono** solo su
  quello di casa: i calendari di Home Assistant sono di Google o di iCloud, e
  una casa che scrive nell'agenda di lavoro di qualcuno fa un danno che non
  sa di fare.
- **Le scadenze di casa** — filtri della caldaia, revisione, bollo, garanzie
  — con ricorrenza e preavviso per riga. Quando si avvicinano, la casa crea
  da sola un promemoria che suona: una scadenza in un elenco che nessuno apre
  e' una scadenza dimenticata.
- Una scadenza segnata come fatta ricomincia **da oggi**, non dalla data
  prevista: altrimenti ogni ritardo si accumula, e un cambio filtri fatto con
  due mesi di ritardo tiene il calendario indietro per sempre.

### Corretto
- «Cena» e' insieme un pasto e un'ora: «dopo cena» e' un orario, «cena con
  Marco» e' il titolo di un impegno. Prima erano la stessa cosa, e «segna
  cena con Marco» diventava l'impegno «con Marco» alle venti.
- **I promemoria impostati a voce non venivano salvati.** Il tool che il
  modello chiama scriveva in una lista in memoria: non toccava il database,
  non programmava nessuna sveglia, e rispondeva «Promemoria salvato». Al
  riavvio del servizio sparivano, e non suonavano mai. Adesso il promemoria
  viene scritto e programmato davvero, ed e' lo stesso percorso per tutte le
  strade — chat, Alexa, dashboard.
- **La casa capisce molti piu' modi di dire quando.** Prima riconosceva solo
  «alle 18» e «tra dieci minuti»: adesso anche «domani mattina», «sabato»,
  «stasera», «fra due giorni», «il 15», «lunedi prossimo», e l'ordine delle
  parole rovesciato. Su dieci frasi normali prese a campione, otto prima
  finivano nel vuoto.
- **Quando non capisce quando, chiede.** Un promemoria senza orario non viene
  piu' accettato in silenzio: l'assistente domanda a che ora, invece di dire
  «salvato». Chi non sa a che ora mettere la sveglia non la mette a caso.
- «Che promemoria ho?» legge il database invece di una lista in memoria:
  prima rispondeva «nessun promemoria» a chi ne aveva sette.

### Aggiunto
- **La casa conosce le fasce orarie italiane.** F1, F2 e F3 secondo il
  calendario vero: sabato senza ore di punta, domenica fuori punta dalle 0
  alle 24, e gli undici festivi nazionali fuori punta per l'intera giornata —
  Pasquetta compresa, che e' l'unico mobile e viene calcolata. «In che fascia
  siamo?» risponde anche quando cambia.
- **Consumi e costi.** Quanti kilowattora oggi, ieri, negli ultimi sette o
  trenta giorni, divisi per fascia e convertiti in euro. La tariffa si
  configura monoraria, bioraria o trioraria; la bioraria mette F2 e F3 sotto
  lo stesso prezzo, come i contratti italiani.
- **«Quanto mi costa tenere acceso questo»** risponde all'ora e al giorno,
  alla tariffa della fascia in cui siamo adesso.
- **Senza sensori di energia lo dice, invece di inventare un numero.** «Zero
  kilowattora» e «non lo so» sono risposte diverse, e la prima detta al posto
  della seconda e' il modo piu' rapido per far perdere fiducia a un conto in
  bolletta. Lo stesso vale per la tariffa: senza prezzi configurati la
  risposta arriva comunque, ma dichiarata come stima.
- I contatori vengono letti un'ora alla volta e archiviati. Si conservano le
  letture grezze e non i consumi gia' calcolati: le differenze si
  ricalcolano, le letture perdute no.
- Un contatore che si azzera — dispositivo riavviato, sensore ricreato — non
  produce un consumo negativo, e un sensore irraggiungibile viene saltato
  invece di essere scritto come zero.
- **Il clima si comanda per intero.** Prima si sapeva dire solo una
  temperatura: adesso anche la modalita' (riscaldamento, raffrescamento,
  automatico, deumidificazione, ventilazione), la velocita' della ventola,
  l'umidita' obiettivo e i profili predefiniti. «Metti il condizionatore in
  deumidificazione» era una frase che non aveva modo di arrivare a Home
  Assistant.
- **Le tapparelle si fermano dove si vuole.** Posizione percentuale,
  orientamento delle lamelle, arresto a meta' corsa. Cento e' aperta, zero e'
  chiusa, come sulla dashboard: «abbassala al 40 per cento» vuol dire
  posizione 40.
- **Si chiede al dispositivo cosa sa fare prima di chiederglielo.** Un
  termostato che non deumidifica, a cui si manda quel comando, non risponde
  «non so farlo»: non fa niente, e chi ha chiesto sente «fatto». Adesso il
  rifiuto arriva prima della chiamata, e dice cosa quel dispositivo sa fare
  davvero. Vale anche per le tapparelle che si aprono e si chiudono e basta.
- «A che temperatura e' impostato il termostato?» risponde con la temperatura
  **obiettivo**, che non e' quella misurata nella stanza: confonderle era il
  modo piu' facile per rispondere con sicurezza una cosa sbagliata.
- Una temperatura fuori dalla portata del termostato viene accorciata invece
  che rifiutata, ma **lo dice**: chi ha chiesto trenta gradi e sente «fatto»
  crede di averne trenta.
- **La casa finge di essere abitata quando si e' via.** Una luce che si
  accende alle 20:00 e si spegne alle 23:00 tutte le sere non dice «c'e'
  qualcuno», dice «c'e' un timer»: chi guarda una casa per tre sere di fila
  lo capisce, ed e' esattamente la persona da cui ci si vorrebbe difendere.
  Ogni sera vengono accese da tre a cinque luci, scaglionate lungo la serata
  a partire dal tramonto vero letto da Home Assistant, e il piano di stasera
  viene confrontato con quello di ieri: se ne esce uno uguale, si riprova.
- **La simulazione si rifiuta di partire con qualcuno in casa e smette da
  sola appena qualcuno rientra.** Una casa che continua a fingere mentre ci
  vive qualcuno accende e spegne le luci addosso alle persone, ed e' il modo
  piu' rapido perche' la funzione venga disattivata per sempre. E' cio' che
  la presenza (#22) serviva a rendere possibile.
- Il piano si rifa' ogni pomeriggio da solo: una casa illuminata la prima
  notte e buia le successive dice «qui non c'e' nessuno» piu' chiaramente di
  una casa sempre spenta.
- **L'allarme si comanda, e non si inserisce su una casa aperta.** Era il
  dominio per cui una famiglia installa la domotica, e l'unico completamente
  scoperto. Chiedendo di inserirlo con una finestra aperta l'assistente
  rifiuta e dice quale: un allarme inserito su una casa aperta suona da solo
  dopo dieci minuti, e chi lo ha inserito impara che l'allarme e'
  inaffidabile e smette di usarlo. Si puo' inserire lo stesso, ma dicendolo.
- **«Sono chiuse tutte le finestre?»** risponde con l'elenco vero. Home
  Assistant non ha un dominio «aperture»: porte e finestre sono
  `binary_sensor` con una `device_class`, le tapparelle sono `cover`, e `on`
  per un sensore di movimento non significa affatto aperto. Senza sensori
  configurati lo dice, invece di rassicurare a vuoto.
- Un sensore che non risponde non conta ne' come aperto ne' come chiuso:
  metterlo fra gli aperti impedirebbe di inserire l'allarme per un guasto.
- Quando l'allarme scatta, `casa.intrusione` finisce sul bus con dentro chi
  c'era in casa in quel momento — la prima domanda che si fa chi riceve
  l'avviso, e una risposta che dopo cinque minuti non e' piu' recuperabile.
  La notifica verso il telefono e' la issue #29 e non esiste ancora:
  l'evento la aspetta.

### Aggiunto
- **La casa sa se c'e' qualcuno.** `person` era fra i domini visibili e
  nessuna riga lo guardava: l'informazione piu' utile della domotica era
  anche l'unica che non si vedeva. Adesso c'e' un servizio che aggrega le
  persone in uno stato di casa e pubblica sul bus i quattro momenti che
  contano — qualcuno rientra, qualcuno esce, la prima persona torna, l'ultima
  se ne va — e una pastiglia nella barra dice quanti sono in casa.
- **Un buco del GPS non svuota la casa.** Il telefono perde il segnale in
  garage o in ascensore, Home Assistant lo racconta come «uscito» e ci
  ripensa un minuto dopo. Un'uscita si crede solo dopo un'attesa
  (`presenza.ritardo_uscita_secondi`, due minuti per difetto); un rientro si
  crede subito, perche' chi torna vuole la luce accesa adesso e un falso
  rientro non spegne niente a nessuno.
- Chi ha uno stato ignoto non conta ne' come presente ne' come assente: non
  sapere dov'e' una persona non e' saperla fuori.
- `GET /api/presenza` dice chi c'e', chi no, e chi e' in attesa di conferma —
  vedere l'attesa spiega perche' la casa non ha ancora reagito.

### Modificato
- I domini **osservati** sul bus degli eventi non sono piu' gli stessi di
  quelli **comandabili**: `person` non si comanda, e finche' passava solo
  cio' che si comanda la presenza non sarebbe mai arrivata a nessuno.

### Corretto
- **Spegnere una fonte di notizie adesso la spegne.** La scheda «Fonti &
  Notizie» mostrava le testate con i loro interruttori, e il codice leggeva
  un elenco fisso scritto dentro `news_search.py`: si disattivava ANSA
  Politica, si chiedevano le notizie, e arrivava politica da ANSA. Nessun
  errore — silenzio, che e' peggio, perche' non c'e' niente da leggere e si
  finisce col dare la colpa a se stessi.
- **Le categorie preferite di ogni profilo contano.** Erano
  nell'anagrafica dalla prima versione, si sceglievano nell'interfaccia, e
  non le leggeva nessuno: la rassegna era identica per tutti. Adesso due
  persone di casa con interessi diversi ricevono notizie diverse.
- Con piu' fonti accese si prende una notizia per fonte a giro. Leggerne
  quattro dalla prima significherebbe che la seconda non si sente mai, e chi
  l'ha accesa ha ragione di aspettarsi il contrario.
- Spegnere *tutte* le fonti di una categoria adesso lo dice, invece di
  ripiegare in silenzio su quelle scritte nel codice: era proprio la
  mancanza di effetto il difetto.

### Rimosso
- `assistant.language` e `security.protect_dashboard`: due opzioni che
  nessuna riga leggeva. La seconda aveva perfino una casella nelle
  impostazioni, mentre la rotta rispondeva `True` fisso — prometteva di poter
  *disattivare* la protezione della dashboard, cioe' di riaprire il difetto
  SEC-03 chiuso nella `0.1.0`, dove il blocco era un rettangolo CSS sopra
  dati gia' inviati. Un'opzione cosi' non va collegata, va tolta. Il
  linguaggio tornera' con la internazionalizzazione (issue #36).
- Con questa versione la suite non ha piu' nessun test marcato `xfail`: i due
  rimasti erano proprio questi difetti, dichiarati aperti dalla `0.1.0`.

### Aggiunto
- **Serrature, media player, aspirapolvere e ventilatori si comandano.**
  Erano elencati come comandabili nella mappa dispositivi e nessun tool
  sapeva toccarli: si chiedeva, e non succedeva niente. E' il difetto che
  erode la fiducia piu' di un errore esplicito, perche' non ha nemmeno un
  messaggio da leggere.
- **Prima di comandare si verifica che il dispositivo esista.**
  L'`entity_id` lo propone il modello, e il modello inventa nomi plausibili:
  `lock.porta_ingresso` esiste, `lock.porta_ingresso_principale` no. Senza
  controllo la richiesta partiva, Home Assistant rispondeva 200 senza fare
  niente, e l'assistente annunciava che la porta era chiusa mentre era
  aperta. L'errore propone anche l'alternativa piu' simile. Se la casa non
  risponde affatto il comando passa lo stesso: un controllo che trasforma
  «non lo so» in «non esiste» impedirebbe di comandare la casa proprio
  quando e' gia' in difficolta'.
- **Aprire una serratura chiede conferma**: una seconda richiesta entro un
  minuto, non un parametro `conferma=True` che il modello riempirebbe da
  solo — quello sarebbe teatro. E **dalla voce non si apre affatto**, finche'
  i profili vocali della `0.4.0` non permetteranno di sapere chi sta
  parlando: oggi chiunque si rivolga a un Echo agisce con l'identita' della
  sessione aperta.

### Modificato
- Il contesto della richiesta — correlazione, attore, canale — si sposta da
  `services/registro.py` a `domain/contesto.py`. E' un valore, non un
  servizio: il registro e' un suo consumatore, non il proprietario. Se ne e'
  accorto il test sulle regole di dipendenza quando il tool delle serrature
  ha avuto bisogno di sapere da quale canale arriva la richiesta.

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
