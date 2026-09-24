// ==================== LO STATO CHE ATTRAVERSA LE AREE ====================
//
// Dalla #145 le aree sono file separati, e ognuna teneva il suo stato in una
// `let` a colonna zero. Finche' quella variabile la leggeva solo il suo file
// andava bene. Undici non erano cosi': le scriveva un'area e le leggeva
// un'altra — `activeUserId` girava per cinque file — e guardando un file solo
// non c'era modo di sapere quali fossero. Lo spazio globale era il
// contenitore, cioe' nessun contenitore.
//
// Qui stanno quelle undici, e **solo** quelle. Una variabile che usa un'area
// sola resta dov'e': portarla qui non direbbe niente a nessuno, e allungare
// l'elenco finche' non lo legge piu' nessuno e' il modo di tornare al punto
// di partenza con un nome piu' bello.
//
// Due guardie tengono la regola, in `tests/unit/test_interfaccia.py`:
//
//   - `test_lo_stato_condiviso_sta_nel_contenitore` — se un `let` a colonna
//     zero viene letto da un altro file, dev'essere qui dentro;
//   - `test_ogni_campo_dello_stato_esiste_davvero` — perche' il contenitore
//     toglie una protezione: con le variabili sciolte, `activeUserIdd` era un
//     nome sconosciuto e ESLint lo fermava; `Stato.utenteAttivoo` invece e'
//     una proprieta' come un'altra, e vale `undefined` in silenzio.
//
// Riferimento: issue #34.

const Stato = {
    // --- chi sta usando la dashboard -------------------------------------

    /** L'identificativo del profilo a cui appartiene la sessione aperta.
     *  Lo scrive l'accesso, lo leggono la console, l'apprendimento e i
     *  timer per sapere a nome di chi parlano.
     *
     *  Parte da `alessio` e non da `null` perche' cosi' era prima, e questo
     *  lavoro sposta lo stato senza cambiarlo: il valore di partenza e' il
     *  profilo che c'e' in ogni installazione, e l'accesso lo riscrive
     *  appena qualcuno entra davvero. */
    utenteAttivo: 'alessio',

    /** I profili come li ha mandati il server, l'ultima volta che li si e'
     *  chiesti. Li disegnano la scheda Utenti, i ruoli e le passkey. */
    utenti: [],

    /** I ruoli e cosa puo' fare ciascuno. Li usa la scheda Ruoli per
     *  disegnarli e la scheda Utenti per dire a cosa si sta assegnando
     *  qualcuno. */
    ruoli: [],

    // --- l'editor a nodi ---------------------------------------------------

    /** Nodi, cavi, trascinamento e cavo in corso dell'editor delle routine.
     *  E' lo stato piu' letto della dashboard — ottanta riferimenti su
     *  quattro file: lo tocca il disegno, lo tocca la gestione dei nodi, e
     *  lo leggono le regole per sapere quale routine si sta modificando. */
    tela: {
        id: '',
        name: '',
        icon: 'workflow',
        description: '',
        trigger_phrases: [],
        nodes: [],
        edges: [],
        isDraggingNode: null,
        dragOffset: { x: 0, y: 0 },
        connectingSourceId: null,
    },

    /** Le routine come le ha mandate il server. Servono all'editor per
     *  aprirne una e alle regole per dire quale routine fanno partire. */
    routine: [],

    // --- la voce -----------------------------------------------------------

    /** Se Shinra deve stare zitta. Lo decide l'utente dalle impostazioni, lo
     *  rispetta la voce, e l'accesso lo rimette a posto allo sblocco.
     *
     *  La scelta sopravvive alla chiusura della pagina, quindi si rilegge da
     *  `localStorage` all'avvio — come faceva la variabile che stava in
     *  `voce.js`. Sotto try/catch: in una finestra anonima l'accesso a
     *  `localStorage` puo' sollevare, e una dashboard che non parte perche'
     *  non sa se deve stare zitta sarebbe un guasto sproporzionato. */
    voceZittita: (() => {
        try {
            return localStorage.getItem('shinra_voice_muted') === 'true';
        } catch {
            return false;
        }
    })(),

    /** L'audio che sta suonando adesso, per poterlo fermare quando ne parte
     *  un altro o quando si blocca lo schermo. */
    audioInCorso: null,

    /** Come si chiama l'assistente in questa casa. Lo si cambia dalle
     *  impostazioni, lo dice la console.
     *
     *  Il valore di partenza e' `Kyra`, che e' quello che c'era: le
     *  impostazioni lo riscrivono appena arrivano dal server, e cambiarlo
     *  qui sarebbe cambiare il comportamento dentro un lavoro che deve
     *  spostare lo stato e basta. */
    nomeAssistente: 'Kyra',

    // --- il canale degli eventi --------------------------------------------

    /** Se il canale degli eventi e' aperto. Lo sa `eventi.js`, e lo chiedono
     *  i timer per decidere se aggiornarsi da soli o aspettare un messaggio. */
    eventiCollegati: false,

    /** Quanto aspettare prima di riprovare a collegarsi, in millisecondi.
     *  Raddoppia a ogni tentativo fallito e riparte da capo quando la
     *  sessione torna buona — che e' perche' la tocca anche l'accesso. */
    attesaRiconnessione: 1000,

    /** I timer accesi in casa. Li disegna la scheda dei timer e li aggiorna
     *  il canale degli eventi quando ne scatta uno. */
    timerAttivi: [],
};
