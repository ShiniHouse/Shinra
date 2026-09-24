// ==================== I GESTI CHE LA PAGINA PUO' CHIEDERE ====================
//
// Fino alla #179 il markup chiamava le funzioni cosi':
//
//     <button onclick="switchTab('console')">
//
// Un attributo `onclick` e' una stringa che il browser esegue nello **spazio
// globale**. Funziona finche' i copioni sono copioni; il giorno che diventano
// moduli ES non funziona piu', perche' un modulo non mette niente in globale:
// i clic smetterebbero di fare qualcosa, tutti insieme e in silenzio. E'
// l'unico vero ostacolo ai moduli, ed e' il motivo per cui l'ADR 0006 dice
// che il lavoro della #34 non e' aggiungere `type="module"`.
//
// Adesso il markup **nomina** un gesto, e non esegue niente:
//
//     <button data-gesto="switchTab" data-testo="console">
//
// Chi ascolta e' un guardiano solo, su `document`. Due conseguenze buone
// oltre ai moduli: un elemento disegnato dal JavaScript dopo il caricamento
// funziona senza dover collegare niente, e le funzioni che la pagina puo'
// chiamare sono un elenco scritto — `Gesti.registra(...)` in fondo a ogni
// area — invece di qualcosa che si scopre cercando `onclick` nel markup.
//
// Riferimento: issue #34, ADR 0006.

const Gesti = {
    /** Dal nome del gesto alla funzione che lo fa. */
    _fatti: new Map(),

    /** L'attributo da leggere, per tipo di evento.
     *
     *  Sono quattro nomi diversi e non un `data-gesto` con un `data-evento`
     *  accanto: cosi' un elemento puo' averne piu' d'uno — un campo che fa
     *  una cosa mentre si scrive e un'altra quando si esce — e chi legge il
     *  markup vede subito quando scatta. */
    EVENTI: {
        click: 'gesto',
        change: 'alCambio',
        input: 'mentreScrivi',
        submit: 'allInvio',
    },

    /** Registra un'area intera: `Gesti.registra({ switchTab, setPalette })`.
     *
     *  Si passa un oggetto con la scorciatoia di JavaScript, che e' la stessa
     *  forma di una lista di `export`: il giorno dei moduli, questa riga
     *  diventa quella. */
    registra(funzioni) {
        for (const [nome, funzione] of Object.entries(funzioni)) {
            if (typeof funzione !== 'function') {
                console.error(`Gesti: «${nome}» non e' una funzione`);
                continue;
            }
            if (this._fatti.has(nome) && this._fatti.get(nome) !== funzione) {
                // Due aree che registrano lo stesso nome vuol dire che una
                // delle due sta rispondendo a clic che non sono suoi.
                console.error(`Gesti: «${nome}» e' registrato due volte`);
            }
            this._fatti.set(nome, funzione);
        }
    },

    /** Se un gesto con questo nome esiste. Lo usa la guardia dei test. */
    conosce(nome) {
        return this._fatti.has(nome);
    },

    /** L'argomento da passare, letto dal markup.
     *
     *  Il vocabolario e' chiuso apposta: indovinare l'argomento
     *  dall'elemento — «se e' un input passagli il valore» — sembra comodo
     *  finche' non si incontra `openModularModeBuilder(existingId = null)`,
     *  che chiamata con un evento aprirebbe l'editor su una routine che si
     *  chiama `[object PointerEvent]`.
     *
     *  Nessun attributo vuol dire **nessun argomento**, non «l'evento». */
    _argomento(elemento, evento) {
        if ('testo' in elemento.dataset) return [elemento.dataset.testo];
        const da = elemento.dataset.argomento;
        if (da === undefined) return [];
        if (da === 'valore') return [elemento.value];
        if (da === 'spunta') return [elemento.checked];
        if (da === 'evento') return [evento];
        if (da === 'vero') return [true];
        if (da === 'falso') return [false];
        if (da === 'niente') return [null];
        console.error(`Gesti: argomento «${da}» sconosciuto su`, elemento);
        return [];
    },

    _esegui(evento, attributo) {
        const elemento = evento.target.closest(`[data-${attributo}]`);
        if (!elemento) return;
        const nome = elemento.dataset[this.EVENTI[evento.type]];
        const funzione = this._fatti.get(nome);
        if (!funzione) {
            // Rumoroso apposta: un gesto scritto nel markup e mai registrato
            // e' un pulsante che non fa niente, e senza questa riga non
            // lascerebbe alcuna traccia.
            console.error(`Gesti: nessuno sa fare «${nome}»`, elemento);
            return;
        }
        funzione(...this._argomento(elemento, evento));
    },

    /** Mette in ascolto la radice. Una volta sola, per tutta la pagina. */
    ascolta(radice) {
        for (const tipo of Object.keys(this.EVENTI)) {
            const attributo = this.EVENTI[tipo].replace(/[A-Z]/g, (l) => '-' + l.toLowerCase());
            radice.addEventListener(tipo, (evento) => this._esegui(evento, attributo));
        }
    },
};

Gesti.ascolta(document);
