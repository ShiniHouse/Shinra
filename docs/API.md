# Riferimento delle API

> **Questo file e' generato.** Non si modifica a mano: lo riscrive
> `python scripts/genera_api.py` leggendo le rotte vere, e un test
> (`tests/unit/test_documentazione_api.py`) fallisce se resta indietro.
> Il testo di ogni riga e' la prima frase della documentazione della funzione
> che risponde: se una riga e' vuota o poco chiara, si corregge *li*.

Tutte le rotte stanno sotto `/api`, tranne le pagine, i file statici e il
canale degli eventi. Le risposte sono JSON.

## Chi puo' chiamare cosa

| Colonna «Chi» | Significato |
| :--- | :--- |
| pubblica | Nessuna credenziale. E' una scelta dichiarata: l'accesso stesso, lo stato del servizio, e l'endpoint Alexa, che si difende con la firma Amazon |
| sessione aperta | Qualunque persona entrata in casa (PIN, passkey o dispositivo fidato) |
| permesso `x` | Una sessione **il cui ruolo ha il permesso** `x` ([ADR 0004](adr/0004-identita-ruoli-e-permessi.md)). Senza, la risposta e' `403` con il nome del permesso che manca |
| amministratore | Solo il ruolo amministratore |

Senza sessione, le rotte protette rispondono `401`. L'autenticazione e' attiva
per difetto: una rotta e' pubblica solo se lo dice il codice.

## Come si autentica un client

1. `POST /api/auth/login` con `{"user_id": "...", "pin": "..."}`. Risponde con
   `{"success": true, "token": "...", "utente": {...}}` e imposta il cookie di
   sessione `shinra_sessione` (non leggibile da JavaScript). Dopo cinque PIN
   errati in cinque minuti risponde `429`.
2. Il browser rimanda il cookie da solo. Un client che non usa i cookie manda
   il token nell'intestazione `x-shinra-auth: Bearer <token>`.
3. La sessione dura trenta giorni. Una sessione scaduta risponde `401`; la
   dashboard lo dice e riporta all'accesso invece di ritentare.
4. `POST /api/auth/logout` la chiude.

I dettagli del flusso con le passkey e dei dispositivi fidati stanno nell'ADR
0004. Lo schema completo di richieste e risposte di ogni rotta lo serve
l'applicazione stessa, quando e' in funzione, su `/docs` (Swagger) e
`/openapi.json`.

## Le rotte (90)

### `alexa`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| POST | `/api/alexa` | pubblica | Endpoint per Amazon Alexa Skill Kit. |
| GET | `/api/alexa/interaction-model` | sessione aperta | Restituisce lo schema JSON Interaction Model per Amazon Alexa Skill Kit con nome personalizzato. |

### `aliases`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/aliases` | sessione aperta | Elenca gli alias: i nomi che la casa da' ai dispositivi («luce cucina»). |
| POST | `/api/aliases` | permesso `impostazioni.gestisci` | Crea o aggiorna un alias di dispositivo. |
| DELETE | `/api/aliases/{alias_id}` | permesso `impostazioni.gestisci` | Cancella un alias. |

### `auth`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| POST | `/api/auth/login` | pubblica | Verifica identita' e PIN, e apre una sessione. |
| POST | `/api/auth/logout` | pubblica | Chiude la sessione e cancella i cookie. |
| GET | `/api/auth/passkey` | sessione aperta | Le proprie, non quelle di casa: le passkey sono personali come i dispositivi fidati, e per lo stesso motivo non portano un permesso. |
| POST | `/api/auth/passkey/accesso/fine` | pubblica | Verifica la firma e apre la sessione. |
| POST | `/api/auth/passkey/accesso/inizio` | pubblica | Pubblica per mestiere: e' l'accesso. |
| POST | `/api/auth/passkey/registrazione/fine` | sessione aperta | Conclude la registrazione di una passkey sul dispositivo di chi e' entrato. |
| POST | `/api/auth/passkey/registrazione/inizio` | sessione aperta | Una passkey si aggiunge al proprio profilo, da dentro casa. |
| GET | `/api/auth/passkey/stato` | pubblica | Se qui le passkey si possono usare, e altrimenti perche' no. |
| DELETE | `/api/auth/passkey/{identificativo:path}` | sessione aperta | Toglie una passkey: da quel dispositivo non si entra piu' con quella. |
| GET | `/api/auth/profili` | pubblica | Chi puo' accedere, per la schermata di scelta. |
| GET | `/api/auth/status` | pubblica | Dice al client se deve autenticarsi, chi e', e cosa puo' fare. |

### `chat`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| POST | `/api/chat` | sessione aperta | Endpoint per richieste di chat / voce dall'interfaccia web o client locali. |

### `conoscenza`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/conoscenza/fatti-usati` | sessione aperta | I fatti che hanno contribuito all'ultima risposta, con i punteggi. |
| POST | `/api/conoscenza/reindicizza` | permesso `conoscenza.scrivi` | Ricalcola gli embedding mancanti, o tutti con `forza=true`. |
| GET | `/api/conoscenza/stato` | sessione aperta | Quanti fatti, quanti indicizzati, e se il recupero e' semantico. |

### `dispositivi`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/dispositivi` | sessione aperta | I dispositivi ricordati. |
| POST | `/api/dispositivi/revoca-tutti` | sessione aperta | Il telefono perso. |
| DELETE | `/api/dispositivi/{id_dispositivo}` | sessione aperta | Revoca un dispositivo fidato. Chi non e' amministratore puo' revocare solo i propri. |

### `ha`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/ha/entities` | sessione aperta | Restituisce tutte le entità HA raggruppate per dominio. |

### `health`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/health` | pubblica | Sonda di liveness: dice solo che il processo risponde. |

### `knowledge`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/knowledge` | sessione aperta | Elenca i fatti della conoscenza di casa. |
| POST | `/api/knowledge` | permesso `conoscenza.scrivi` | Aggiunge o aggiorna un fatto della conoscenza di casa. |
| DELETE | `/api/knowledge/{item_id}` | permesso `conoscenza.scrivi` | Cancella un fatto della conoscenza di casa. |

### `learning`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| POST | `/api/learning/answer` | sessione aperta | Manda la risposta a una domanda dell'intervista. |
| POST | `/api/learning/confirm-routine` | sessione aperta | Conferma la routine proposta alla fine dell'intervista. |
| POST | `/api/learning/start` | sessione aperta | Avvia l'intervista di apprendimento per un profilo. |
| GET | `/api/learning/status` | sessione aperta | Dice se c'e' un'intervista aperta e a che punto e'. |
| POST | `/api/learning/stop` | sessione aperta | Interrompe l'intervista di apprendimento. |

### `lingue`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/lingue` | sessione aperta | Le lingue che Shinra sa parlare, per il menu del profilo (issue #36). |

### `modes`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/modes` | sessione aperta | Elenca le routine (modalita') configurate. |
| POST | `/api/modes` | permesso `modalita.modifica` | Salva una routine, se il suo grafo sta in piedi. |
| POST | `/api/modes/simula` | permesso `modalita.modifica` | Cosa farebbe questa routine adesso, senza farlo. |
| POST | `/api/modes/valida` | sessione aperta | Cosa non va in questo grafo, senza salvarlo. |
| DELETE | `/api/modes/{mode_id}` | permesso `modalita.modifica` | Cancella una routine, e con lei le regole che il suo grafo aveva generato. |
| POST | `/api/modes/{mode_name}/activate` | permesso `modalita.attiva` | Esegue una routine per nome, con i permessi di chi la invoca. |

### `notifiche`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/notifiche/chiave` | sessione aperta | La chiave con cui il browser si registra. |
| POST | `/api/notifiche/dimentica` | sessione aperta | Toglie un telefono, **solo se e' di chi lo chiede**. |
| GET | `/api/notifiche/dispositivi` | sessione aperta | I telefoni registrati di chi chiede. |
| GET | `/api/notifiche/preferenze` | sessione aperta | Le preferenze di notifica di chi chiede: canali, categorie e cosa non si puo' silenziare. |
| POST | `/api/notifiche/preferenze` | sessione aperta | Cambia una preferenza. |
| POST | `/api/notifiche/prova` | sessione aperta | Manda una notifica di prova a chi la chiede. |
| POST | `/api/notifiche/sottoscrivi` | sessione aperta | Registra questo telefono per la persona della sessione. |

### `ollama`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/ollama/models` | sessione aperta | Recupera la lista dettagliata dei modelli disponibili direttamente da Ollama. |

### `pagine`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/` | pubblica | Serve la dashboard, oppure la pagina di accesso a chi non e' entrato. |

### `permessi`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/permessi` | sessione aperta | Il catalogo dei permessi: serve alla schermata dei ruoli. |

### `presenza`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/presenza` | sessione aperta | Chi c'e' in casa adesso. |

### `registro`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/registro` | amministratore | Chi ha fatto cosa in casa, e com'e' andata. |
| GET | `/api/registro/azioni` | amministratore | L'elenco dei tipi di azione presenti, per costruire i filtri. |

### `regole`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/regole` | sessione aperta | Le regole, con **quando scatteranno la prossima volta**. |
| POST | `/api/regole` | permesso `modalita.modifica` | Crea una regola del motore (innesco, condizioni, azioni). |
| PATCH | `/api/regole/{identificativo}` | permesso `modalita.modifica` | Modifica una regola esistente. |
| DELETE | `/api/regole/{identificativo}` | permesso `modalita.modifica` | Cancella una regola. |
| POST | `/api/regole/{identificativo}/prova` | permesso `modalita.modifica` | Esegue la regola saltando il trigger, **ma non le condizioni**. |

### `reminders`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/reminders` | sessione aperta | Elenca i promemoria in attesa. |
| POST | `/api/reminders` | sessione aperta | Crea un promemoria. |
| DELETE | `/api/reminders/{reminder_id}` | sessione aperta | Cancella un promemoria. |

### `ruoli`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/ruoli` | sessione aperta | Elenca i ruoli con i loro permessi. |
| POST | `/api/ruoli` | permesso `utenti.gestisci` | Crea o modifica un ruolo. |
| DELETE | `/api/ruoli/{id_ruolo}` | permesso `utenti.gestisci` | Cancella un ruolo personalizzato: i cinque predefiniti, e quelli con persone assegnate, no. |

### `satelliti`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/satelliti` | sessione aperta | Chi sta ascoltando, e da dove. |
| POST | `/api/satelliti` | sessione aperta | Un punto di ascolto si presenta e dice in quale stanza si trova. |

### `settings`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/settings` | permesso `impostazioni.gestisci` | Le impostazioni lette dal disco, con token e PIN mascherati. |
| POST | `/api/settings` | permesso `impostazioni.gestisci` | Salva le impostazioni. Un token o un PIN rimasti mascherati non sovrascrivono quelli veri. |

### `sources`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/sources` | sessione aperta | Elenca le fonti di notizie (feed RSS). |
| POST | `/api/sources` | sessione aperta | Aggiunge o aggiorna una fonte di notizie. |
| POST | `/api/sources/bulk-toggle` | sessione aperta | Accende o spegne tutte le fonti di notizie in una volta. |
| GET | `/api/sources/test` | sessione aperta | Prova un indirizzo di feed prima di aggiungerlo: dice se e' valido e mostra tre titoli. |
| DELETE | `/api/sources/{source_id}` | sessione aperta | Cancella una fonte di notizie. |

### `status`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/status` | sessione aperta | Controlla lo stato dei servizi (Ollama, Home Assistant). |

### `timers`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/timers` | sessione aperta | Elenca i timer attivi. |
| POST | `/api/timers` | sessione aperta | Crea un timer. |
| DELETE | `/api/timers/{timer_id}` | sessione aperta | Cancella un timer. |

### `tts`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| POST | `/api/tts` | sessione aperta | Genera audio vocale neurale MP3 in alta definizione. |
| GET | `/api/tts/voices` | sessione aperta | Restituisce le voci neurali disponibili nel server. |

### `users`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/users` | sessione aperta | Elenca i profili della casa. Il PIN non esce mai. |
| POST | `/api/users` | permesso `utenti.gestisci` | Crea o aggiorna un profilo. Declassare l'ultimo amministratore e' rifiutato. |
| POST | `/api/users/identify` | sessione aperta | Riconosce un profilo dal nome detto e restituisce il saluto adatto alla sua fascia d'eta'. |
| DELETE | `/api/users/{user_id}` | permesso `utenti.gestisci` | Cancella un profilo. |
| POST | `/api/users/{user_id}/pin` | permesso `utenti.gestisci` | Imposta o rimuove il PIN di un profilo. |

### `voce`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/voce/stato` | sessione aperta | Se il microfono si puo' accendere, e cosa dire se no. |
| POST | `/api/voce/trascrivi` | sessione aperta | Riceve una registrazione e restituisce cio' che e' stato detto. |

### `voci`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| GET | `/api/voci` | sessione aperta | Le voci sentite, la piu' recente per prima. |
| POST | `/api/voci/associa` | permesso `utenti.gestisci` | Dice di chi e' una voce, o la riporta a sconosciuta. |
| DELETE | `/api/voci/{person_id}` | permesso `utenti.gestisci` | Toglie la riga. |

### `ws`

| Metodo | Percorso | Chi | Cosa fa |
| :--- | :--- | :--- | :--- |
| WS | `/ws/eventi` | sessione aperta | Eventi in tempo reale verso la dashboard. |
