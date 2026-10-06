"""L'accesso: una caduta del canale si capisce, una destinazione sconosciuta non svuota la pagina, le due schermate del PIN.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import re
import shutil

import pytest
from aiuti_frontend import (
    CARTELLA_JS,
    RADICE,
    _esegui_con_node,
    _funzione_javascript,
    _markup,
    _riga_javascript,
    _testo,
)

# ------------------------------- una caduta si capisce prima di ritentarla


def _banco_del_canale_eventi() -> str:
    """Il codice vero di `eventi.js` piu' un mondo finto in cui farlo girare.

    Si porta dentro le funzioni reali — non una copia, che resterebbe giusta
    anche dopo che l'originale ha smesso di esserlo — e finge tutto il resto:
    la websocket, `fetch`, la pagina, e `setTimeout`, che qui non fa passare
    il tempo ma segna soltanto se qualcuno ha chiesto di ritentare.
    """
    sorgente = _testo(CARTELLA_JS / "eventi.js")
    return "\n".join(
        [
            # `Stato.eventiCollegati` e `Stato.attesaRiconnessione` stanno in `Stato`
            # dalla #34, e `_esegui_con_node` porta dentro il contenitore
            # vero. Qui resta solo il socket, che e' di quest'area sola.
            _riga_javascript(sorgente, "let _eventiSocket"),
            _funzione_javascript(sorgente, "_segnalaStatoEventi"),
            _funzione_javascript(sorgente, "collegaEventi"),
            _funzione_javascript(sorgente, "_laSessioneEFinita"),
            _funzione_javascript(sorgente, "_sessioneScaduta"),
            """
// ----------------------------------------------------------- mondo finto
const registro = { ritentativi: [], barre: [] };
let _ultimoSocket = null;

globalThis.location = { protocol: 'https:', host: 'casa' };
globalThis.document = { getElementById: () => null };
globalThis.getAuthHeaders = () => ({});
globalThis.mostraRifiuto = (stato) => registro.barre.push(stato);
globalThis.setTimeout = (_funzione, attesa) => registro.ritentativi.push(attesa);
globalThis.gestisciEvento = () => {};
globalThis.WebSocket = class {
    constructor() {
        this.readyState = 1;
        _ultimoSocket = this;
    }
};

function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}

async function cade(rispostaDiStato) {
    _eventiSocket = null;
    Stato.attesaRiconnessione = 1000;
    registro.ritentativi = [];
    registro.barre = [];
    globalThis.fetch = rispostaDiStato;
    collegaEventi();
    await _ultimoSocket.onclose();
}

const dentro = async () => ({ ok: true, json: async () => ({ auth_enabled: true, authenticated: true }) });
const fuori = async () => ({ ok: true, json: async () => ({ auth_enabled: true, authenticated: false }) });
const serverGiu = async () => { throw new Error('connessione rifiutata'); };
// La forma esatta che `/api/auth/status` manda a casa con l'autenticazione
// spenta. Provare una forma che il server non produce sarebbe teatro.
const senzaAutenticazione = async () => ({ ok: true, json: async () => ({ auth_enabled: false, authenticated: true }) });
""",
        ]
    )


def test_una_sessione_scaduta_smette_di_ritentare_e_lo_dice():
    """Issue #161.

    Un 403 sull'handshake arriva a JavaScript come una chiusura 1006: la
    stessa che si prende a server spento. Il ciclo ritentava per entrambi, e
    a sessione morta ha ritentato per ore — riempiendo il journal e non
    dicendo niente a chi guardava lo schermo. La casa aveva smesso di
    avvisare e la dashboard sembrava a posto.

    Si esegue il codice vero con `node`: una guardia che cercasse
    `mostraRifiuto` nel sorgente resterebbe verde con la riga svuotata, o
    peggio con la chiamata finita dentro un ramo che non viene mai preso.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = _banco_del_canale_eventi() + """
(async () => {
    await cade(fuori);
    esigi(registro.barre.length === 1, 'la sessione e\\' scaduta e nessuno lo dice');
    esigi(registro.barre[0] === 401, 'l\\'avviso non parla di sessione scaduta');
    esigi(registro.ritentativi.length === 0,
          'si continua a ritentare con la sessione morta: e\\' il difetto della #161');
})();
"""
    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


def test_un_server_irraggiungibile_si_ritenta_ancora_e_in_silenzio():
    """Il gemello, perche' la riparazione non diventi «non si ritenta mai».

    Se il server non risponde affatto, ritentare e' esattamente la cosa
    giusta — ed e' il caso di ogni riavvio del servizio, che dura pochi
    secondi. Mostrare li' «la sessione e' scaduta» sarebbe una bugia, e
    manderebbe a rifare il PIN senza motivo.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = _banco_del_canale_eventi() + """
(async () => {
    await cade(serverGiu);
    esigi(registro.barre.length === 0,
          'il server e\\' irraggiungibile e si accusa la sessione');
    esigi(registro.ritentativi.length === 1, 'non si ritenta piu\\' a server spento');
    esigi(registro.ritentativi[0] === 1000, 'il primo ritentativo non e\\' immediato');
    esigi(Stato.attesaRiconnessione === 2000, 'l\\'attesa non cresce piu\\'');

    // E chi e' dentro davvero: la caduta e' un'altra cosa, si ritenta.
    await cade(dentro);
    esigi(registro.barre.length === 0, 'si accusa la sessione di chi e\\' autenticato');
    esigi(registro.ritentativi.length === 1, 'chi e\\' dentro non si ricollega piu\\'');

    // E in una casa senza autenticazione non esiste sessione da perdere.
    await cade(senzaAutenticazione);
    esigi(registro.barre.length === 0, 'si parla di sessione dove l\\'autenticazione e\\' spenta');
    esigi(registro.ritentativi.length === 1, 'senza autenticazione non ci si ricollega piu\\'');
})();
"""
    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


# --------------------------- una destinazione sconosciuta non svuota la pagina


def _banco_della_navigazione() -> str:
    """`switchTab` vera, dentro una pagina finta di cui si sa tutto.

    La pagina finta e' minima apposta: schede, pulsanti, e niente altro. Se un
    giorno `switchTab` cominciasse a toccare qualcos'altro, il banco lo dice
    con un errore invece di far finta di niente.
    """
    sorgente = _testo(CARTELLA_JS / "navigazione.js")
    dichiarazione = sorgente[sorgente.index("const tabDisplayMap = {") :]
    dichiarazione = dichiarazione[: dichiarazione.index("};") + 2]
    unite = sorgente[sorgente.index("const SCHEDE_UNITE = {") :]
    unite = unite[: unite.index("};") + 2]

    return "\n".join(
        [
            dichiarazione,
            unite,
            _riga_javascript(sorgente, "const SCHEDA_DI_RIPIEGO"),
            _riga_javascript(sorgente, "const SCHEDE_DI_CONFIGURAZIONE"),
            _funzione_javascript(sorgente, "switchTab"),
            """
// -------------------------------------------------------- pagina finta
const avvisi = [];
console.warn = (m) => avvisi.push(m);

function elemento(id) {
    return {
        id,
        style: { display: '' },
        classList: { add() {}, remove() {}, contains: () => false },
    };
}

let pagina = {};
function costruisci(schede) {
    pagina = {};
    for (const nome of schede) pagina[`tab-${nome}`] = elemento(`tab-${nome}`);
}

globalThis.document = {
    getElementById: (id) => pagina[id] || null,
    querySelectorAll: () => [],
};
globalThis.chiudiMenuConfigurazione = () => {};
for (const caricatore of ['loadKnowledge', 'loadSources', 'loadAliases', 'loadRegole',
                          'loadModes', 'disegnaScorciatoia', 'loadUsers', 'loadSettings',
                          'preparaSezioniImpostazioni', 'loadCervello', 'fermaCervello', 'caricaNotifiche']) {
    globalThis[caricatore] = () => {};
}

function visibili() {
    return Object.values(pagina)
        .filter((e) => e.style.display && e.style.display !== 'none')
        .map((e) => e.id);
}

function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}

const TUTTE = Object.keys(tabDisplayMap);
""",
        ]
    )


def test_una_scheda_che_non_esiste_riporta_alla_console():
    """Issue #153.

    `switchTab` nasconde tutte le schede e poi accende quella giusta. Con un
    identificativo sconosciuto la seconda meta' non faceva niente: restava la
    barra in alto e il vuoto sotto. Nessun errore, nessun 500 — un guasto
    muto, che sembra un guasto del codice.

    L'ho incontrato scrivendo `devices` invece di `aliases` in un harness, e
    la schermata bianca mi ha mandato a cercare dalla parte sbagliata.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = _banco_della_navigazione() + """
costruisci(TUTTE);
switchTab('devices');
esigi(visibili().length === 1, 'la pagina resta vuota con una scheda che non esiste');
esigi(visibili()[0] === 'tab-console', 'non si torna alla console: si finisce su ' + visibili());
esigi(avvisi.length === 1, 'la pagina si e\\' sistemata da sola senza dirlo a nessuno');
esigi(avvisi[0].includes('devices'), 'l\\'avviso non dice quale scheda mancava');
"""
    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


def test_il_ripiego_non_ruba_il_posto_alle_schede_che_esistono():
    """Il gemello, perche' la riparazione non diventi «si va sempre in console».

    E l'ultimo caso e' quello che una chiamata ricorsiva avrebbe mancato: su
    una pagina senza nemmeno la console non c'e' dove ripiegare, e allora si
    lascia tutto com'e'. Una schermata vecchia e' sempre meglio di una bianca.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    prova = _banco_della_navigazione() + """
for (const nome of TUTTE) {
    costruisci(TUTTE);
    avvisi.length = 0;
    switchTab(nome);
    esigi(visibili().length === 1, `${nome}: schede accese ` + visibili());
    esigi(visibili()[0] === `tab-${nome}`, `${nome} porta invece a ` + visibili());
    esigi(avvisi.length === 0, `${nome} esiste e viene trattata come sconosciuta`);
}

// E i nomi di prima continuano ad arrivare dove devono, senza avviso:
// non sono sconosciuti, sono tradotti.
for (const vecchio of Object.keys(SCHEDE_UNITE)) {
    costruisci(TUTTE);
    avvisi.length = 0;
    switchTab(vecchio);
    esigi(visibili()[0] === `tab-${SCHEDE_UNITE[vecchio]}`,
          `${vecchio} non porta piu' a ${SCHEDE_UNITE[vecchio]}`);
    esigi(avvisi.length === 0, `${vecchio} viene trattata come sconosciuta invece che tradotta`);
}

// E il caso che una chiamata ricorsiva avrebbe girato a vuoto: una pagina
// che ha delle schede ma **non** la console. Non c'e' dove ripiegare, e
// allora non si tocca niente — invece di nascondere tutto e lasciare il
// bianco, che e' esattamente il difetto da cui si e' partiti.
costruisci(['aliases', 'users']);
switchTab('aliases');
esigi(visibili()[0] === 'tab-aliases', 'il banco non parte da una scheda accesa');
avvisi.length = 0;
switchTab('devices');
esigi(avvisi.length === 1, 'la scheda sconosciuta passa senza un avviso');
esigi(visibili().length === 1 && visibili()[0] === 'tab-aliases',
      'senza console si spegne tutto lo stesso: la pagina resta bianca');
"""
    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


# --------------------- le due schermate del PIN fanno la stessa cosa (#161)


def _corpo_inviato_da(sorgente: str, nome_funzione: str) -> str:
    """Il `JSON.stringify({...})` che una funzione manda a `/api/auth/login`."""
    funzione = _funzione_javascript(sorgente, nome_funzione)
    apertura = funzione.index("JSON.stringify(")
    testo = funzione[apertura:]
    livello, fine = 0, None
    for indice, carattere in enumerate(testo):
        if carattere == "(":
            livello += 1
        elif carattere == ")":
            livello -= 1
            if livello == 0:
                fine = indice + 1
                break
    assert fine, f"{nome_funzione}: la chiamata a JSON.stringify non si chiude"
    return testo[:fine]


def test_le_due_schermate_del_pin_mandano_gli_stessi_campi():
    """Issue #161.

    Il PIN si chiede da due posti: la pagina `accesso.html`, servita a chi non
    e' entrato, e il modale dentro la dashboard, che compare quando la
    sessione muore mentre la pagina e' aperta — cioe' a ogni riavvio del
    servizio, perche' le sessioni stanno in memoria.

    Chiamano la stessa rotta, ma il modale mandava solo `{pin, user_id}`:
    `ricorda_dispositivo` non partiva proprio. Si rientrava senza dispositivo
    fidato, e al riavvio successivo si ricominciava da capo — canale degli
    eventi compreso (#159, #160).

    Due schermate che fanno la stessa cosa in modo leggermente diverso sono
    la premessa del prossimo difetto: qui si pretende che mandino gli stessi
    campi, chiunque le tocchi.
    """

    dal_modale = _corpo_inviato_da(_testo(CARTELLA_JS / "accesso.js"), "handleUnlockSubmit")

    pagina_accesso = _testo(RADICE / "web" / "templates" / "accesso.html")
    campi_pagina = set(re.findall(r"^\s*([a-z_]+):", pagina_accesso, re.M))
    attesi = {"pin", "user_id", "ricorda_dispositivo"}
    assert attesi <= campi_pagina, (
        f"la pagina di accesso non manda piu' {attesi - campi_pagina}: "
        "il confronto non ha piu' un riferimento"
    )

    for campo in attesi:
        assert campo in dal_modale, (
            f"il modale della dashboard non manda «{campo}», la pagina di accesso si'. "
            f"Corpo inviato: {dal_modale}"
        )


def test_il_modale_manda_quello_che_la_casella_dice():
    """Il campo parte, ma segue davvero la spunta?

    Scritto come ricerca di nomi, questo test restava verde con
    `ricorda_dispositivo: false` scritto fisso: il nome del campo c'era, la
    casella veniva anche letta, e il suo valore non arrivava da nessuna
    parte. L'ha detto una mutazione.

    Qui la funzione si esegue davvero, due volte, e si guarda cosa parte.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    pagina = _markup()
    modale = pagina[pagina.index('id="lock-screen-modal"') :][:4000]
    assert 'id="unlock-ricorda"' in modale, "il modale non ha la casella «ricorda questo dispositivo»"
    assert 'type="checkbox"' in modale, "la casella non e' una casella"

    sorgente = _testo(CARTELLA_JS / "accesso.js")
    prova = _funzione_javascript(sorgente, "handleUnlockSubmit") + """
let _profiloDaAccedere = 'alessio';
let spuntata = false;
const inviati = [];

const campi = {
    'unlock-ricorda': { get checked() { return spuntata; } },
    'unlock-pin-input': { value: '482913' },
    'unlock-error-msg': { classList: { add() {}, remove() {} }, innerText: '' },
    'lock-screen-modal': { style: {} },
};
globalThis.document = { getElementById: (id) => campi[id] || null };
globalThis.fetch = async (indirizzo, opzioni) => {
    inviati.push(JSON.parse(opzioni.body));
    // Si fa fallire apposta: la strada del successo richiama mezza
    // dashboard, e qui interessa solo cosa e' partito.
    return { ok: false, json: async () => ({ detail: 'no' }) };
};

function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}

(async () => {
    spuntata = false;
    await handleUnlockSubmit(null);
    // Dopo un rifiuto la funzione svuota il campo del PIN, e senza rimetterlo
    // il secondo giro esce subito. Meglio saperlo qui che scoprirlo come
    // «manda sempre false».
    campi['unlock-pin-input'].value = '482913';
    spuntata = true;
    await handleUnlockSubmit(null);

    esigi(inviati.length === 2, 'non sono partite due richieste: ' + inviati.length);
    esigi(inviati[0].pin === '482913', 'il PIN non parte');
    esigi(inviati[0].user_id === 'alessio', 'il profilo scelto non parte');
    esigi(inviati[0].ricorda_dispositivo === false,
          'senza spunta manda ' + JSON.stringify(inviati[0].ricorda_dispositivo));
    esigi(inviati[1].ricorda_dispositivo === true,
          'con la spunta manda ' + JSON.stringify(inviati[1].ricorda_dispositivo));
})();
"""

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


def test_l_intervista_mostra_quello_che_dice_il_server_non_la_domanda_dello_step():
    """La riparazione della #171 non arrivava sullo schermo.

    La #171 ha insegnato al motore a dire quando non ha capito: «Non sono
    riuscita a ricavarne niente di preciso... controlla quale modello e'
    configurato». Quella frase viaggiava nel campo `message` della risposta.

    E la schermata la buttava via. `renderLearningStep` scriveva
    `qText.innerText = step.question || data.message`, e `step.question` c'e'
    **sempre**: il riconoscimento non e' mai comparso, in nessuna delle sue
    tre forme. Chi rispondeva vedeva la domanda dopo e basta, e continuava a
    credere che la casa stesse imparando — che e' esattamente il difetto che
    la #171 doveva chiudere.

    Non si cerca una stringa nel sorgente: la funzione si esegue, con un DOM
    finto, e si guarda cosa finisce nel paragrafo.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    sorgente = _testo(CARTELLA_JS / "istruisci.js")
    prova = _funzione_javascript(sorgente, "renderLearningStep") + """
function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}
function _html(pezzi) { return pezzi.raw.join(''); }
function safeCreateIcons() {}
const detto = [];
function speakText(testo) { detto.push(testo); }
function loadKnowledge() {}
let lastLearningQuestion = '';

function elemento() {
    return {
        innerText: '', innerHTML: '', value: '', placeholder: '',
        style: {}, classList: { add() {}, remove() {} },
        focus() {}, appendChild() {},
        parentElement: { classList: { add() {}, remove() {} }, innerHTML: '' },
    };
}
const campi = {};
for (const id of ['learning-interview-modal', 'learning-step-badge', 'learning-progress-bar',
                  'learning-topic-title', 'learning-question-text', 'learning-hint-text',
                  'learning-answer-input', 'learning-routine-box', 'learning-routine-desc',
                  'learning-facts-container', 'learning-facts-list', 'learning-submit-btn']) {
    campi[id] = elemento();
}
globalThis.document = {
    getElementById: (id) => campi[id] || null,
    createElement: () => elemento(),
};

const passo = { title: 'Membri della Famiglia', question: 'Chi vive con te in casa?', hint: 'es. Sonia e Thomas.' };

// 1. Il riconoscimento della #171, che precede la domanda successiva.
renderLearningStep({
    is_active: true, is_complete: false, step_index: 1, total_steps: 6, fase: 'domanda',
    step: passo,
    message: "Ho conservato la tua risposta, ma non sono riuscita a ricavarne niente di preciso: controlla quale modello e' configurato. Chi vive con te in casa?",
    new_facts: [], capiti: [], suggerimento: null,
});
const mostrato = campi['learning-question-text'].innerText;
esigi(mostrato.includes('non sono riuscita'),
      'il riconoscimento non arriva sullo schermo: ' + JSON.stringify(mostrato));
esigi(detto.some((t) => t.includes('non sono riuscita')),
      'e nemmeno viene detto a voce: ' + JSON.stringify(detto));

// 2. Il riepilogo della #170: si deve leggere cosa ha capito, prima di dire si'.
renderLearningStep({
    is_active: true, is_complete: false, step_index: 0, total_steps: 6, fase: 'conferma',
    step: passo,
    message: 'Ho capito questo:\\n\\u2022 La casa e\\' ad Arezzo\\nE\\' giusto?',
    new_facts: [], capiti: [{ text: "La casa e' ad Arezzo" }],
    suggerimento: 'Rispondi si\\' per salvare.',
});
const riepilogo = campi['learning-question-text'].innerText;
esigi(riepilogo.includes('Arezzo'),
      'il riepilogo di cosa ha capito non si vede: ' + JSON.stringify(riepilogo));
esigi(campi['learning-hint-text'].innerText.includes('Rispondi'),
      'non dice come si risponde a un riepilogo: ' + JSON.stringify(campi['learning-hint-text'].innerText));
"""

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout
