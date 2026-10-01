"""Nessun HTML costruito attaccando stringhe: ogni valore che finisce nella pagina viene scappato.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
from aiuti_frontend import (
    CARTELLA_JS,
    _copioni,
    _esegui_con_node,
    _funzione_javascript,
    _riga_javascript,
    _senza_commenti_html,
    _testo,
)

# ------------------------------------------- HTML costruito attaccando stringhe

# Le aree ancora da convertire a `_html`. L'elenco si accorcia, mai il
# contrario: `test_la_lista_dei_non_convertiti_non_si_allunga` lo impedisce.
# Un file nuovo nasce fuori da qui, quindi nasce gia' protetto.
NON_ANCORA_CONVERTITI: set[str] = set()


# Un tag vero: `<` seguito da un nome e poi da spazio, `>` o `/`. Serve a
# distinguere il markup da un confronto (`i < n`, che ha uno spazio in
# mezzo) e da un indirizzo.
TAG = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*[\s/>]")


# Dove puo' cominciare un'espressione regolare: dopo uno di questi una
# barra apre una regex, non una divisione.
PRIMA_DI_UNA_REGEX = set("(,=:[!&|?{};+-*%~^") | {""}


def _aperture_di_template(sorgente: str) -> list[tuple[int, str]]:
    r"""Ogni template literal del sorgente: dove si apre e cosa contiene.

    Un `${...}` dentro un template puo' contenere un altro template, e la
    fine di quello annidato **non** e' la fine di quello che lo contiene.
    Una guardia che cercasse l'apice inverso successivo scambierebbe una
    chiusura per un'apertura — e' quello che faceva la prima versione, e
    si e' vista sbagliare su `_html\`<ul>${v.map((x) => _html\`<li>...`.

    Quindi si legge il sorgente una volta sola tenendo una pila, e si
    saltano stringhe, commenti ed espressioni regolari, dove un apice
    inverso non apre niente.
    """
    pila: list[list] = []  # ["tpl", inizio, pezzi] oppure ["expr", profondita]
    aperti: list[tuple[int, list]] = []
    trovati = []
    i, n = 0, len(sorgente)
    ultimo_significativo = ""

    def dentro_un_template() -> bool:
        return bool(pila) and pila[-1][0] == "tpl"

    while i < n:
        c = sorgente[i]

        if dentro_un_template():
            if c == "\\":
                i += 2
                continue
            if c == "$" and sorgente[i : i + 2] == "${":
                # Un segnaposto al posto dell'espressione: serve a
                # distinguere un template vuoto da un involucro — cioe' da
                # uno fatto di soli `${...}` — che fuori di qui sono due
                # cose molto diverse.
                aperti[-1][1].append("\x00")
                pila.append(["expr", 0])
                i += 2
                continue
            if c == "`":
                inizio_tpl, pezzi = aperti.pop()
                pila.pop()
                trovati.append((inizio_tpl, "".join(pezzi)))
                i += 1
                continue
            aperti[-1][1].append(c)
            i += 1
            continue

        # Qui siamo in codice: o al primo livello, o dentro un `${...}`.
        if c in "'\"":
            i += 1
            while i < n and sorgente[i] != c:
                i += 1 + (sorgente[i] == "\\")
            i += 1
            ultimo_significativo = "x"
            continue
        if sorgente[i : i + 2] == "//":
            i = sorgente.find("\n", i)
            if i < 0:
                break
            continue
        if sorgente[i : i + 2] == "/*":
            i = sorgente.find("*/", i) + 2
            continue
        if c == "/" and ultimo_significativo in PRIMA_DI_UNA_REGEX:
            i += 1
            in_classe = False
            while i < n and (in_classe or sorgente[i] != "/"):
                if sorgente[i] == "\\":
                    i += 1
                elif sorgente[i] == "[":
                    in_classe = True
                elif sorgente[i] == "]":
                    in_classe = False
                i += 1
            i += 1
            ultimo_significativo = "x"
            continue
        if c == "`":
            pila.append(["tpl", i, []])
            aperti.append((i, pila[-1][2]))
            i += 1
            continue
        if pila and pila[-1][0] == "expr":
            if c == "{":
                pila[-1][1] += 1
            elif c == "}":
                if pila[-1][1] == 0:
                    pila.pop()
                    i += 1
                    continue
                pila[-1][1] -= 1

        if not c.isspace():
            ultimo_significativo = c
        i += 1

    # Arrivare in fondo con qualcosa ancora aperto vuol dire aver perso il
    # filo: una stringa saltata male, un commento, una regex. E allora il
    # guasto non e' l'elenco sbagliato — e' che l'elenco **si accorcia**,
    # perche' un template che non si chiude non viene mai riportato. Una
    # guardia che, quando si confonde, tace, e' peggio di nessuna guardia.
    # E' successo davvero: su `fonti.js`, tagliato da `_senza_commenti`,
    # questa funzione non vedeva meta' file e una mutazione vera e' passata.
    if pila:
        riga = sorgente.count("\n", 0, aperti[0][0]) + 1 if aperti else "?"
        raise ValueError(f"sorgente non bilanciato: qualcosa aperto alla riga {riga} non si chiude")

    return sorted(trovati)


def _aperture_di_markup(sorgente: str) -> list[int]:
    """Gli apici inversi che aprono un template che contiene markup."""
    return [i for i, contenuto in _aperture_di_template(sorgente) if TAG.search(contenuto)]


# I tre sbocchi: qui una stringa smette di essere una stringa e diventa la
# pagina. `showModal` e' `innerHTML` con un altro nome.
SBOCCO = re.compile(r"(?:\.innerHTML\s*=|\.insertAdjacentHTML\s*\([^`]*,|\bshowModal\s*\()\s*$", re.S)


def _template_da_marcare(sorgente: str) -> list[tuple[int, str]]:
    """I template che devono passare da `_html`, e per quale dei tre motivi.

    **markup** — fra gli apici c'e' un tag. E' il caso ovvio.

    **sbocco** — sta subito dopo un `innerHTML =`, o dentro uno
    `showModal(`. Qui il tag puo' non esserci: in
    `innerHTML = \u0060${voci.map(...)}\u0060` fra gli apici non c'e' niente,
    eppure e' markup — quello vero sta nei pezzi che l'elenco produce.
    Senza `_html` l'elenco diventa `String(array)`, cioe' i pezzi separati
    da virgole.

    **involucro** — fra gli apici c'e' **un solo** `${...}` e nient'altro,
    neppure uno spazio. E' la stessa cosa di sopra quando il risultato
    passa per una variabile prima di finire nella pagina. Un involucro
    senza `_html` non fa niente che `String(...)` non faccia gia', quindi
    chiederglielo non costa nulla.

    Lo spazio conta davvero: `\u0060${nome} ${cognome}\u0060` non e' un
    involucro, e' una frase che si costruisce. La prima versione di questa
    regola non li distingueva e accusava tre punti innocenti.

    I primi tentativi di questa guardia avevano solo il primo motivo, e
    cinque mutazioni su dodici non mordevano — tutte e cinque di questa
    forma.
    """
    da_marcare = []
    for i, contenuto in _aperture_di_template(sorgente):
        if TAG.search(contenuto):
            da_marcare.append((i, "markup"))
        elif SBOCCO.search(sorgente[:i]):
            da_marcare.append((i, "sbocco"))
        elif contenuto and set(contenuto) == {"\x00"}:
            da_marcare.append((i, "involucro"))
    return da_marcare


# I tre sbocchi: qui una stringa smette di essere una stringa e diventa
# la pagina. `showModal` e' `innerHTML` con un altro nome.
SBOCCHI = re.compile(r"\.innerHTML\s*=\s*|\.insertAdjacentHTML\s*\(|\bshowModal\s*\(")


def _fine_istruzione(sorgente: str, inizio: int) -> int:
    """Dove finisce l'istruzione che comincia a `inizio`.

    Il primo `;` o fine riga a parentesi chiuse, saltando stringhe,
    template e commenti — dove un `;` non conta.
    """
    i, n = inizio, len(sorgente)
    profondita = 0
    while i < n:
        c = sorgente[i]
        if c in "'\"":
            i += 1
            while i < n and sorgente[i] != c:
                i += 1 + (sorgente[i] == "\\")
            i += 1
            continue
        if c == "`":
            # Salta il template intero, annidati compresi.
            interni = [a for a, _ in _aperture_di_template(sorgente[i:]) if a == 0]
            livello, j = 0, i
            while j < n:
                if sorgente[j] == "\\":
                    j += 2
                    continue
                if sorgente[j] == "`":
                    livello += 1 if livello == 0 else 0
                    j += 1
                    if livello:
                        # cerca la chiusura contando i `${`
                        graffe = 0
                        while j < n:
                            if sorgente[j] == "\\":
                                j += 2
                                continue
                            if sorgente[j : j + 2] == "${":
                                graffe += 1
                                j += 2
                                continue
                            if graffe and sorgente[j] == "}":
                                graffe -= 1
                            elif not graffe and sorgente[j] == "`":
                                j += 1
                                break
                            elif graffe and sorgente[j] == "`":
                                # template annidato dentro l'espressione
                                k = _fine_istruzione(sorgente, j)
                                j = max(k, j + 1)
                                continue
                            j += 1
                        break
                    continue
                j += 1
            i = j
            del interni
            continue
        if sorgente[i : i + 2] == "//":
            i = sorgente.find("\n", i)
            if i < 0:
                return n
            continue
        if c in "([{":
            profondita += 1
        elif c in ")]}":
            profondita -= 1
            if profondita < 0:
                return i
        elif c == ";" and profondita <= 0:
            return i
        i += 1
    return n


def test_il_markup_con_valori_dentro_passa_da_html():
    """Costruire markup attaccando stringhe e' come costruire SQL attaccando
    stringhe, e per la stessa ragione.

        div.innerHTML = `<p>${testo}</p>`;

    Se `testo` viene dal server, dall'utente o dal modello, quello che entra
    fra i tag non e' testo: e' markup. Shinra legge notizie, cerca sul web e
    riassume pagine, e quello che riassume finisce nella finestra della chat
    — in una pagina che ha in mano la sessione dell'amministratore e il
    token di Home Assistant. Chi scrive il titolo di una notizia non e' di
    casa.

    `_html` ripulisce ogni valore interpolato, e un pezzo che e' davvero
    markup si dichiara con `_grezzo`. Il difetto e' rovesciato: prima
    bisognava ricordarsi di ripulire, e non ci si ricordava — `_testoSicuro`
    esisteva ed era usato in dieci punti su novanta.

    Riferimento: issue #34.
    """
    colpevoli = []
    for percorso in _copioni():
        if percorso.name in NON_ANCORA_CONVERTITI or percorso.name == "sicurezza.js":
            continue
        # Il testo grezzo, non `_senza_commenti`: quella funzione toglie da
        # `//` a fine riga, e in `fonti.js` ci sono decine di `https://...`
        # dentro apici. Tagliarle lascia stringhe non chiuse, e lo scanner
        # qui sotto perde il conto e smette di vedere meta' file — l'ho
        # scoperto perche' una mutazione su `fonti.js` non mordeva.
        # I commenti veri li salta gia' lo scanner, che sa dove guardare.
        testo = _testo(percorso)
        for i, perche in _template_da_marcare(testo):
            if not testo[:i].rstrip().endswith("_html"):
                riga = testo.count("\n", 0, i) + 1
                colpevoli.append(f"{percorso.name}:{riga} ({perche}) -> {testo[i : i + 60]!r}")

    assert not colpevoli, "markup costruito attaccando stringhe, senza passare da `_html`:\n" + "\n".join(
        colpevoli
    )


def test_la_guardia_riconosce_il_markup_da_un_confronto():
    """`i < n` non e' un tag, e `<p>` si'.

    Senza questa distinzione la guardia griderebbe su ogni ciclo, qualcuno
    la allenterebbe, e da quel momento non guarderebbe piu' niente. E il
    contrario e' peggio: una guardia che scambia una chiusura per
    un'apertura da' un elenco di colpevoli inventati, e lo stesso finisce.
    """
    assert _aperture_di_markup("const a = `<p>${x}</p>`;") == [10]
    assert _aperture_di_markup("const a = _html`<p>${x}</p>`;") == [15]
    assert _aperture_di_markup("const a = `/api/timers/${id}`;") == []
    assert _aperture_di_markup("const a = `${i} < ${n} elementi`;") == []
    assert _aperture_di_markup("const a = `stato-${x}`;") == []

    # Uno annidato dentro un altro: due aperture, non tre. La chiusura di
    # quello di dentro vede `)}</ul>` e non deve contarsi.
    assert _aperture_di_markup("_html`<ul>${v.map((x) => _html`<li>${x}</li>`)}</ul>`") == [5, 30]

    # Un apice inverso dentro una stringa, un commento o una regex non apre
    # niente.
    assert _aperture_di_markup("const a = '`<p>';") == []
    assert _aperture_di_markup("// `<p>${x}</p>`\nconst a = 1;") == []
    assert _aperture_di_markup("const a = /[`<p>]/.test(x);") == []

    # Un indirizzo dentro apici non e' un commento. `_senza_commenti`
    # taglierebbe da `//` in poi lasciando la stringa aperta, e da li' in
    # avanti lo scanner perderebbe il conto: e' successo su `fonti.js`, e
    # una mutazione vera e' passata inosservata per questo.
    assert _aperture_di_markup("const u = 'https://esempio.it/x';\nconst a = `<p>${x}</p>`;") == [44]

    # E se il filo si perde, lo deve dire. Un apice inverso che non si
    # chiude e' il sintomo di uno scanner che ha sbagliato a saltare
    # qualcosa: tacere vorrebbe dire restituire un elenco corto e sembrare
    # a posto.
    with pytest.raises(ValueError, match="non bilanciato"):
        _aperture_di_markup("const a = `<p>manca la chiusura;")

    # E il contenuto di un template annidato non finisce in quello esterno:
    # se cosi' fosse, ogni esterno risulterebbe markup per colpa di dentro.
    esterni = _aperture_di_template("`fuori ${`<p>dentro</p>`} ancora`")
    assert esterni[0][1] == "fuori \x00 ancora", esterni

    # Un involucro — un solo `${...}` e nient'altro — va marcato anche
    # senza tag dentro: quello vero sta nei pezzi che l'espressione
    # produce. Una frase costruita a pezzi, invece, no.
    assert _template_da_marcare("const a = `${voci.map(f)}`;") == [(10, "involucro")]
    assert _template_da_marcare("const a = `${nome} ${cognome}`;") == []
    assert _template_da_marcare("x.innerHTML = `${voci}`;") == [(14, "sbocco")]
    assert _template_da_marcare("showModal(`${voci}`);") == [(10, "sbocco")]
    assert _template_da_marcare("const a = `ciao ${nome}`;") == []


def test_la_lista_dei_non_convertiti_non_si_allunga():
    """L'elenco e' un debito dichiarato, non un permesso.

    Serve perche' convertire novanta punti in una volta sola darebbe una
    modifica che nessuno puo' rivedere. Ma un elenco di eccezioni che
    qualcuno puo' allungare non e' un debito: e' una porta. Questa guardia
    la tiene aperta in una direzione sola.

    Un copione nuovo non e' nell'elenco, quindi nasce gia' protetto.
    """
    esistenti = {p.name for p in _copioni()}
    fantasmi = NON_ANCORA_CONVERTITI - esistenti
    assert not fantasmi, f"nell'elenco ci sono file che non esistono piu': {fantasmi}"

    # Il numero scende a ogni passo. Alzarlo vuol dire aver aggiunto
    # un'eccezione invece di toglierne una.
    # L'elenco e' vuoto: ogni area passa da `_html`. Resta la costante, e
    # resta questa guardia, perche' la strada facile per far passare un
    # copione nuovo che concatena e' aggiungerlo qui invece di sistemarlo.
    assert not NON_ANCORA_CONVERTITI, (
        f"l'elenco e' tornato a contenere qualcosa: {sorted(NON_ANCORA_CONVERTITI)}. "
        "Era vuoto: se un'area nuova concatena, si sistema l'area, non l'elenco"
    )


def test_una_notizia_ostile_non_diventa_codice_nella_chat():
    """La dimostrazione, eseguita.

    Prima di questa modifica, dando in pasto alla chat una risposta che
    contiene `<img src=x onerror=...>` — cosa che basta a ottenere mettendo
    quel testo nel titolo di una notizia che Shinra riassume — il tag
    finiva nella pagina intatto, e l'`onerror` girava con la sessione
    dell'amministratore aperta.

    Finiva in **due** punti: fra i tag, e dentro l'attributo `onclick` del
    pulsante «Riascolta», dove una sola apice chiusa bastava.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    ostile = 'Notizie: <img src=x onerror=\\"rubo()\\"> e un\'apice'

    prova = (
        _testo(CARTELLA_JS / "sicurezza.js")
        + """
let activeAssistantName = 'Kyra';
let disegnato = '';
const container = { appendChild() {}, scrollTop: 0, scrollHeight: 0 };
const document = {
    getElementById: () => container,
    createElement: () => ({ set innerHTML(v) { disegnato = String(v); }, className: '' }),
};
function safeCreateIcons() {}
function speakText() {}
"""
        + _funzione_javascript(_testo(CARTELLA_JS / "conversazione.js"), "appendAssistantMessage")
        + f"""
appendAssistantMessage("{ostile}");
console.log(JSON.stringify({{
    intatto: disegnato.includes('<img src=x'),
    scappato: disegnato.includes('&lt;img src=x'),
    apiceNudaNellAttributo: /data-gesto="speakText" data-args="[^"]*'[^"]*"/.test(disegnato),
}}));
"""
    )

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert not visto["intatto"], "il tag arriva nella pagina intatto: e' esecuzione di codice altrui"
    assert visto["scappato"], "il testo non compare affatto: la guardia non sta guardando niente"
    assert not visto[
        "apiceNudaNellAttributo"
    ], "un apice nudo nell'attributo dei dati: il valore smette di essere solo un valore"


def test_html_ripulisce_anche_cio_che_finisce_in_un_attributo():
    """`_testoSicuro`, che c'era prima, passava da `textContent`: ripuliva
    `& < >` e lasciava passare apici e virgolette.

    Basta per un valore fra i tag. Non basta per `value="${x}"`, dove una
    virgoletta chiude l'attributo e ne apre un altro — ed e' esattamente
    quello che faceva l'elenco delle stanze note.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = _testo(CARTELLA_JS / "sicurezza.js") + r"""
const casi = {
    tag: String(_html`<p>${'<b>ciao</b>'}</p>`),
    virgolette: String(_html`<input value="${'" onfocus="rubo()'}">`),
    apici: String(_html`<input value='${"' onfocus='rubo()"}'>`),
    backtick: String(_html`<p>${'`${rubo()}`'}</p>`),
    vuoto: String(_html`<p>${null}${undefined}</p>`),
    numero: String(_html`<p>${42}</p>`),
    grezzo: String(_html`<p>${_grezzo('<b>voluto</b>')}</p>`),
    annidato: String(_html`<ul>${['a<b', 'c&d'].map((v) => _html`<li>${v}</li>`)}</ul>`),
    argomenti: String(_html`<b data-args="${_args("un'apice \" e virgolette")}"></b>`),
};
console.log(JSON.stringify(casi));
"""

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert visto["tag"] == "<p>&lt;b&gt;ciao&lt;/b&gt;</p>"
    # Non che la parola «onfocus» sparisca — resta, ed e' giusto che resti:
    # e' testo dentro il valore. Che non ci sia piu' una virgoletta **nuda**
    # capace di chiudere l'attributo e aprirne un altro. Nel risultato le
    # sole virgolette vere sono le due che delimitano il valore.
    assert visto["virgolette"].count('"') == 2, f"attributo iniettato: {visto['virgolette']}"
    assert "&quot;" in visto["virgolette"], "le virgolette del valore non sono state ripulite"
    assert visto["apici"].count("'") == 2, f"attributo iniettato: {visto['apici']}"
    assert "&#39;" in visto["apici"], "gli apici del valore non sono stati ripuliti"
    assert "`" not in visto["backtick"], f"il backtick passa: {visto['backtick']}"
    assert visto["vuoto"] == "<p></p>", f"null e undefined finiscono scritti: {visto['vuoto']}"
    assert visto["numero"] == "<p>42</p>"
    assert visto["grezzo"] == "<p><b>voluto</b></p>", "`_grezzo` non lascia passare il markup voluto"
    assert visto["annidato"] == "<ul><li>a&lt;b</li><li>c&amp;d</li></ul>", (
        "un `_html` dentro un altro va ripulito due volte, o non ci entra affatto: " f"{visto['annidato']}"
    )
    valore = visto["argomenti"].split('data-args="')[1].rsplit('"', 1)[0]
    assert "'" not in valore and '"' not in valore, f"l'attributo dei dati si apre da solo: {valore}"


def _argomento_di(sorgente: str, apertura: int) -> str:
    """Cio' che sta fra le parentesi, contando quelle annidate."""
    i = sorgente.index("(", apertura) + 1
    profondita, inizio = 1, i
    while i < len(sorgente) and profondita:
        if sorgente[i] == "(":
            profondita += 1
        elif sorgente[i] == ")":
            profondita -= 1
        i += 1
    return sorgente[inizio : i - 1].strip()


def test_grezzo_si_usa_solo_su_markup_scritto_da_noi():
    """`_grezzo` e' la scappatoia del meccanismo, e va sorvegliata.

    Tutto l'impianto di `_html` regge su una cosa sola: che `_grezzo` sia
    raro e si usi solo su markup che abbiamo scritto noi. Metterci dentro
    un valore che arriva dal server — `_grezzo(r.nome)` — spegne le fughe
    in quel punto e basta, senza rumore: nessuna delle altre guardie se ne
    accorge, e la riga accanto sembra identica a una giusta.

    L'ho scoperto provando a rovinare una riga cosi': l'unica mutazione,
    su otto, che non mordeva.

    Quindi l'argomento deve essere una stringa scritta li': apici e
    nient'altro.

    Riferimento: issue #34.
    """
    colpevoli = []
    for percorso in _copioni():
        if percorso.name in NON_ANCORA_CONVERTITI or percorso.name == "sicurezza.js":
            continue
        testo = _testo(percorso)
        for m in re.finditer(r"\b_grezzo\s*\(", testo):
            argomento = _argomento_di(testo, m.start())
            letterale = re.fullmatch(r"(?s)(['\"]).*\1,?", argomento)
            if not letterale:
                riga = testo.count("\n", 0, m.start()) + 1
                colpevoli.append(f"{percorso.name}:{riga} -> _grezzo({argomento[:60]})")

    assert not colpevoli, (
        "`_grezzo` con dentro qualcosa che non e' markup scritto a mano:\n"
        + "\n".join(colpevoli)
        + "\nSe il valore viene dal server, toglilo: `_html` lo ripulisce da solo."
    )


def test_premere_la_x_di_un_nodo_non_lo_trascina():
    """Il pulsante che sembrava morto.

    L'editor a nodi ha una crocetta per togliere un blocco. Premendola
    partiva invece il trascinamento del nodo, perche' la guardia di
    `startDragNode` chiedeva `e.target.tagName === 'BUTTON'` — e il
    bersaglio di un clic sull'icona di un pulsante non e' il pulsante: e'
    l'icona. Lucide sostituisce ogni `<i data-lucide>` con un `<svg>`,
    quindi il confronto era sempre falso.

    Con un mouse fermo il clic arrivava lo stesso e non se ne accorgeva
    nessuno. Con un trackpad o un dito il gesto si legge come uno
    spostamento e il clic non arriva: il pulsante non fa niente, e non
    dice perche'.

    La guardia **esegue** `startDragNode` con bersagli veri — l'`<svg>`
    dell'icona, la `<path>` dentro l'`<svg>`, il campo di testo, e
    l'intestazione nuda — invece di cercare `closest` nel sorgente: una
    riga cosi' sopravvive intatta dentro un `if (false)`.

    Riferimento: issue #34, segnalato dalla casa.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = (
        """
// Si **riempie** la tela vera invece di sostituirla: cosi' se un giorno
// `Stato.tela` nascesse `null`, qui esplode subito invece di passare.
Stato.tela.nodes = [{ id: 'n1', x: 10, y: 10 }];
Stato.tela.isDraggingNode = null;
Stato.tela.dragOffset = null;
function finto(tag, dentro) {
    const nodo = {
        tagName: tag.toUpperCase(),
        _dentro: dentro,
        closest(selettore) {
            const nomi = selettore.split(',').map((s) => s.trim().toUpperCase());
            if (nomi.includes(this.tagName)) return this;
            return this._dentro ? this._dentro.closest(selettore) : null;
        },
    };
    return nodo;
}
const document = { getElementById: () => ({ getBoundingClientRect: () => ({ left: 0, top: 0 }) }) };
"""
        # L'elenco dei comandi viene dal file, non riscritto qui: se qualcuno
        # ne toglie uno, questa guardia deve accorgersene invece di provare
        # una copia sua rimasta giusta.
        + _riga_javascript(_testo(CARTELLA_JS / "tela_nodi.js"), "const COMANDI_DENTRO_AL_NODO")
        + "\n"
        + _funzione_javascript(_testo(CARTELLA_JS / "tela_nodi.js"), "startDragNode")
        + """
const bottone = finto('button', null);
const casi = {
    // Quello che succede davvero: lucide ha messo un <svg> dentro il pulsante.
    svgDentroIlPulsante: finto('svg', bottone),
    // Un clic un pixel piu' in la': la <path> dentro l'<svg>.
    pathDentroIlPulsante: finto('path', finto('svg', bottone)),
    // Il pulsante nudo, che gia' funzionava.
    pulsante: finto('button', null),
    // I campi del nodo: scrivere non deve spostare il nodo.
    campoDiTesto: finto('input', null),
    menuATendina: finto('select', null),
    // L'intestazione: prenderla per spostare il nodo deve funzionare.
    intestazione: finto('div', null),
};
const esito = {};
for (const [nome, bersaglio] of Object.entries(casi)) {
    Stato.tela.isDraggingNode = null;
    startDragNode('n1', { target: bersaglio, clientX: 100, clientY: 100 });
    esito[nome] = Stato.tela.isDraggingNode !== null;
}
console.log(JSON.stringify(esito));
"""
    )

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr
    trascina = json.loads(esito.stdout.strip())

    for nome in ("svgDentroIlPulsante", "pathDentroIlPulsante", "pulsante", "campoDiTesto", "menuATendina"):
        assert not trascina[nome], f"premendo {nome} parte il trascinamento del nodo: il comando non risponde"

    # E l'intestazione deve restare la maniglia: una guardia che spegne
    # tutto sarebbe verde e avrebbe rotto lo spostamento dei nodi.
    assert trascina["intestazione"], "il nodo non si puo' piu' spostare prendendolo per l'intestazione"


def test_la_crocetta_che_stacca_un_cavo_si_puo_premere():
    """Il difetto che ha visto la casa: i cavi non si staccavano.

    La tela ha due piani sovrapposti. Sotto i cavi, disegnati in SVG:
    il piano non prende i clic (`pointer-events-none`), tranne le
    crocette che staccano un cavo, che li prendono. Sopra, il piano dei
    nodi, che copre **tutta** la tela con `inset-0`.

    Se quel piano prende gli eventi del mouse li prende dappertutto,
    anche dove non c'e' nessun nodo — e li' sotto c'e' la crocetta.
    Il clic si fermava sul telaio e non arrivava mai al cavo. Misurato
    con un browser vero: `elementFromPoint` sul centro della crocetta
    restituiva il `div` del telaio, e `deleteCanvasEdge` non veniva
    chiamata nemmeno una volta.

    Il telaio ora fa il telaio: a ricevere i clic sono i nodi.

    **Cosa non vede questa guardia.** Legge le classi, non lo schermo.
    Un elemento puo' coprirne un altro in mille modi che qui non si
    vedono: uno `z-index` cambiato, un margine, un `transform`. Il
    difetto e' stato trovato in un browser e li' andrebbe difeso — vedi
    l'issue sui gesti dell'interfaccia. Questa tiene la porta che si e'
    aperta oggi.

    Riferimento: segnalato dalla casa durante la #34.
    """
    tela = _senza_commenti_html(_testo(CARTELLA_JS / "tela.js"))
    nodi = _senza_commenti_html(_testo(CARTELLA_JS / "tela_disegno.js"))

    telaio = re.search(r'id="flow-nodes-container" class="([^"]+)"', tela)
    assert telaio, "il piano dei nodi non c'e' piu'"
    classi = telaio.group(1).split()
    assert "inset-0" in classi, "il piano dei nodi non copre piu' tutta la tela: rileggi questa guardia"
    assert "pointer-events-none" in classi, (
        "il piano dei nodi prende i clic su tutta la tela, crocette dei cavi comprese: "
        f"classi = {telaio.group(1)}"
    )

    nodo = re.search(r'id="c-node-\$\{node\.id\}" class="([^"]+)"', nodi)
    assert nodo, "il nodo non c'e' piu'"
    assert "pointer-events-auto" in nodo.group(1).split(), (
        "col telaio trasparente, un nodo che non riprende gli eventi non risponde piu' a niente: "
        f"classi = {nodo.group(1)}"
    )

    piano_cavi = re.search(r'id="flow-svg-layer" class="([^"]+)"', tela)
    assert piano_cavi and "pointer-events-none" in piano_cavi.group(
        1
    ), "il piano dei cavi prende i clic: i cavi passano sopra i nodi e li coprirebbero"

    crocetta = re.search(
        r"<circle[^>]*data-gesto=\"deleteCanvasEdge\"",
        _senza_commenti_html(_testo(CARTELLA_JS / "tela_nodi.js")),
    )
    assert crocetta, "la crocetta che stacca un cavo non c'e' piu'"
    assert "pointer-events-auto" in crocetta.group(
        0
    ), "la crocetta non riprende gli eventi: il piano dei cavi non ne fa passare nessuno"
