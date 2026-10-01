"""Le impostazioni a sezioni e il dispositivo come punto di ascolto.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
from aiuti_frontend import (
    _esegui_con_node,
    _frontend,
    _funzione_javascript,
    _gesto,
    _pezzo,
    _senza_commenti,
    _senza_commenti_html,
    _stile,
)

# ------------------------------------ questo dispositivo come punto di ascolto


def test_la_dashboard_si_dichiara_punto_di_ascolto():
    """La dashboard aperta in cucina **e'** un satellite: ha un microfono, sta
    in una stanza, e puo' dire quale. Non serve un Raspberry per avere
    «accendi la luce» che accende quella giusta — serve sapere da dove arriva
    la frase.

    Riferimento: issue #33.
    """
    testo = _frontend()

    assert "'/api/satelliti'" in testo, "il dispositivo non si annuncia mai"

    # La chiamata **all'avvio**, dentro il gestore del caricamento. Cercare
    # `annunciaQuestoDispositivo();` ovunque nel file la trovava dentro
    # `scegliStanza`, che la chiama quando si cambia stanza a mano: la
    # guardia restava verde con l'annuncio iniziale tolto, e un dispositivo
    # che si annuncia solo se qualcuno tocca la stanza non si annuncia mai.
    #
    # E' la quarta volta che scrivo questa guardia debole in tre giorni. La
    # forma giusta e' sempre la stessa: ancorarsi al blocco, non al nome.
    avvio = testo[testo.index("window.addEventListener('load'") :]
    assert "annunciaQuestoDispositivo();" in avvio, "l'annuncio non viene chiamato all'avvio"


def test_la_stanza_viaggia_con_ogni_messaggio():
    """Se si ferma per strada, tutto il resto e' inutile: il dominio sa
    scegliere e nessuno gli dice da dove si parla."""
    testo = _frontend()

    corpo = testo[testo.index("const res = await fetch('/api/chat'") :][:800]

    assert "satellite: satelliteDiQuestoDispositivo()" in corpo, "la stanza non arriva al server"


def test_la_stanza_si_puo_cambiare_da_dove_si_parla():
    """Il telefono che si sposta di stanza cambia risposta: nasconderlo in un
    pannello di impostazioni vorrebbe dire che nessuno lo aggiorna mai."""
    testo = _frontend()

    assert 'id="scelta-stanza"' in testo, "non si puo' scegliere la stanza"
    assert (
        _gesto("scegliStanza", quando="al-cambio") + ' data-argomento="valore"' in testo
    ), "la scelta non viene salvata"
    # Sta nella barra del microfono, non fra le impostazioni.
    barra = testo[testo.index('id="chat-form"') : testo.index("<!-- Right: Activity Logs")]
    assert 'id="scelta-stanza"' in barra, "la stanza e' finita lontano da dove si parla"


def test_la_memoria_della_stanza_non_fa_esplodere_la_pagina():
    """In navigazione privata `localStorage` solleva invece di rispondere. Una
    dashboard che non si apre perche' non puo' ricordare una stanza sarebbe un
    prezzo assurdo per una comodita'."""
    testo = _frontend()

    # Solo questa funzione, non i settecento caratteri che seguono: la fetta
    # larga arrivava dentro `stanzaDiQuestoDispositivo`, che ha il suo
    # `catch`, e la guardia restava verde anche togliendo quello di qui.
    corpo = testo[
        testo.index("function satelliteDiQuestoDispositivo") : testo.index(
            "function stanzaDiQuestoDispositivo"
        )
    ]

    assert "try {" in corpo, "l'accesso alla memoria del sito non e' protetto"
    # `catch {` senza nome vale quanto `catch (e) {`: l'errore si raccoglie
    # lo stesso, e da quando ESLint e' in CI i nomi che nessuno legge si
    # tolgono. La guardia guarda che ci sia un `catch`, non come si chiama.
    assert re.search(
        r"\}\s*catch\s*(\(\s*\w+\s*\))?\s*\{", corpo
    ), "un errore della memoria del sito non viene raccolto"
    assert "return null;" in corpo, "senza memoria non si resta un dispositivo senza stanza"


def test_le_stanze_suggerite_vengono_dagli_alias():
    """Un secondo elenco di stanze divergerebbe dal primo, e «Cucina» contro
    «cucina » sono due stanze che non si incontreranno mai."""
    testo = _frontend()

    corpo = testo[testo.index("async function riempiStanzeNote") :][:900]

    assert "'/api/aliases'" in corpo, "le stanze suggerite non vengono dai dispositivi"
    assert "a.room" in corpo


# ----------------------------------- Impostazioni a sezioni richiudibili (#124)


def _scheda_impostazioni() -> str:
    """Tutta la scheda Impostazioni. Dalla #34 e' un file suo: prima si
    ritagliava da `<div id="tab-settings">` fino a `</main>`, e quel
    `</main>` adesso sta in `index.html`, cioe' in un altro file."""
    return _pezzo("impostazioni")


def _a_riposo(pezzo: str) -> str:
    """Cio' che si vede aprendo la scheda, senza toccare niente.

    Di una sezione chiusa resta il solo sommario; tutto il resto della scheda
    — compreso il pulsante «Salva», che sta fuori dalle sezioni — si vede.
    I `<details>` non sono annidati, percio' il non-goloso e' esatto.
    """

    def solo_il_sommario(trovato):
        sommario = re.search(r"<summary.*?</summary>", trovato.group(1), re.S)
        return sommario.group(0) if sommario else ""

    return re.sub(
        r"<details\b(?![^>]*\bopen\b)[^>]*>(.*?)</details>",
        solo_il_sommario,
        _senza_commenti_html(pezzo),
        flags=re.S,
    )


def test_le_impostazioni_si_aprono_una_sezione_alla_volta():
    """Quattrocentoventun righe di markup con tutto aperto insieme.

    Non e' una schermata da leggere, e' una schermata in cui si cerca — e
    cercare in un muro aperto e' piu' lento che aprire la sezione giusta.
    """
    scheda = _senza_commenti_html(_scheda_impostazioni())

    sezioni = re.findall(r'<details class="sezione-impostazioni" data-sezione="(\w+)"([^>]*)>', scheda)

    assert len(sezioni) >= 8, f"le sezioni sono {len(sezioni)}: la scheda non e' stata divisa"

    aperte = [nome for nome, resto in sezioni if "open" in resto]
    assert len(aperte) == 1, f"all'arrivo sono aperte {len(aperte)} sezioni: {aperte}"
    assert aperte[0] == sezioni[0][0], "l'unica aperta non e' la prima"


def test_ogni_sezione_dice_cosa_contiene_anche_da_chiusa():
    """Una sezione chiusa che non dice cosa c'e' dentro e' un cassetto senza
    etichetta: si aprono tutti finche' non salta fuori quello giusto, che e'
    esattamente cio' da cui si voleva uscire."""
    scheda = _senza_commenti_html(_scheda_impostazioni())

    mute = []
    for sezione in re.findall(r'data-sezione="(\w+)".*?</summary>', scheda, re.S):
        blocco = re.search(rf'data-sezione="{sezione}".*?</summary>', scheda, re.S).group(0)
        titolo = re.search(r"<h3[^>]*>(.*?)</h3>", blocco, re.S)
        riga = re.search(r'<p class="text-\[11px\][^"]*"[^>]*>(.*?)</p>', blocco, re.S)
        if not titolo or not riga or len(re.sub(r"<[^>]+>", "", riga.group(1)).strip()) < 15:
            mute.append(sezione)

    assert mute == [], f"queste sezioni non dicono cosa contengono da chiuse: {mute}"


def test_nessun_campo_sparisce_dalle_impostazioni():
    """Richiudere non e' togliere.

    Una guardia che contasse solo cio' che si vede a riposo sarebbe verde
    anche il giorno che qualcuno cancella una sezione invece di chiuderla,
    ed e' l'errore piu' facile da fare riorganizzando una schermata piena.
    """
    testo = _frontend()
    scheda = _senza_commenti_html(_scheda_impostazioni())

    # Gli identificativi dei campi che la pagina legge e scrive davvero.
    letti = set(re.findall(r"getElementById\('(cfg-[\w-]+)'\)", _senza_commenti(testo)))
    assert letti, "nessun campo di configurazione: il test non guarda piu' niente"

    mancanti = sorted(c for c in letti if f'id="{c}"' not in scheda)

    assert mancanti == [], f"la pagina cerca questi campi e non sono piu' in Impostazioni: {mancanti}"


def test_a_riposo_le_impostazioni_mostrano_meno_di_un_terzo_dei_campi():
    """Il criterio della scheda, misurato invece che sperato.

    Misurato: 17 campi e 7 pulsanti visibili a riposo sono diventati 0 campi
    e 1 pulsante — quello che salva. Lo zero non e' un trionfo: la prima
    sezione e' la scelta della palette, che si fa con delle carte e non con
    dei campi. Cio' che conta e' che i 17 restino tutti a un clic.
    """
    scheda = _scheda_impostazioni()

    tutti = len(re.findall(r"<(?:input|select|textarea)\b", _senza_commenti_html(scheda)))
    visibili = len(re.findall(r"<(?:input|select|textarea)\b", _a_riposo(scheda)))

    assert tutti >= 15, f"solo {tutti} campi in tutta la scheda: ne e' sparito qualcuno"
    assert (
        visibili * 3 < tutti
    ), f"a riposo se ne vedono {visibili} su {tutti}: la scheda e' tornata un muro aperto"


def test_la_sezione_aperta_si_ricorda_senza_rompere_niente():
    """`localStorage` non risponde sempre — finestra anonima, dati del sito
    bloccati, spazio esaurito — e in quei casi *lancia*, non torna `null`.

    Ricordare quale sezione era aperta e' una comodita': se costasse una
    schermata bianca sarebbe un pessimo affare.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()

    prova = (
        """
const localStorage = {
    getItem() { throw new Error('dati del sito bloccati'); },
    setItem() { throw new Error('dati del sito bloccati'); },
    removeItem() { throw new Error('dati del sito bloccati'); }
};
const window = { localStorage };
const MEMORIA_SEZIONE = 'prova';
"""
        + _funzione_javascript(testo, "_ricordaSezione")
        + "\n"
        + _funzione_javascript(testo, "_sezioneRicordata")
        + """
_ricordaSezione('voce');
_ricordaSezione(null);
console.log(JSON.stringify({ letta: _sezioneRicordata() }));
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, "con `localStorage` che protesta la schermata si pianta: " + esito.stderr
    assert json.loads(esito.stdout.strip())["letta"] is None


def test_aprire_una_sezione_chiude_le_altre():
    """«Aperta solo quella che serve» e' il titolo della scheda.

    Senza questo si torna al muro un pannello alla volta, e la memoria di
    quale fosse aperta non vorrebbe piu' dire niente.

    La guardia **esegue** la funzione con una finta pagina invece di cercare
    `altra.open = false` nel sorgente: quella riga sopravvive intatta anche
    dentro un `if (false)`, e infatti la prima versione di questo test non se
    ne accorgeva.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()

    prova = (
        """
const memoria = {};
const window = { localStorage: {
    getItem: (k) => (k in memoria ? memoria[k] : null),
    setItem: (k, v) => { memoria[k] = String(v); },
    removeItem: (k) => { delete memoria[k]; }
}};
const MEMORIA_SEZIONE = 'prova';
function safeCreateIcons() {}

function finta(nome, aperta) {
    return {
        nome, open: aperta, dataset: {}, ascoltatori: [],
        getAttribute: function () { return this.nome; },
        addEventListener: function (_evento, fn) { this.ascoltatori.push(fn); }
    };
}
const sezioni = [finta('aspetto', true), finta('casa', false), finta('voce', false)];
const document = { querySelectorAll: () => sezioni };
"""
        + _funzione_javascript(testo, "_ricordaSezione")
        + "\n"
        + _funzione_javascript(testo, "_sezioneRicordata")
        + "\n"
        + _funzione_javascript(testo, "preparaSezioniImpostazioni")
        + """
preparaSezioniImpostazioni();
preparaSezioniImpostazioni();

// Il browser apre la sezione e poi avvisa: si fa lo stesso qui.
sezioni[2].open = true;
sezioni[2].ascoltatori.forEach(fn => fn());

console.log(JSON.stringify({
    aperte: sezioni.filter(s => s.open).map(s => s.nome),
    ricordata: memoria[MEMORIA_SEZIONE] || null,
    ascoltatori: sezioni.map(s => s.ascoltatori.length)
}));
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert visto["aperte"] == [
        "voce"
    ], f"aprendo «voce» restano aperte anche {visto['aperte']}: la scheda torna un muro"
    assert visto["ricordata"] == "voce", "chi torna non ritrova la sezione che stava sistemando"
    # La scheda si riapre molte volte in una sessione: se ogni giro aggiunge
    # un ascoltatore, un solo clic finisce per chiudere le altre N volte.
    assert visto["ascoltatori"] == [1, 1, 1], f"ascoltatori doppi: {visto['ascoltatori']}"


# Le famiglie di grigio velato che la guardia dei colori salta apposta.
# `bg-slate-900/50` — le carte delle palette — e' rimasto grigio scuro su
# bianco proprio per questo, e si e' visto solo guardando la schermata.
def test_anche_i_veli_di_grigio_hanno_un_colore_per_il_giorno():
    """La sorella della guardia dei colori, per la famiglia che quella esclude.

    `test_ogni_fondo_scuro_o_velato_ha_un_colore_per_il_giorno` salta `slate`
    di proposito, perche' i grigi hanno il loro blocco di riscritture. Ma quel
    blocco e' un elenco scritto a mano come tutti gli altri, e restava
    indietro allo stesso modo: `bg-slate-900/50`, `bg-slate-800/20` e
    `bg-slate-800/30` non c'erano.
    """
    testo = _frontend()
    stile = _stile()

    usati = set(re.findall(r"\bbg-(slate-(?:800|900|950)/\d+)\b", testo))
    coperti = {
        c.replace("\\/", "/") for c in re.findall(r"html\.light[^{]*?\.bg-(slate-\d+(?:\\/\d+)?)\b", stile)
    }

    assert usati, "nessun velo di grigio nella pagina: il test non guarda piu' niente"
    mancanti = sorted(f"bg-{c}" for c in usati - coperti)
    assert mancanti == [], f"di giorno questi grigi restano scuri: {mancanti}"
