"""Il tema: leggibilita' di giorno e la decisione prima del primo pixel.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import re
import shutil

import pytest
from aiuti_frontend import (
    CARTELLA_JS,
    PAGINA,
    _esegui_con_node,
    _frontend,
    _funzione_javascript,
    _gesto,
    _stile,
    _testo,
)

# ------------------------------------------------- leggibilita' di giorno


def test_ogni_tinta_pallida_ha_un_colore_per_il_giorno():
    """Il tema chiaro non e' un tema: e' un elenco di eccezioni.

    Le classi di Tailwind vengono compilate per un fondo scuro, e il giorno
    si ottiene riscrivendone i colori una per una sotto `html.light`. Chi
    scrive un pannello nuovo con una tinta che non e' ancora in quell'elenco
    non se ne accorge, a meno di aprire la dashboard di giorno: di sera tutto
    e' perfetto.

    E' successo ai quattro pulsanti dell'editor a nodi — «Quando», «Voce
    Shinra», «Condizione», «Notifica» — rimasti illeggibili per intere
    versioni, mentre il quinto si vedeva benissimo perche' era indigo e
    l'indigo era gia' nell'elenco.

    La guardia non giudica i colori: pretende solo che per ogni tinta
    pallida usata ce ne sia una scelta anche per il giorno.
    """
    testo = _frontend()
    stile = _stile()

    usate = set(re.findall(r"\btext-([a-z]+)-(100|200|300)\b", testo))
    coperte = set(re.findall(r"html\.light[^{]*?\.text-([a-z]+)-(100|200|300)\b", stile))

    assert usate, "nessuna tinta pallida nella pagina: il test non guarda piu' niente"
    mancanti = sorted(f"text-{colore}-{tinta}" for colore, tinta in usate - coperte)
    assert mancanti == [], f"di giorno queste scritte sbiadiscono sul bianco: {mancanti}"


def test_ogni_pulsante_a_tinta_traslucida_si_vede_di_giorno():
    """Stessa storia, dalla parte del fondo.

    Un `bg-emerald-600/30` sul buio e' un velo di verde dietro una scritta
    chiara; sul bianco e' quasi niente, e il pulsante sembra disabilitato.
    """
    testo = _frontend()
    stile = _stile()

    usati = set(re.findall(r"\bbg-([a-z]+)-600/(20|30)\b", testo))
    # `(?!:)` esclude le regole `:hover`. Senza, una tinta col solo colore
    # del passaggio del mouse risultava coperta: e' quello che e' successo
    # alla prima stesura di questa guardia, che non mordeva togliendo la
    # regola vera e lasciando quella dell'hover.
    coperti = set(re.findall(r"html\.light button\.bg-([a-z]+)-600\\/(20|30)(?!:)", stile))

    assert usati, "nessun pulsante a tinta traslucida: il test non guarda piu' niente"
    mancanti = sorted(f"bg-{colore}-600/{quota}" for colore, quota in usati - coperti)
    assert mancanti == [], f"di giorno questi pulsanti sembrano spenti: {mancanti}"


def test_ogni_fondo_scuro_o_velato_ha_un_colore_per_il_giorno():
    """La terza faccia dello stesso problema, e quella che e' sfuggita.

    Due famiglie di fondi non possono restare com'e' sono su bianco: le tinte
    950, nate per stare sul buio, e i veli con opacita', che sul buio sono un
    accenno di colore e sul bianco quasi niente.

    L'etichetta verde «Parla» delle routine e' rimasta illeggibile per intere
    versioni per questo: `bg-emerald-950/80` non era nell'elenco delle
    riscritture — c'erano `/40` e `/60` — mentre `text-emerald-400` si', e
    diventava verde scuro. Verde scuro su verde quasi nero.

    Le due guardie di prima non bastavano: una guarda il testo, l'altra
    guarda i fondi **dei soli pulsanti**. Un'etichetta non e' un pulsante.
    """
    testo = _frontend()
    stile = _stile()

    usati = set(
        re.findall(
            r"\bbg-((?!slate|white|black|gradient)[a-z]+-"
            r"(?:(?:900|950)(?:/\d+)?|(?:300|400|500|600)/\d+))\b",
            testo,
        )
    )
    # `\/` perche' nel foglio di stile la barra della classe va protetta.
    coperti = set(re.findall(r"html\.light[^{]*?\.bg-([a-z]+-\d+(?:\\/\d+)?)\b", stile))
    coperti = {c.replace("\\/", "/") for c in coperti}

    assert usati, "nessun fondo di questo tipo nella pagina: il test non guarda piu' niente"
    mancanti = sorted(f"bg-{c}" for c in usati - coperti)
    assert mancanti == [], f"di giorno questi fondi restano scuri o spariscono: {mancanti}"


def test_la_chiusura_dell_editor_sta_fuori_dalla_finestra():
    """Una X in fila dopo «Salva» sembra una terza azione fra cui scegliere.

    Non lo e': e' l'uscita, e sta dove la cercano le mani — nell'angolo, fuori
    dal riquadro. In fila fra i comandi era anche pericolosa, perche' il
    bersaglio di «chiudi senza salvare» stava a otto pixel da «salva».
    """
    testo = _frontend()

    apertura = testo.index("function renderFlowCanvasModal()")
    corpo = testo[apertura : testo.index("function initCanvasInteractions")]

    assert _gesto("closeModal") in corpo, "l'editor non si puo' piu' chiudere"
    assert "-top-3.5 -right-3.5" in corpo, "la chiusura non e' nell'angolo, fuori dal riquadro"

    # E la fetta attorno a «Salva» non deve contenere anche la chiusura.
    intorno = corpo[corpo.index(_gesto("saveCanvasMode")) :][:600]
    assert _gesto("closeModal") not in intorno, "la X e' tornata in fila accanto a «Salva»"


def test_la_finestra_larga_non_taglia_cio_che_sporge():
    """La X nell'angolo esiste solo se la finestra la lascia sporgere."""
    testo = _frontend()

    corpo = testo[testo.index("function showModal(") : testo.index("function closeModal(")]
    largo = corpo[corpo.index("if (isWide)") : corpo.index("} else {")]
    # I commenti si tolgono prima di guardare: qui sopra ce n'e' uno che
    # **nomina** `overflow-hidden` per spiegare perche' non c'e' piu', e
    # cercarlo nel testo grezzo lo trovava li'.
    largo = re.sub(r"//[^\n]*", "", largo)

    assert "overflow-hidden" not in largo, "la finestra larga taglia la chiusura nell'angolo"
    assert "relative" in largo, "senza posizionamento, l'angolo non e' l'angolo della finestra"


def test_la_tela_dell_editor_segue_il_tema_della_casa():
    """L'unica superficie che restava notturna a mezzogiorno.

    Il nero e la griglia stavano scritti nell'attributo `style` del div: un
    colore dentro l'HTML non lo raggiunge nessun tema, e l'editor restava una
    finestra sulla notte in mezzo a una dashboard bianca.
    """
    testo = _frontend()
    stile = _stile()

    apertura = testo.index('id="flow-canvas"')
    tag = testo[apertura : testo.index(">", apertura)]

    assert "tela-flusso" in tag, "la tela non usa la classe che porta il tema"
    assert "bg-[#" not in tag, "la tela ha ancora un fondo scritto a mano"
    assert "background-image" not in tag, "la griglia e' ancora chiusa dentro l'attributo style"
    assert ".tela-flusso {" in stile, "la classe della tela non esiste"
    assert "html.light .tela-flusso" in stile, "di giorno la tela resta notturna"


def test_non_si_registra_mentre_il_modello_si_sta_caricando():
    """Lo stesso principio che questa schermata gia' applica al motore
    assente, un passo piu' in la'.

    Al primo avvio i pesi di Whisper si scaricano, e possono volerci minuti.
    Registrare in quell'intervallo vuol dire parlare dentro un'attesa che
    verra' tagliata da qualunque proxy stia davanti al server — in casa e'
    uscito un «Errore 524», che non c'entra niente con quello che era stato
    detto.
    """
    testo = _frontend()

    corpo = testo[
        testo.index("async function toggleTrascrizioneLocale(") : testo.index(
            "async function toggleWebSpeech("
        )
    ]
    corpo = re.sub(r"//[^\n]*", "", corpo)

    assert "stato.modello_caricato" in corpo, "la pagina non guarda se i pesi sono in memoria"
    assert corpo.index("stato.modello_caricato") < corpo.index(
        "new MediaRecorder"
    ), "il controllo arriva dopo aver gia' cominciato a registrare"
    # Il messaggio arriva dal server: «sto preparando» e «ci ho provato e non
    # ci sono riuscito» sono due cose diverse, e una frase fissa scritta qui
    # dentro non puo' distinguerle — ripeterebbe «riprova fra un minuto,
    # succede una volta sola» anche a caricamento gia' morto.
    assert "stato.spiegazione_modello" in corpo, "il motivo e' una frase fissa scritta nella pagina"


def test_lo_stato_della_voce_non_si_ricorda_finche_non_e_definitivo():
    """«Non ancora pronto» e' vero adesso e falso fra un minuto.

    La risposta si teneva da parte alla prima lettura: ricordare un «sto
    caricando» vorrebbe dire un microfono spento fino al prossimo
    ricaricamento della pagina, cioe' un rimedio peggiore del difetto.
    """
    testo = _frontend()

    corpo = testo[
        testo.index("async function leggiStatoVoce()") : testo.index(
            "async function toggleSpeechRecognition()"
        )
    ]
    corpo = re.sub(r"//[^\n]*", "", corpo)

    assert "modello_caricato" in corpo, "la pagina si ricorda anche uno stato provvisorio"


# ------------------------------- il tema deciso prima del primo pixel (#152)


def _copione_in_linea_del_tema() -> str:
    """Il blocco che decide il tema in cima a `index.html`.

    Si prende dal markup vero e si esegue: e' l'unico modo per sapere che
    decide **la stessa cosa** di `avvio.js`, invece di sperarlo.
    """
    pagina = _testo(PAGINA)
    apertura = pagina.index("var scelta = localStorage.getItem('shinra_theme_mode')")
    inizio = pagina.rindex("(function () {", 0, apertura)
    fine = pagina.index("})();", apertura)
    # Si toglie la chiamata: nella pagina il blocco parte da solo, qui serve
    # una funzione da poter chiamare a comando, con l'orologio che vogliamo.
    return pagina[inizio:fine] + "})"


def test_il_tema_deciso_subito_e_quello_che_decide_avvio_js():
    """Issue #152: due regole per la stessa domanda, e devono dire lo stesso.

    Il tema si decide due volte — una in linea nel `<head>`, prima che la
    pagina si disegni, e una in `avvio.js` quando tutto e' caricato. Due
    copie della stessa regola divergono: basta che qualcuno sposti l'alba
    dalle 7:00 alle 6:30 in un posto solo, e la pagina cambia colore mezzo
    secondo dopo essere apparsa.

    Qui si eseguono **tutte e due**, ora per ora, e si pretende lo stesso
    verdetto. Una guardia che confrontasse le stringhe `7.0` e `19.5` nei due
    file resterebbe verde con la logica invertita.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    avvio = _testo(CARTELLA_JS / "avvio.js")

    prova = (
        _funzione_javascript(avvio, "getSolarTheme")
        + """
const inLinea = """
        + _copione_in_linea_del_tema()
        + """;

let memoria = {};
globalThis.localStorage = {
    getItem: (k) => (k in memoria ? memoria[k] : null),
    setItem: (k, v) => { memoria[k] = String(v); },
};
globalThis.document = {
    documentElement: {
        classi: new Set(['dark']),
        classList: {
            remove(...n) { for (const x of n) globalThis.document.documentElement.classi.delete(x); },
            add(...n) { for (const x of n) globalThis.document.documentElement.classi.add(x); },
        },
        setAttribute() {},
    },
};

const VeraData = Date;
function fingiOra(ore, minuti) {
    globalThis.Date = class extends VeraData {
        getHours() { return ore; }
        getMinutes() { return minuti; }
    };
}

function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}

// A tutte le ore, in modalita' automatica, le due regole devono dire lo stesso.
for (let ora = 0; ora < 24; ora++) {
    for (const minuti of [0, 29, 30, 31, 59]) {
        memoria = {};
        fingiOra(ora, minuti);
        document.documentElement.classi = new Set(['dark']);
        inLinea();
        const subito = document.documentElement.classi.has('light') ? 'light' : 'dark';
        const dopo = getSolarTheme();
        esigi(subito === dopo,
              `alle ${ora}:${minuti} il tema in linea dice ${subito} e avvio.js dice ${dopo}`);
    }
}

// E una scelta esplicita vince sull'orologio, in tutte e due i sensi.
for (const scelta of ['light', 'dark']) {
    memoria = { shinra_theme_mode: scelta };
    fingiOra(scelta === 'light' ? 3 : 12, 0);   // l'ora dice il contrario
    document.documentElement.classi = new Set([scelta === 'light' ? 'dark' : 'light']);
    inLinea();
    esigi(document.documentElement.classi.has(scelta),
          `la scelta esplicita «${scelta}» viene ignorata dal tema in linea`);
    esigi(!document.documentElement.classi.has(scelta === 'light' ? 'dark' : 'light'),
          `restano tutte e due le classi: «${scelta}» e il suo contrario`);
}

// Senza localStorage non si esplode: resta il `dark` scritto sul tag.
memoria = {};
globalThis.localStorage = { getItem() { throw new Error('bloccato'); }, setItem() {} };
document.documentElement.classi = new Set(['dark']);
fingiOra(12, 0);
inLinea();
esigi(document.documentElement.classi.has('dark'),
      'con localStorage bloccato il tema in linea lascia la pagina senza classe');
"""
    )

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


def test_il_tema_si_decide_prima_dei_copioni():
    """Il blocco sta in cima al `<head>`, davanti a ogni richiesta di rete.

    Se qualcuno lo sposta dopo i `<link>` o dopo Tailwind, torna la finestra
    di schermata scura — piu' corta, ma torna. E' l'unica cosa che il
    posizionamento garantisce, quindi va guardata qui.
    """
    pagina = _testo(PAGINA)
    tema = pagina.index("shinra_theme_mode")
    for piu_lento in ('<link rel="stylesheet"', "tailwind.css", 'rel="preload"', "<body"):
        assert pagina.index(piu_lento) > tema, (
            f"«{piu_lento}» viene prima della decisione sul tema: "
            "la pagina si disegna scura e poi cambia colore."
        )
