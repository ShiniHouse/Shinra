"""La struttura: la pagina scomposta in moduli, lo stato in un posto solo, i gesti, e la versione negli indirizzi.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from aiuti_frontend import (
    ACCESSO,
    CARTELLA_JS,
    CONTENITORE,
    INGRESSO,
    PAGINA,
    RADICE,
    _comportamento,
    _copioni,
    _esegui_con_node,
    _fogli,
    _frontend,
    _funzione_javascript,
    _markup,
    _parti,
    _script_inline,
    _senza_commenti,
    _senza_commenti_html,
    _stile,
    _testo,
    _testo_grezzo,
)

# ------------------------------------------ la pagina scomposta (issue #34)


def test_la_pagina_non_porta_piu_dentro_il_copione_e_il_foglio():
    """Settemilaquattrocento righe in un file solo.

    Markup, CSS e JavaScript insieme vogliono dire che l'ambito di qualunque
    cosa e' tutto, e che ogni modifica all'interfaccia costa piu' del dovuto.
    E' il freno principale alle altre schede rimaste.

    Resta in linea un solo copione, e deve restarci: decide il tema
    **prima** che la pagina si disegni. Un file esterno arriverebbe troppo
    tardi, ed e' esattamente il difetto della #152: il tema stava in un file,
    veniva deciso su `load`, e per mezzo secondo la pagina era scura anche a
    mezzogiorno.

    Il numero e' fissato apposta. Ogni copione in linea in piu' e' codice che
    nessun linter guarda e nessun file raccoglie: se ne serve un secondo, lo si
    aggiunge qui con la sua ragione scritta, invece di lasciarlo crescere.
    """
    pagina = _testo(PAGINA)

    assert "<style>" not in _markup(), "il foglio di stile e' tornato dentro la pagina"

    inline = _script_inline(pagina)
    assert len(inline) == 1, (
        f"i copioni in linea sono {len(inline)}: deve restare solo quello del "
        "`<head>`, che gira prima del disegno"
    )
    for blocco in inline:
        assert len(blocco) < 2000, "un copione in linea e' cresciuto: va in un file suo"

    # I pezzi inclusi sono markup e basta: un copione in linea li' dentro non
    # sta nel `<head>`, quindi non ha la ragione che giustifica quello del tema,
    # e nessun linter lo guarderebbe.
    intrusi = {p.name: len(_script_inline(_testo(p))) for p in _parti() if _script_inline(_testo(p))}
    assert not intrusi, f"copioni in linea dentro i pezzi del markup: {intrusi}"

    assert len(pagina.splitlines()) < 250, (
        f"index.html e' {len(pagina.splitlines())} righe: dalla #34 tiene solo "
        "il `<head>`, l'ossatura e i collegamenti — una scheda nuova e' un "
        "pezzo in `parti/`, non altre righe qui"
    )


def test_i_fogli_e_i_copioni_esistono_e_non_sono_vuoti():
    """Una guardia che controllasse solo l'assenza dalla pagina sarebbe verde
    anche il giorno che qualcuno cancella i file invece di collegarli."""
    fogli, copioni = _fogli(), _copioni()

    assert len(fogli) >= 4, f"fogli di stile trovati: {[p.name for p in fogli]}"
    assert len(copioni) >= 15, f"copioni trovati: {[p.name for p in copioni]}"

    for percorso in [*fogli, *copioni]:
        if percorso.name == "tailwind.css":
            # Generato e compresso su una riga (`npm run css`): lo guarda `npm run css:verifica`.
            assert len(_testo(percorso)) > 10000, "tailwind.css e' quasi vuoto: rigeneralo con `npm run css`"
            continue
        righe = len(_testo(percorso).splitlines())
        assert righe > 30, f"{percorso.name} ha {righe} righe: o e' vuoto, o non doveva nascere"

    assert len(_stile().splitlines()) > 700, "il foglio di stile complessivo si e' svuotato"
    assert len(_comportamento().splitlines()) > 5000, "il copione complessivo si e' svuotato"


def test_nessun_pezzo_del_frontend_supera_le_cinquecento_righe():
    """Il criterio di accettazione della #34, scritto come guardia.

    Il numero non e' magico: e' la soglia oltre la quale un file smette di
    entrare in testa tutto insieme, e si torna a modificarlo cercando col
    trova invece di leggerlo. La pagina unica ne aveva 7.438.

    Fino a poco fa qui c'era un'eccezione — `lunghi.pop("index.html")` — con
    scritto accanto che il markup andava spezzato in template inclusi. Adesso
    e' spezzato, e l'eccezione e' sparita: nessun file del frontend e' piu'
    fuori dal criterio.

    Riferimento: issue #34.
    """
    lunghi = {}
    for percorso in [PAGINA, ACCESSO, *_parti(), *_fogli(), *_copioni()]:
        righe = len(_testo(percorso).splitlines())
        if righe > 500:
            lunghi[percorso.name] = righe

    assert not lunghi, f"file oltre le cinquecento righe: {lunghi}"


def _inclusi() -> list[str]:
    """I pezzi che `index.html` include, nell'ordine in cui stanno."""
    return re.findall(r'{%\s*include\s+"parti/([^"]+)"\s*%}', _senza_commenti_html(_testo(PAGINA)))


def test_la_pagina_include_tutti_i_pezzi_e_nessun_altro():
    """Il gemello della guardia sui collegamenti, per il markup.

    Un pezzo scritto e mai incluso e' una scheda che non esiste, e non da'
    nessun errore: il file c'e', la pagina si compone lo stesso, e manca una
    parte di dashboard. Un nome sbagliato nell'altro verso fa l'opposto —
    `TemplateNotFound` a ogni apertura — ed e' il caso fortunato.

    Riferimento: issue #34.
    """
    inclusi = _inclusi()
    sul_disco = [p.name for p in _parti()]

    assert sorted(inclusi) == sorted(sul_disco), (
        f"esistono ma la pagina non li include: {sorted(set(sul_disco) - set(inclusi))}\n"
        f"inclusi ma non esistono: {sorted(set(inclusi) - set(sul_disco))}"
    )
    assert len(inclusi) == len(set(inclusi)), f"un pezzo e' incluso due volte: {inclusi}"


def test_ogni_scheda_sta_in_un_pezzo_suo():
    """Una scheda per pezzo, e nessuna rimasta dentro `index.html`.

    E' il senso della scomposizione: aprire il file giusto senza cercare. Un
    pezzo che ne contenesse due sarebbe un file spezzato senza il vantaggio
    dello spezzarlo, e una scheda rimasta nell'ossatura sarebbe la prima riga
    di un ritorno al file unico — che di righe ne aveva 7.438.
    """

    def schede(testo: str) -> list[str]:
        return re.findall(r'id="tab-([a-z]+)"[^>]*class="[^"]*\btab-content\b', testo)

    nell_ossatura = schede(_testo(PAGINA))
    assert not nell_ossatura, f"schede rimaste dentro index.html: {nell_ossatura}"

    doppie = {p.name: s for p in _parti() if len(s := schede(_testo(p))) > 1}
    assert not doppie, f"pezzi che portano piu' di una scheda: {doppie}"

    tutte = [s for p in _parti() for s in schede(_testo(p))]
    assert len(tutte) >= 6, f"schede trovate nei pezzi: {tutte}"


def _collegamenti(pagina: str) -> list[str]:
    """Gli indirizzi statici che la pagina collega, nell'ordine in cui stanno."""
    return re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"?]+)', _senza_commenti_html(pagina))


def test_la_pagina_collega_tutti_i_pezzi_e_nessun_altro():
    """Un foglio nuovo che nessuno collega e' codice morto; un pezzo tolto e
    lasciato collegato e' un 404 a ogni apertura.

    I fogli di stile stanno tutti nella pagina. Il JavaScript, dalla #34, ci
    sta con **un solo** collegamento — il punto d'ingresso dei moduli — e le
    aree si raggiungono per `import` (vedi `test_ogni_modulo_e_raggiungibile`).

    Riferimento: issue #34.
    """
    collegati = _collegamenti(_testo(PAGINA))
    sul_disco = [f"/static/css/{p.name}" for p in _fogli()] + [f"/static/js/{INGRESSO}"]

    assert sorted(collegati) == sorted(sul_disco), (
        f"scollegati (esistono ma la pagina non li carica): {sorted(set(sul_disco) - set(collegati))}\n"
        f"fantasmi (collegati ma non esistono): {sorted(set(collegati) - set(sul_disco))}"
    )
    assert re.search(
        rf'<script type="module" src="/static/js/{re.escape(INGRESSO)}\?v=',
        _senza_commenti_html(_testo(PAGINA)),
    ), "il punto d'ingresso non e' caricato come modulo: senza type=\"module\" gli `import` sono errori di sintassi"


def _importazioni(percorso: Path) -> list[tuple[list[str], str]]:
    """Gli `import` di un modulo: i nomi chiesti e il file da cui arrivano."""
    trovati = []
    for m in re.finditer(r"^import\s+(?:\{([^}]*)\}\s+from\s+)?'\./([^']+)';", _testo_grezzo(percorso), re.M):
        nomi = [n.strip() for n in (m.group(1) or "").split(",") if n.strip()]
        trovati.append((nomi, m.group(2)))
    return trovati


def test_il_punto_d_ingresso_importa_ogni_area_una_volta_sola():
    """L'ordine degli `import` in `principale.js` non e' piu' l'ordine di
    caricamento dei copioni: le dipendenze stanno negli `import` di ciascun
    file. Resta da garantire che nessuna area sia dimenticata — un'area non
    importata da nessuno non gira, e non da' nessun errore — e che nessuna sia
    messa due volte.
    """
    importate = [sorgente for _, sorgente in _importazioni(CARTELLA_JS / INGRESSO)]

    assert sorted(importate) == sorted(p.name for p in _copioni()), (
        f"aree non importate: {sorted({p.name for p in _copioni()} - set(importate))}; "
        f"importate ma inesistenti: {sorted(set(importate) - {p.name for p in _copioni()})}"
    )
    assert len(importate) == len(set(importate)), f"un'area e' importata due volte: {importate}"
    assert not any(nomi for nomi, _ in _importazioni(CARTELLA_JS / INGRESSO)), (
        "il punto d'ingresso importa dei nomi: dovrebbe importare solo per gli effetti, " "senza codice suo"
    )


def test_ogni_modulo_e_raggiungibile_e_ogni_nome_importato_esiste():
    """La guardia che `type="module"` rende necessaria.

    Un copione classico che nomina una funzione inesistente fallisce quando la
    chiama. Un modulo che importa un nome che l'altro **non esporta** non si
    carica affatto: il browser rifiuta l'intero grafo, e la dashboard resta
    come l'ha lasciata il server — con lo stile e senza nessun comportamento.
    ESLint non lo vede, perche' guarda un file per volta.
    """
    esportati = {}
    for p in _copioni():
        esportati[p.name] = set(
            re.findall(
                r"^export\s+(?:async\s+)?(?:function\*?|const|let|var|class)\s+([A-Za-z_$][\w$]*)",
                _testo_grezzo(p),
                re.M,
            )
        )

    mancanti = []
    for p in _copioni():
        for nomi, sorgente in _importazioni(p):
            assert sorgente in esportati, f"{p.name} importa da {sorgente}, che non esiste"
            for nome in nomi:
                if nome not in esportati[sorgente]:
                    mancanti.append(f"{p.name} importa «{nome}» da {sorgente}, che non lo esporta")
    assert mancanti == [], mancanti

    # E ogni area si raggiunge dall'ingresso, direttamente o per altre aree.
    raggiunte = {sorgente for _, sorgente in _importazioni(CARTELLA_JS / INGRESSO)}
    assert raggiunte == {p.name for p in _copioni()}, "aree che l'ingresso non raggiunge"

    # Un'esportazione che nessuno importa e' un nome che qualcuno ha reso
    # pubblico senza un lettore: o serve a una registrazione di gesti (e
    # allora non occorre `export`), o e' codice morto.
    importati = {(sorgente, nome) for p in _copioni() for nomi, sorgente in _importazioni(p) for nome in nomi}
    inutili = sorted(f"{f}:{n}" for f, nomi in esportati.items() for n in nomi if (f, n) not in importati)
    assert inutili == [], f"esportato e mai importato: {inutili}"


def test_la_pagina_li_collega_con_la_versione_attaccata():
    """Il browser tiene i file statici finche' non cambia l'indirizzo.

    Con il copione dentro la pagina il problema non c'era: la pagina si
    rivalida a ogni apertura. Portandolo fuori si e' aperta una superficie di
    cache nuova, e una dashboard che gira su JavaScript vecchio dopo un
    aggiornamento e' esattamente il genere di guasto che fa perdere un
    pomeriggio — e' gia' successo con la pagina intera.

    La versione cambia a ogni commit: attaccarla all'indirizzo basta per i
    fogli e per il punto d'ingresso. Per i moduli che quello importa non
    basta — un `import` non porta la versione — e ci pensa il server
    (vedi `test_il_server_fa_rivalidare_i_moduli`).
    """
    pagina = _testo(PAGINA)
    indirizzi = _collegamenti(pagina)
    assert len(indirizzi) >= 6, f"collegamenti trovati: {indirizzi}"

    for indirizzo in indirizzi:
        collegamento = re.search(rf'{re.escape(indirizzo)}\?v=([^"]+)"', pagina)
        assert collegamento, f"{indirizzo} e' collegato senza la versione attaccata"
        assert "versione" in collegamento.group(1), (
            f"{indirizzo} porta una versione fissa invece di quella vera: " f"{collegamento.group(1)}"
        )


def test_la_pagina_servita_porta_dentro_ogni_pezzo(cliente_autenticato):
    """Le guardie di sopra leggono il disco. Questa guarda cosa arriva.

    E' l'unica che prova davvero che `{% include %}` funziona: che la
    cartella sia quella che Jinja cerca, che i nomi combacino, e che la
    pagina composta contenga tutto il markup che prima era scritto dentro.

    Di ogni pezzo si cerca la prima riga vera — tolti i commenti, che nella
    pagina ci sarebbero comunque anche se l'include fallisse a meta'.

    Riferimento: issue #34.
    """
    servita = cliente_autenticato.get("/")
    assert servita.status_code == 200, f"la dashboard risponde {servita.status_code}"

    mancanti = []
    for pezzo in _parti():
        vere = [r.strip() for r in _senza_commenti_html(_testo(pezzo)).splitlines() if r.strip()]
        assert vere, f"{pezzo.name} non ha nemmeno una riga di markup"
        if vere[0] not in servita.text:
            mancanti.append(f"{pezzo.name}: manca «{vere[0][:60]}»")

    assert not mancanti, f"pezzi che non arrivano nella pagina servita: {mancanti}"

    # E la pagina composta deve pesare quanto la somma dei pezzi: un include
    # che portasse dentro solo la prima riga passerebbe il controllo di sopra.
    atteso = sum(len(_testo(p).splitlines()) for p in _parti())
    arrivate = len(servita.text.splitlines())
    assert arrivate > atteso, f"la pagina servita ha {arrivate} righe, i soli pezzi ne fanno {atteso}"


def test_il_server_serve_davvero_il_foglio_e_il_copione(cliente_autenticato):
    """Le guardie di sopra leggono il disco. Questa chiede al server.

    Un `<link>` o uno `<script src>` verso un indirizzo che risponde 404
    lascia la dashboard senza stile e senza comportamento, e la pagina
    continua a rispondere 200: nessuna guardia che legge i file se ne
    accorgerebbe. E' lo stesso genere di silenzio per cui esiste
    `test_ogni_chiamata_api_della_pagina_corrisponde_a_una_rotta`.
    """
    pagina = cliente_autenticato.get("/")
    assert pagina.status_code == 200

    indirizzi = re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"]+)"', pagina.text)
    attesi = len(_fogli()) + 1  # i fogli, e il punto d'ingresso dei moduli
    assert len(indirizzi) == attesi, f"collegamenti trovati: {len(indirizzi)}, attesi: {attesi}"

    for indirizzo in indirizzi:
        risposta = cliente_autenticato.get(indirizzo)
        assert risposta.status_code == 200, f"{indirizzo} risponde {risposta.status_code}"
        assert len(risposta.content) > 500, f"{indirizzo} e' quasi vuoto"

        # E la versione attaccata deve essere quella vera: se il template non
        # venisse riempito, l'indirizzo non cambierebbe mai e il browser
        # terrebbe il file vecchio per sempre.
        versione = indirizzo.split("?v=")[-1]
        assert "{{" not in versione and versione not in (
            "",
            "dev",
        ), f"la versione non e' stata riempita: {versione}"

    # Le aree non sono nella pagina: le raggiunge l'ingresso per `import`.
    # Se una risponde 404, il browser rifiuta tutto il grafo dei moduli.
    for p in [*_copioni(), CARTELLA_JS / INGRESSO]:
        risposta = cliente_autenticato.get(f"/static/js/{p.name}")
        assert risposta.status_code == 200, f"/static/js/{p.name} risponde {risposta.status_code}"


def test_il_server_fa_rivalidare_i_moduli(cliente_autenticato):
    """Un `import` non porta il numero di versione.

    `principale.js?v=...` cambia a ogni rilascio, ma `./stato.js` dentro di
    lui resta lo stesso indirizzo. Senza `Cache-Control: no-cache` un browser
    puo' tenere un modulo vecchio per ore (la cache euristica e' una frazione
    dell'eta' del file) e dopo un aggiornamento la pagina girerebbe con
    un'area nuova e una vecchia insieme. `no-cache` non vuol dire non
    tenerlo: vuol dire chiedere prima; con l'ETag la risposta a un file
    invariato e' un 304 senza corpo.
    """
    risposta = cliente_autenticato.get("/static/js/stato.js")
    assert risposta.status_code == 200
    assert risposta.headers.get("cache-control") == "no-cache", (
        "i moduli vengono serviti senza l'ordine di rivalidare: "
        f"cache-control = {risposta.headers.get('cache-control')}"
    )

    etag = risposta.headers.get("etag")
    assert etag, "senza ETag ogni rivalidazione riscarica il file intero"
    invariato = cliente_autenticato.get("/static/js/stato.js", headers={"If-None-Match": etag})
    assert invariato.status_code == 304, f"un file invariato risponde {invariato.status_code}, non 304"


def test_avviare_un_timer_a_mano_non_muore_su_un_nome_che_non_esiste():
    """Il pulsante «+ Timer» chiamava una variabile che non e' mai esistita.

    `saveNewTimerManual` metteva nel corpo della richiesta `_currentUserId`:
    un nome che nessun file dichiara. In JavaScript non e' un errore di
    sintassi, e' un `ReferenceError` che scatta **quando si preme il
    pulsante** — la funzione muore prima della `fetch`, la finestra resta
    aperta, il timer non nasce e sullo schermo non succede niente. Nessuna
    delle guardie che leggono il sorgente poteva vederlo, e infatti non
    l'hanno visto: l'ha trovato ESLint il giorno che e' entrato in CI.

    Questa guardia **esegue** la funzione con una finta pagina e una finta
    `fetch`, e guarda cosa parte davvero.

    Riferimento: issue #34.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = (
        """
let activeUserId = 'alessio';
let partita = null;
const campi = { 'new-timer-label': { value: '  Pasta  ' }, 'new-timer-min': { value: '9' } };
const document = { getElementById: (id) => campi[id] || null };
function getAuthHeaders() { return {}; }
function closeModal() {}
function loadTimers() {}
async function fetch(indirizzo, opzioni) {
    partita = { indirizzo, corpo: JSON.parse(opzioni.body) };
    return { ok: true };
}
"""
        + _funzione_javascript(_comportamento(), "saveNewTimerManual")
        + """
saveNewTimerManual()
    .then(() => console.log(JSON.stringify(partita)))
    .catch((e) => { console.log(JSON.stringify({ errore: String(e) })); });
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert "errore" not in visto, f"il pulsante muore prima di chiamare il server: {visto['errore']}"
    assert visto["indirizzo"] == "/api/timers"
    assert visto["corpo"]["user_id"] == "alessio", (
        "il timer parte senza dire di chi e': finisce sul profilo predefinito "
        "invece che su chi l'ha chiesto"
    )
    assert visto["corpo"]["label"] == "Pasta"
    assert visto["corpo"]["duration_seconds"] == 9 * 60


# ----------------------------- lo stato in un posto solo (issue #34)


def _dichiarazioni_mutabili(percorso: Path) -> set[str]:
    """I `let` e i `var` a colonna zero: quelli che finiscono in globale.

    Le costanti restano fuori apposta. Una `const` condivisa non e' stato —
    e' un valore che tutti leggono e nessuno cambia, e spostarla in un
    contenitore di stato direbbe una cosa falsa su cosa sia.
    """
    return set(re.findall(r"^(?:let|var)\s+([A-Za-z_$][\w$]*)", _senza_commenti(_testo(percorso)), re.M))


def test_lo_stato_condiviso_sta_nel_contenitore():
    """La regola della #34, scritta come guardia.

    Fino a poco fa ogni area teneva il suo stato in un `let` a colonna zero.
    Finche' quella variabile la leggeva solo il suo file andava bene. Undici
    non erano cosi': le scriveva un'area e le leggeva un'altra —
    `activeUserId` girava per cinque file — e guardando un file solo non
    c'era modo di sapere quali fossero. Lo spazio globale era il contenitore,
    cioe' nessun contenitore.

    Adesso quelle stanno in `Stato`. Questa guardia impedisce che ne nasca
    una dodicesima di nascosto: se un `let` dichiarato in un file viene letto
    da un altro, o entra nel contenitore o resta dove sta.

    Riferimento: issue #34.
    """
    copioni = [p for p in _copioni() if p.name != CONTENITORE]
    assert len(copioni) > 15, f"copioni trovati: {[p.name for p in copioni]}"

    # Il codice senza commenti: un nome citato nella spiegazione di un'altra
    # area non e' un uso, ed e' esattamente il modo in cui una guardia di
    # questo file e' gia' stata resa cieca quattro volte.
    corpi = {p.name: _senza_commenti(_testo(p)) for p in copioni}

    sparsi = []
    for percorso in copioni:
        for nome in _dichiarazioni_mutabili(percorso):
            altri = [
                altro
                for altro, corpo in corpi.items()
                if altro != percorso.name and re.search(rf"\b{re.escape(nome)}\b", corpo)
            ]
            if altri:
                sparsi.append(f"{percorso.name} dichiara `{nome}`, che leggono anche {altri}")

    assert sparsi == [], (
        "questo stato attraversa le aree e non sta in `Stato`: o entra nel "
        f"contenitore, o resta dentro la sua area — {sparsi}"
    )


def _campi_dello_stato() -> set[str]:
    """I campi dichiarati in `Stato`, presi dal contenitore.

    Sono le chiavi al primo livello di rientro dentro `const Stato = {`:
    quattro spazi, un nome, due punti. Un campo annidato — `tela.nodes` — non
    e' un campo dello stato, e' un dettaglio di quel campo.
    """
    sorgente = _senza_commenti(_testo(CARTELLA_JS / CONTENITORE))
    corpo = sorgente[sorgente.index("const Stato = {") :]
    return set(re.findall(r"^    ([A-Za-z_$][\w$]*):", corpo, re.M))


def test_ogni_campo_dello_stato_esiste_davvero():
    """Il contenitore toglie una protezione: questa la rimette.

    Con le variabili sciolte, `activeUserIdd` era un nome che nessuno
    dichiarava e `no-undef` fermava ESLint. `Stato.utenteAttivoo` invece e'
    una proprieta' come un'altra: vale `undefined`, non solleva niente, e il
    difetto si vede in casa come una funzione che «non fa niente» — che e'
    il guasto piu' caro da cercare, perche' non lascia tracce.

    ESLint non puo' saperlo. Questa guardia si': i campi li legge dal
    contenitore, gli usi da tutto il frontend.

    Riferimento: issue #34.
    """
    campi = _campi_dello_stato()
    assert len(campi) >= 10, f"campi trovati in Stato: {sorted(campi)}"

    usati = set(re.findall(r"\bStato\.([A-Za-z_$][\w$]*)", _senza_commenti(_frontend())))
    assert usati, "nessun uso di `Stato` nel frontend: la guardia non guarda piu' niente"

    inventati = sorted(usati - campi)
    assert inventati == [], (
        f"queste proprieta' di `Stato` non esistono nel contenitore: {inventati}. "
        "Valgono `undefined` senza dire niente — aggiungile a `stato.js` o "
        "correggi il nome."
    )

    # E l'altro verso: un campo che non usa piu' nessuno e' stato che la
    # dashboard si porta dietro senza motivo.
    mai_usati = sorted(campi - usati)
    assert mai_usati == [], f"campi dichiarati in `Stato` e usati da nessuno: {mai_usati}"


def test_i_gesti_parlano_allo_stato_vero():
    """Il banco dei gesti legge `Stato.tela` dentro un `page.evaluate()`.

    E' codice che gira nel browser vero, quindi un nome sbagliato li' dentro
    non e' un errore di compilazione: e' un test che fallisce parlando di
    tutt'altro. Il nome sta scritto in due posti — qui e nel contenitore — e
    questa guardia li tiene insieme.
    """
    banchi = sorted((RADICE / "tests" / "gesti").glob("*.mjs"))
    assert banchi, "i banchi dei gesti sono spariti"

    campi = _campi_dello_stato()
    nominati = set()
    for banco in banchi:
        nominati |= set(re.findall(r"\bStato\.([A-Za-z_$][\w$]*)", _senza_commenti(_testo(banco))))

    assert nominati, "nessun banco dei gesti guarda piu' lo stato della dashboard"
    assert (
        sorted(nominati - campi) == []
    ), f"i gesti nominano campi che `Stato` non ha: {sorted(nominati - campi)}"


def test_zittire_shinra_sopravvive_alla_riapertura():
    """Lo stato che si ricorda fra un'apertura e l'altra ha due estremi.

    Chi zittisce Shinra lo fa una volta e si aspetta che resti cosi'. La
    scelta si scrive in `localStorage` da due punti — le impostazioni e lo
    sblocco — e si rilegge in `stato.js` quando la dashboard nasce. Sono tre
    posti che devono nominare **la stessa chiave**: se uno solo la sbaglia,
    la dashboard riparte parlando e nessun errore lo dice.

    Spostando la variabile in `Stato` (#34) la rilettura ha cambiato file, ed
    e' esattamente il momento in cui un capo dei due si perde. Una mutazione
    che la toglieva non faceva fallire niente: questa guardia e' quella
    mutazione, scritta.
    """
    contenitore = _senza_commenti(_testo(CARTELLA_JS / CONTENITORE))
    partenza = re.search(
        r"voceZittita:.*?localStorage\.getItem\(\s*'([^']+)'\s*\)\s*===\s*'true'",
        contenitore,
        re.S,
    )
    assert partenza, (
        "`Stato.voceZittita` non si rilegge piu' da `localStorage`: chi zittisce "
        "Shinra se la ritrova che parla alla riapertura"
    )
    chiave = partenza.group(1)

    scritture = set(re.findall(r"localStorage\.setItem\(\s*'([^']+)'\s*,\s*[^)]*[Mm]uted", _comportamento()))
    scritture |= set(
        re.findall(r"localStorage\.setItem\(\s*'([^']+)'\s*,\s*Stato\.voceZittita", _comportamento())
    )
    assert scritture, "nessuno scrive piu' la scelta: si perde a ogni chiusura"
    assert scritture == {chiave}, (
        f"chi rilegge cerca `{chiave}`, chi scrive usa {sorted(scritture)}: "
        "i due capi non si incontrano, e la scelta si perde in silenzio"
    )


# ------------------------------- i gesti al posto degli onclick (issue #34)

QUANDO = {
    "gesto": "click",
    "al-cambio": "change",
    "mentre-scrivi": "input",
    "all-invio": "submit",
    "al-premere": "mousedown",
    "al-rilascio": "mouseup",
}


# Gli argomenti che il guardiano sa preparare. Il vocabolario e' chiuso
# apposta: indovinarlo dall'elemento sembra comodo finche' non si incontra
# `openModularModeBuilder(existingId = null)`, che chiamata con un evento
# aprirebbe l'editor su una routine che si chiama `[object PointerEvent]`.
ARGOMENTI = {"valore", "spunta", "evento", "vero", "falso", "niente"}


def _gesti_nel_markup() -> dict[str, set[str]]:
    """Dal nome dell'attributo ai gesti che il markup chiede con quello."""
    # Il markup scritto nei file HTML, piu' quello che disegna il JavaScript:
    # dalla #34 sono due posti e lo stesso vocabolario.
    markup = _markup() + "\n" + _senza_commenti(_comportamento())
    return {q: set(re.findall(rf'data-{q}="([^"]+)"', markup)) for q in QUANDO}


def _gesti_registrati() -> set[str]:
    """I nomi che le aree passano a `Gesti.registra({...})`.

    Si leggono dal codice senza commenti: un nome citato in una spiegazione
    non e' una registrazione, ed e' il modo in cui una guardia di questo file
    e' gia' stata resa cieca quattro volte.
    """
    nomi = set()
    for blocco in re.findall(r"Gesti\.registra\(\{(.*?)\}\)", _senza_commenti(_comportamento()), re.S):
        nomi |= set(re.findall(r"^\s*([A-Za-z_$][\w$]*)\s*,", blocco, re.M))
    return nomi


def test_la_dashboard_non_esegue_piu_stringhe_dal_markup():
    """Il vero ostacolo ai moduli ES, tolto (#34, ADR 0006).

    Un attributo `onclick` e' una stringa che il browser esegue nello spazio
    globale. Il giorno che i copioni diventano moduli quello spazio resta
    vuoto, e ogni clic smette di fare qualcosa — tutti insieme, senza un
    errore. Per questo il lavoro della #34 non e' aggiungere `type="module"`:
    e' arrivare qui.

    `accesso.html` resta fuori e per nome: e' un'altra pagina, con un copione
    suo di poche righe e tre gesti, e caricarci `gesti.js` per quelli
    costerebbe piu' di quello che varrebbe.
    """
    colpevoli = []
    for pezzo in [PAGINA, *_parti()]:
        for attributo in re.findall(r"\son([a-z]+)=\"", _senza_commenti_html(_testo(pezzo))):
            colpevoli.append(f"{pezzo.name}: on{attributo}")
    # E quello che il JavaScript disegna: 72 `onclick` stavano nelle stringhe
    # dei copioni e non in un file di markup, e una guardia che guardava solo
    # i file HTML li lasciava passare.
    for percorso in _copioni():
        for attributo in re.findall(r"\son([a-z]+)=\"", _senza_commenti(_testo(percorso))):
            colpevoli.append(f"{percorso.name}: on{attributo}")

    assert colpevoli == [], (
        "la dashboard esegue di nuovo stringhe dal markup: il giorno dei "
        f"moduli questi clic non faranno piu' niente — {colpevoli}"
    )


def test_ogni_gesto_chiesto_dal_markup_e_registrato():
    """Un gesto scritto e mai registrato e' un pulsante che non fa niente.

    A differenza di un `onclick` con un refuso — che almeno lasciava un
    ReferenceError in console — qui il guardiano stampa il nome che non
    conosce, ma solo **se** qualcuno preme. Questa guardia lo dice prima.
    """
    chiesti = set().union(*_gesti_nel_markup().values())
    assert len(chiesti) > 30, f"gesti trovati nel markup: {sorted(chiesti)}"

    registrati = _gesti_registrati()
    assert len(registrati) > 30, f"gesti registrati: {sorted(registrati)}"

    assert (
        sorted(chiesti - registrati) == []
    ), f"il markup chiede gesti che nessuna area registra: {sorted(chiesti - registrati)}"


def test_ogni_gesto_registrato_e_una_funzione_che_esiste():
    """L'altro verso, che ESLint gia' controlla — ma solo se il nome sta in
    un file che lui guarda. Scriverlo qui costa una riga e vale il giorno che
    qualcuno rinomina una funzione e dimentica la registrazione."""
    dichiarate = set(
        re.findall(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", _comportamento(), re.M)
    )
    inesistenti = sorted(_gesti_registrati() - dichiarate)
    assert inesistenti == [], f"gesti registrati che non sono funzioni: {inesistenti}"


def test_nessun_gesto_registrato_resta_senza_chi_lo_chiami():
    """Una registrazione di troppo e' un nome che la pagina non usa piu'.

    Non fa danno, ma dice una cosa falsa: che quel pulsante esista. E il
    giorno dei moduli diventerebbe un `export` senza lettori.
    """
    chiesti = set().union(*_gesti_nel_markup().values())
    inutili = sorted(_gesti_registrati() - chiesti)
    assert inutili == [], f"questi gesti sono registrati e nessuno li chiede dal markup: {inutili}"


def test_ogni_argomento_dichiarato_e_uno_che_il_guardiano_sa_preparare():
    """`data-argomento` ha un vocabolario chiuso, e un nome fuori elenco non
    e' un errore di sintassi: e' una funzione chiamata senza argomenti, che
    fa qualcosa di leggermente sbagliato in silenzio."""
    strani = sorted(set(re.findall(r'data-argomento="([^"]+)"', _markup())) - ARGOMENTI)
    assert strani == [], f"argomenti che il guardiano non sa preparare: {strani}"

    # E nessun elemento deve dichiararne due: `data-testo` e `data-argomento`
    # insieme non si contraddicono a caso — vince `data-testo`, e l'altro
    # resta li' a dire una cosa che non succede.
    doppi = re.findall(
        r"<[^>]*data-testo=\"[^\"]*\"[^>]*data-argomento=|<[^>]*data-argomento=\"[^\"]*\"[^>]*data-testo=",
        _markup(),
    )
    assert doppi == [], f"elementi che dichiarano due argomenti: {len(doppi)}"


def test_il_guardiano_dei_gesti_ascolta_i_quattro_eventi():
    """Gli attributi nel markup e gli eventi ascoltati sono due elenchi che
    devono combaciare: un `data-mentre-scrivi` senza un ascolto su `input` e'
    un campo che non reagisce mentre ci si scrive, e non lo dice nessuno."""
    sorgente = _senza_commenti(_testo(CARTELLA_JS / "gesti.js"))
    mappa = re.search(r"EVENTI:\s*\{(.*?)\}", sorgente, re.S)
    assert mappa, "`gesti.js` non dichiara piu' quali eventi ascolta"

    dichiarati = dict(re.findall(r"(\w+):\s*'(\w+)'", mappa.group(1)))
    # Dal nome della proprieta' in JavaScript all'attributo nel markup:
    # `alCambio` -> `al-cambio`.
    attributi = {
        re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), v): k
        for v, k in ((v, k) for k, v in dichiarati.items())
    }
    assert attributi == QUANDO, f"gli eventi ascoltati sono {attributi}, i test si aspettano {QUANDO}"

    usati = {q for q, nomi in _gesti_nel_markup().items() if nomi}
    assert usati, "il markup non chiede piu' nessun gesto"
    assert usati <= set(QUANDO), f"il markup usa attributi che nessuno ascolta: {sorted(usati - set(QUANDO))}"


# ------------------------- i moduli hanno la versione negli indirizzi (import map)


def _mappa_della_pagina(html: str) -> dict[str, str]:
    trovata = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
    assert trovata, "la pagina non ha un import map: i moduli si importano senza versione"
    return json.loads(trovata.group(1))["imports"]


def test_la_pagina_servita_mappa_ogni_modulo_con_la_versione(cliente_autenticato):
    """Dietro Cloudflare l'intestazione `no-cache` arriva al browser come
    `max-age=14400`: quattro ore in cui `./stato.js` si legge dalla cache anche
    dopo un aggiornamento, e la dashboard gira mezza nuova e mezza vecchia.
    L'import map cambia l'indirizzo di ogni modulo a ogni versione, e nessuna
    cache in mezzo puo' piu' servire il file di prima.
    """
    pagina = cliente_autenticato.get("/")
    assert pagina.status_code == 200

    mappa = _mappa_della_pagina(pagina.text)
    moduli = sorted(p.name for p in _copioni())  # senza il punto d'ingresso

    assert sorted(m.rsplit("/", 1)[1] for m in mappa) == moduli, "l'import map non elenca tutti i moduli"
    for origine, destinazione in mappa.items():
        assert destinazione.startswith(origine + "?v="), f"{origine} -> {destinazione}"
        versione = destinazione.split("?v=", 1)[1]
        assert versione and "{{" not in versione and versione != "dev", f"versione non riempita: {versione!r}"
    assert len({d.split("?v=", 1)[1] for d in mappa.values()}) == 1, "moduli con versioni diverse"


def test_l_import_map_non_rimappa_il_punto_d_ingresso(cliente_autenticato):
    """L'ingresso ha gia' il suo `?v=` scritto dal template: rimapparlo lo
    farebbe caricare con due indirizzi diversi, cioe' due volte."""
    pagina = cliente_autenticato.get("/")

    assert f"/static/js/{INGRESSO}" not in _mappa_della_pagina(pagina.text)
    assert re.search(rf'<script type="module" src="/static/js/{INGRESSO}\?v=', pagina.text)


def test_l_import_map_viene_prima_dei_moduli(cliente_autenticato):
    """Un import map dopo il primo modulo e' ignorato dal browser, con un
    avviso in console e nessun errore: i moduli si caricherebbero senza
    versione e il difetto tornerebbe in silenzio."""
    pagina = cliente_autenticato.get("/").text

    assert pagina.index('type="importmap"') < pagina.index('type="module"')


def test_un_valore_ostile_non_chiude_il_blocco_dell_import_map(monkeypatch):
    from shinra.api import moduli_web

    moduli_web.mappa_dei_moduli.cache_clear()
    mappa = moduli_web.mappa_dei_moduli("0.5.0</script><img src=x onerror=alert(1)>")

    assert "</script>" not in mappa and "<img" not in mappa
    assert json.loads(mappa)["imports"], "l'escape ha rotto il JSON"
    moduli_web.mappa_dei_moduli.cache_clear()
