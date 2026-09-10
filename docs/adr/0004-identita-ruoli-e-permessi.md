# 0004 — Identita' per persona, ruoli personalizzati e dispositivi fidati

- **Stato:** Accettato
- **Data:** 2026-09-03
- **Attuazione:** `v0.1.0` l'identita', `v0.2.0` i ruoli e i dispositivi fidati

## Contesto

Shinra distingue gia' i profili di famiglia — adulto, ragazzo, bambino — e
calibra il tono delle risposte su di essi. Ma quella distinzione non regge
nulla: l'utente attivo si sceglie da un menu a tendina nella dashboard, e
`restricted_topics` esiste nel modello senza che una sola riga lo applichi.

Il punto da cui parte questa decisione: **un permesso vale quanto l'identita'
su cui poggia.** Con un unico PIN di casa, un flag «questo bambino non puo'
accendere le luci» e' un promemoria educato — basta cambiare profilo dal menu.
Se il sistema deve arrivare a comandare serrature e allarme (milestone
`v0.3.0`), un modello del genere non e' accettabile.

Serve inoltre che la protezione non diventi un fastidio: un PIN richiesto a
ogni accesso su un telefono viene disattivato entro una settimana, e a quel
punto la casa e' aperta come prima.

## Decisione

### 1. Un PIN per persona, non uno per la casa

Ogni profilo utente ha il proprio PIN. All'accesso si sceglie chi si e' e lo si
digita; la sessione porta con se' l'identita' reale, non una selezione da menu.
Il campo `pin` esiste gia' in `UserProfile` ed e' sempre stato inutilizzato.

Conseguenza: chi non ha un PIN configurato non puo' accedere. Un profilo per un
bambino piccolo puo' non averlo affatto — usera' i dispositivi condivisi gia'
sbloccati da un adulto.

### 2. Ruoli personalizzati, non flag fissi

I permessi non sono attributi del profilo ma di un **ruolo**, e i ruoli si
creano. Quattro sono predefiniti e modificabili — Amministratore, Adulto,
Ragazzo, Ospite — e se ne possono aggiungere altri: «Collaboratrice
domestica», «Ospite fine settimana», «Nonno».

Un permesso e' un'azione nominata. Insieme minimo:

| Permesso | Cosa consente |
| :--- | :--- |
| `dispositivi.comanda` | Luci, prese, clima, tapparelle |
| `sicurezza.comanda` | Serrature, allarme — **separato**: sbagliare qui ha conseguenze diverse |
| `modalita.attiva` | Routine e scenari |
| `modalita.modifica` | Creare o alterare una routine |
| `conoscenza.leggi` / `conoscenza.scrivi` | La knowledge base di casa |
| `utenti.gestisci` | Creare, modificare, cancellare profili |
| `impostazioni.gestisci` | Token, modello, configurazione |

Una routine puo' fare qualunque cosa, comprese le azioni che un permesso
negherebbe: **l'esecuzione di una routine verifica i permessi di chi la
invoca**, non quelli di chi l'ha scritta. Altrimenti il controllo si aggira
scrivendo una routine.

### 3. Dispositivi fidati

Dopo il primo accesso con PIN, il dispositivo puo' essere ricordato: riceve una
credenziale a lunga durata legata a un nome scelto dall'utente («iPhone di
Alessio»). Trenta giorni, rinnovati a ogni uso. Nelle impostazioni compare
l'elenco dei dispositivi fidati con l'ultimo accesso, e ognuno e' revocabile
singolarmente.

E' cio' che rende sopportabile un PIN per persona su un telefono. Senza, la
protezione verrebbe disattivata dall'uso quotidiano.

## Alternative considerate

**PIN unico di casa con permessi indicativi.** Piu' semplice e piu' comodo, ma
i permessi diventerebbero una cortesia e non un controllo. Inaccettabile una
volta che il sistema comanda serrature.

**Certificato TLS client sul dispositivo.** E' il «certificare il dispositivo»
in senso stretto, e sarebbe la protezione piu' forte. Scartato per il costo
d'uso: installazione manuale su ogni telefono, scadenze, rinnovi. In una casa
verrebbe abbandonato.

**Passkey (WebAuthn) come meccanismo primario.** Tecnicamente superiore: la
credenziale sta nel telefono e si sblocca con impronta o riconoscimento del
volto, non c'e' nulla da digitare ne' da indovinare, e un familiare non puo'
usare il dispositivo di un altro. Non scartata ma **rimandata**: richiede
HTTPS valido (presente) e un livello di gestione delle credenziali che ha
senso costruire quando l'impianto delle sessioni e' assestato. Pianificata per
la `v0.4.0`, dove sostituira' il PIN come metodo consigliato lasciandolo come
ricaduta.

**Profili vocali Alexa.** Le richieste da un Echo possono portare un
identificativo della persona che ha parlato, se i profili vocali sono
configurati. E' l'unico modo per applicare i permessi al canale vocale, dove
oggi chiunque parli ottiene tutto. Pianificato con la verifica della firma
Alexa e i satelliti vocali della `v0.4.0`.

## Conseguenze

**Positive.** I permessi diventano controlli reali. La casa puo' arrivare a
gestire serrature e allarme con un modello di autorizzazione che regge. I ruoli
personalizzati coprono situazioni che flag fissi non prevedono.

**Negative.** L'accesso diventa piu' complesso: scelta dell'utente piu' PIN, e
una schermata di gestione di ruoli e dispositivi da progettare. Chi oggi apre
la dashboard e la usa dovra' identificarsi la prima volta su ogni dispositivo.

**Rischio da sorvegliare.** Un modello di permessi troppo minuto diventa
ingestibile e viene disattivato in blocco. Si parte dai sette permessi
elencati; se ne aggiungono altri solo davanti a un bisogno reale.

## Aggiornamento — il buco vocale era piu' largo di come l'avevamo scritto

*Aggiunto il 2026-09-10 con la issue #48.*

Qui sopra si leggeva: «chiunque si rivolga a un Echo agisce con l'identita'
configurata nella sessione». Misurandolo prima di ripararlo, la frase si e'
rivelata ottimista. Questa e' la misura:

    attore_nel_contesto      = None
    profilo_corrente         = None
    puo_aprire_serrature     = True

Il canale Alexa **non impostava mai l'attore**. `permessi.profilo_corrente()`
restituiva quindi `None`, e `ha_permesso(None, ...)` concede tutto — perche'
`None` significa «nessuna identita' in gioco»: l'autenticazione spenta, o lo
scheduler che annuncia un promemoria. Non era un problema di identita'
*sbagliata*: **a voce nessun permesso e' mai stato verificato.** L'identita'
della sessione veniva passata all'agente per il tono e la memoria, e li' si
fermava.

Altri due difetti dello stesso ceppo, trovati leggendo:

- `LaunchRequest` impostava la sessione sul **primo profilo dell'elenco**,
  cioe' l'amministratore, e lo salutava per nome a chiunque aprisse la skill.
- «sono Sonia» cambiava profilo **senza nessuna prova**. Un'identita' che si
  ottiene dicendola non e' un'identita', e rende priva di significato ogni
  riga scritta sui permessi del canale vocale.

A trattenere qualcosa restavano due divieti scritti a mano nelle capacita' —
niente serrature da Alexa, una conferma in piu' per l'allarme — e nient'altro.
Hanno retto, ma erano l'unica cosa che reggeva.

### Cosa cambia

**Tre esiti al posto di due.** `profilo_corrente()` distingue «un profilo»,
«nessuna identita' in gioco» (`None`, concede tutto: e' il sistema che agisce)
e **«identita' ignota»** — qualcuno sta agendo e non si sa chi. Le prime due
erano indistinguibili dalla terza, e la terza e' il contrario della seconda.

**L'identita' vocale viene da Amazon, non da cio' che si dice.**
`context.System.person.personId` e' un identificativo opaco e stabile della
persona che ha parlato, presente quando in casa sono configurati i profili
vocali. Si associa a un profilo Shinra dalle impostazioni, una volta sola.
Non e' una password — chi imita una voce puo' farsi riconoscere — ma e'
l'unico segnale di identita' che il canale offra.

**Il silenzio non concede.** Una voce non riconosciuta agisce con il ruolo
`alexa.ruolo_voce_sconosciuta` (`guest` per difetto). Un ruolo inesistente non
da' permessi: e' la direzione giusta in cui sbagliare.

**Il cambio di profilo parlato e' stato tolto.** Non ne resta una versione
attenuata: resta una spiegazione di come farsi riconoscere davvero.

**`sicurezza.comanda` diventa raggiungibile da voce**, ma solo con identita'
riconosciuta *e* conferma esplicita *e* il permesso. Il divieto in blocco non
sparisce: si stringe attorno al caso che lo giustificava. Chi non si sa chi
sia non apre serrature e non disinserisce l'allarme — nemmeno confermando.

**Cio' che resta aperto.** Un profilo vocale distingue una voce, non
autentica una persona: una registrazione o un'imitazione possono superarlo.
Per questo la conferma esplicita resta anche per chi e' riconosciuto, e il
codice dell'allarme — che Home Assistant verifica — resta la protezione vera.
E finche' i profili vocali non sono configurati in casa, **tutte** le voci
sono sconosciute: la configurazione va fatta dall'app Alexa, Shinra non puo'
farla al posto di nessuno.
