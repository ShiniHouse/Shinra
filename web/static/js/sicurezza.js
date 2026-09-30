// Costruire HTML attaccando stringhe (issue #34).
//
// Il modo in cui la dashboard disegnava tutto era questo:
//
//     div.innerHTML = `<p>${testo}</p>`;
//
// Se `testo` viene dal server, dall'utente o dal modello, quello che
// entra fra i tag non e' testo: e' markup. Un `<img src=x onerror=...>`
// dentro il titolo di una notizia, o dentro il nome di un dispositivo,
// diventa codice che gira in una pagina che ha in mano la sessione
// dell'amministratore e il token di Home Assistant.
//
// Non e' un pericolo teorico: Shinra legge notizie, cerca sul web e
// riassume pagine, e quello che riassume finisce nella finestra della
// chat. Chi scrive il titolo di una notizia non e' di casa.
//
// La soluzione non e' ricordarsi di ripulire i valori — ci si dimentica,
// e ci si e' dimenticati: `_testoSicuro` esisteva ed era usato in dieci
// punti su novanta. La soluzione e' rovesciare il difetto: qui il testo
// e' testo per definizione, e l'HTML si dichiara.
//
//     div.innerHTML = _html`<p>${testo}</p>`;
//
// `_html` ripulisce **ogni** valore interpolato. Un pezzo che e' davvero
// markup si marca: `_grezzo(...)`. Un `_html` annidato e' gia' marcato,
// quindi comporre un elenco funziona senza dire niente:
//
//     _html`<ul>${voci.map((v) => _html`<li>${v.nome}</li>`)}</ul>`
//
// La marcatura sopravvive all'assegnazione perche' `innerHTML` chiama
// `toString()`.

class Sicuro {
    constructor(html) {
        this.html = html;
    }
    toString() {
        return this.html;
    }
}

const _FUGHE = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;',
};

// Anche gli apici e il backtick, non solo le parentesi angolate: un
// valore puo' finire dentro un attributo — `value="${x}"` — e li' basta
// chiudere le virgolette per aggiungerne un altro. `_testoSicuro`, che
// passava da `textContent`, ripuliva solo `& < >` e lasciava passare
// esattamente questo.
function _scappa(valore) {
    if (valore instanceof Sicuro) return valore.html;
    if (Array.isArray(valore)) return valore.map(_scappa).join('');
    if (valore === null || valore === undefined) return '';
    return String(valore).replace(/[&<>"'`]/g, (c) => _FUGHE[c]);
}

// Dice «questo pezzo e' markup, lascialo stare». Si usa quando l'HTML
// lo abbiamo scritto noi: un ramo di un ternario, un pezzo costruito
// prima. Mai su qualcosa che arriva dal server.
function _grezzo(html) {
    return new Sicuro(String(html ?? ''));
}

function _html(pezzi, ...valori) {
    let fuori = pezzi[0];
    for (let i = 0; i < valori.length; i++) {
        fuori += _scappa(valori[i]) + pezzi[i + 1];
    }
    return new Sicuro(fuori);
}

// Gli argomenti di un gesto, per il markup: `data-args="${_args(id, nome)}"`.
//
// Fino alla #34 un valore arrivava al gestore dentro una stringa JavaScript
// dentro un attributo — `onclick="fai('${x}')"` — e ogni apice o virgoletta
// nel valore chiudeva una delle due stringhe. Adesso l'attributo contiene
// soltanto JSON, e `Gesti` lo legge con `JSON.parse`: nessun valore e' mai
// codice, qualunque cosa contenga. Le fughe dell'HTML le mette `_html`,
// come per ogni altro valore interpolato.
function _args(...valori) {
    return JSON.stringify(valori);
}
