"""La console: le scelte della schermata, la colonna di destra e i tre ingressi.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest
from aiuti_frontend import (
    CARTELLA_JS,
    _esegui_con_node,
    _frontend,
    _funzione_javascript,
    _gesto,
    _pezzo,
    _senza_commenti,
    _senza_commenti_html,
    _testo,
)

# ------------------------------------------- le scelte di questa schermata


def test_il_ruolo_si_sceglie_e_non_si_deduce_dall_avatar():
    """Il difetto che questa schermata esiste per chiudere.

    Il ruolo veniva calcolato al salvataggio da avatar e fascia d'eta', e la
    fascia «ragazzo» finiva nel ramo `adult`: un tredicenne riceveva il ruolo
    degli adulti, cioe' serrature e allarme. Adesso il ruolo e' un campo, e
    quello che il modulo manda al server e' quello scelto.
    """
    testo = _frontend()

    assert (
        "age_group === 'child' ? 'child' : 'adult'" not in testo
    ), "il ruolo viene ancora dedotto dalla fascia d'eta'"
    assert 'id="new-u-role"' in testo, "manca il campo per scegliere il ruolo"
    assert "document.getElementById('new-u-role')" in testo, "il ruolo scelto non viene letto"


def test_la_scheda_profili_porta_ruoli_e_dispositivi():
    """Le due sezioni esistono e vengono davvero caricate.

    Le rotte c'erano gia' dalla v0.2.0; mancava solo il modo di usarle senza
    chiamare l'API a mano. Una sezione nel markup che nessuno popola sarebbe
    lo stesso problema con un aspetto migliore.
    """
    testo = _frontend()

    for identificativo in ("sezione-ruoli", "ruoli-lista", "sezione-dispositivi", "dispositivi-lista"):
        assert f'id="{identificativo}"' in testo, f"manca la sezione {identificativo}"

    corpo = testo[testo.index("async function loadUsers()") :]
    corpo = corpo[: corpo.index("function openAddUserModal()")]
    assert (
        "loadRuoli()" in corpo and "loadDispositivi()" in corpo
    ), "aprire la scheda profili non carica ruoli e dispositivi"


def test_le_sezioni_riservate_si_nascondono_a_chi_non_amministra():
    """Nascondere non protegge — il server rifiuta comunque — ma mostrare un
    pannello che risponde sempre 403 fa sembrare rotta l'applicazione."""
    testo = _frontend()

    assert "caricaPermessiCorrenti" in testo, "la pagina non chiede quali permessi ha chi la guarda"
    assert "posso('utenti.gestisci')" in testo, "la sezione dei ruoli non e' condizionata al permesso"


def test_il_microfono_non_torna_alla_web_speech_api_di_nascosto():
    """Il difetto della issue #31, in forma di guardia.

    Il riconoscimento vocale usava la Web Speech API, che manda l'audio ai
    server del produttore del browser: ogni parola detta all'assistente usciva
    di casa, mentre il README prometteva il contrario. Adesso l'audio va al
    server, e la vecchia strada resta solo per chi la sceglie scrivendola in
    configurazione.

    La guardia serve perche' la ricaduta e' facile da riscrivere per sbaglio —
    e' una riga — e non si vedrebbe: continuerebbe a funzionare benissimo.

    I commenti si tolgono prima di guardare. La prima scrittura di questa
    guardia cercava `in_casa` nel corpo della funzione e lo trovava nel
    commento che spiega cosa fa: restava verde anche dopo aver spento il
    controllo che descriveva.
    """
    testo = _frontend()

    apertura = testo.index("async function toggleSpeechRecognition()")
    corpo = testo[apertura : testo.index("async function toggleTrascrizioneLocale(")]
    corpo = re.sub(r"//[^\n]*", "", corpo)

    assert (
        "webkitSpeechRecognition" not in corpo
    ), "il microfono usa ancora la Web Speech API prima di chiedere al server"
    assert "/api/voce/stato" in testo, "la pagina non chiede al server quale motore usare"
    assert "'/api/voce/trascrivi'" in testo, "l'audio non viene mandato al server"
    assert "stato.in_casa" in corpo, "la scelta del motore non guarda se l'audio resta in casa"
    assert "toggleTrascrizioneLocale" in corpo, "la strada che tiene l'audio in casa non viene mai imboccata"


def test_i_pin_dei_cavi_hanno_una_dimensione():
    """Il difetto per cui nell'editor non si e' mai potuto tirare un cavo.

    `port-pin` non era definita da nessuna parte e non e' una classe di
    Tailwind: i pin erano `div` senza dimensione — invisibili e non
    cliccabili. Non se n'era accorto nessuno perche' un difetto piu' a monte
    lo nascondeva: il disegno spariva comunque al salvataggio, perche' la
    tabella delle routine non aveva le colonne per tenerlo.

    Riferimento: issue #28.
    """
    testo = _frontend()

    assert ".port-pin {" in testo, "i pin dei cavi non hanno nessuno stile: sarebbero invisibili"
    for regola in (".port-pin-in", ".port-pin-out", ".port-pin-vero", ".port-pin-falso"):
        assert regola in testo, f"manca la posizione di {regola}"


def test_una_condizione_ha_due_uscite_distinte():
    """Un'uscita sola non e' una condizione: e' un filtro che a volte ferma
    tutto, e chi lo disegna si aspetta due strade."""
    testo = _frontend()

    assert 'data-al-premere="onPinMouseDown" data-args="${_args(node.id, \'vero\')}"' in testo
    assert 'data-al-premere="onPinMouseDown" data-args="${_args(node.id, \'falso\')}"' in testo
    assert "nuovo.ramo = ramo" in testo, "il ramo non viene scritto sull'arco"


def test_il_salvataggio_mostra_cosa_non_va_e_dove():
    """«Il grafo non e' valido» manda a guardarne trenta, e chi ne ha
    disegnati trenta non lo fa: salva lo stesso, o rinuncia."""
    testo = _frontend()

    # La **chiamata**, col punto e virgola, non il nome della funzione.
    # Questa guardia e' stata riscritta due volte per lo stesso motivo: prima
    # cercava `illuminaNodiInErrore` ovunque nel file e la trovava nella
    # definizione; poi lo cercava nel ramo giusto e lo trovava lo stesso,
    # perche' la definizione sta subito dopo e ricadeva dentro la fetta.
    # Restava verde con la chiamata tolta.
    apertura = testo.index("} else if (res.status === 400) {")
    ramo = testo[apertura : testo.index("function illuminaNodiInErrore")]

    assert "illuminaNodiInErrore(problemi);" in ramo, "i nodi in errore non vengono indicati"
    assert "dettaglio.problemi" in ramo, "i problemi del server non vengono letti"
    assert "function illuminaNodiInErrore" in testo, "la funzione non esiste"
    assert "nodo-in-errore" in testo


def test_il_microfono_si_spegne_davvero_dopo_la_registrazione():
    """La spia di registrazione del browser che resta accesa e' il modo
    peggiore di far credere a qualcuno che lo stai ascoltando sempre."""
    testo = _frontend()

    corpo = testo[testo.index("registratore.onstop") :][:1200]
    # Senza fissare la spaziatura: da quando Prettier e' in CI, `t => t.stop()`
    # e `(t) => t.stop()` sono la stessa riga scritta due volte, e una guardia
    # che sceglie fra le due fallisce al primo riallineamento invece che al
    # primo microfono lasciato acceso.
    assert re.search(
        r"getTracks\(\)\.forEach\(\s*\(?\s*\w+\s*\)?\s*=>\s*\w+\.stop\(\)", corpo
    ), "il flusso del microfono non viene chiuso"


def test_la_simulazione_la_chiede_al_server():
    """Prima la simulazione era una visita in ampiezza scritta nella pagina, e
    percorreva **tutti** gli archi: mostrava una condizione che accende
    entrambi i rami, cioe' l'unica cosa che una condizione non fa.

    Una simulazione che mostra un percorso diverso da quello vero e' peggio di
    nessuna simulazione, perche' ci si crede. Questa guardia impedisce che la
    visita rientri dalla finestra.

    Riferimento: issue #28.
    """
    testo = _frontend()

    apertura = testo.index("async function simulateCanvasFlow()")
    corpo = testo[apertura : testo.index("function spegniLaSimulazione")]

    assert "'/api/modes/simula'" in corpo, "la simulazione non chiede niente al server"
    assert "esito.visitati" in corpo, "la pagina non usa i nodi che il server dice di aver percorso"
    assert "queue" not in corpo, "e' tornata una visita del grafo dentro la pagina"


def test_la_simulazione_accende_un_ramo_solo():
    """Il ramo non percorso deve restare spento: due rami accesi dicono che
    succedono due cose che si escludono a vicenda."""
    testo = _frontend()

    apertura = testo.index("async function simulateCanvasFlow()")
    corpo = testo[apertura : testo.index("function spegniLaSimulazione")]

    assert "e.ramo === scelta.ramo" in corpo, "i cavi si accendono senza guardare il ramo scelto"
    assert "visitati.includes(e.to)" in corpo, "si accende anche un cavo verso un nodo mai raggiunto"


def test_la_simulazione_dice_perche_ha_scelto_quel_ramo():
    """Il ramo preso senza il perche' e' indistinguibile da un ramo preso a
    caso."""
    testo = _frontend()

    corpo = testo[testo.index("function mostraLeDecisioni") :][:1400]

    assert "(d.motivo ||" in corpo, "il motivo della decisione non viene scritto sotto il nodo"
    # L'etichetta e' `truncate`: un motivo lungo si legge solo fermandoci
    # sopra il mouse. Senza il titolo, di una condizione fallita si legge
    # «ramo no: la condizione non e' sod...» e non si sa quale.
    assert "etichetta.title = d.motivo" in corpo, "il motivo lungo non si puo' leggere per intero"
    assert "decisione-del-nodo" in testo


def test_l_innesco_di_una_routine_si_puo_scegliere():
    """I nodi trigger temporali della scheda #28. Senza il selettore, il nodo
    resta quello che era: un innesco vocale e basta."""
    testo = _frontend()

    assert _gesto("setTipoInnesco", quando="al-cambio") in testo, "non si puo' cambiare tipo di innesco"
    for tipo in ("orario", "alba", "tramonto", "stato", "evento"):
        assert f'value="{tipo}"' in testo, f"manca l'innesco «{tipo}» fra le scelte"


def test_cambiare_tipo_di_innesco_riparte_da_zero():
    """I campi di un innesco a orario non valgono per uno su soglia: lasciarli
    in giro produce una regola che porta dietro dati che nessuno legge."""
    testo = _frontend()

    corpo = testo[testo.index("function setTipoInnesco") : testo.index("function setDatoInnesco")]

    assert "node.data.trigger = predefiniti[tipo]" in corpo, "i campi del tipo precedente restano li'"


def _colonna_della_console() -> str:
    """La colonna di destra della console vocale: un terzo della prima
    schermata che si apre, e l'unica parte della pagina che sta accesa
    davanti a chi abita la casa senza che l'abbia chiesta.

    Prima della #34 finiva «dove comincia la scheda dopo»; adesso finisce
    dove finisce il file, che e' la stessa cosa detta meglio.
    """
    console = _pezzo("console")
    return console[console.index("<!-- Right: Activity Logs & Active Timers -->") :]


def test_la_colonna_della_console_non_porta_piu_la_diagnostica():
    """Il nome del modello e la frase di Alexa non riguardano chi abita qui.

    Stavano accesi un terzo dello schermo, sulla schermata che si apre per
    prima, e non cambiano da un'ora all'altra: il modello si sceglie una
    volta, la frase di invocazione si legge una volta nella vita. Nessuna
    delle due sparisce — si leggono in Impostazioni, che e' dove si va
    quando si vogliono cambiare.
    """
    colonna = _colonna_della_console()

    assert "Stato Sistema" not in colonna, "il pannello della diagnostica e' ancora acceso"
    assert 'id="model-name-badge"' not in colonna, "il nome del modello e' ancora nella colonna"
    assert "Alexa, apri" not in colonna, "la frase di invocazione e' ancora nella colonna"
    assert 'id="tool-logs"' not in colonna, "il registro dei tool e' ancora un pannello acceso"


def test_il_modello_e_la_frase_di_alexa_si_leggono_nelle_impostazioni():
    """Togliere non e' nascondere: il patto e' che tutto resti raggiungibile.

    Una guardia che controllasse solo l'assenza dalla console sarebbe verde
    anche il giorno che qualcuno cancella le due informazioni invece di
    spostarle, ed e' esattamente l'errore che questa riorganizzazione puo'
    fare.
    """
    testo = _frontend()
    impostazioni = testo.index('<div id="tab-settings"')

    for identificativo in ('id="model-name-badge"', 'id="anteprima-invocazione"'):
        assert identificativo in testo, f"{identificativo} non esiste piu' da nessuna parte"
        assert (
            testo.index(identificativo) > impostazioni
        ), f"{identificativo} non sta in Impostazioni, dove si va per cambiarlo"


def test_la_frase_di_alexa_viene_dal_campo_e_non_da_una_riga_scritta_a_mano():
    """Nella console era scritta a mano: «Alexa, apri Kyra».

    Restava quella anche dopo aver cambiato il nome di invocazione, cioe'
    era un'informazione che poteva mentire — e sulla schermata principale,
    per giunta. Adesso si costruisce da cio' che c'e' nel campo, e il test
    la costruisce davvero invece di cercare la parola nel sorgente.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    funzione = _funzione_javascript(_frontend(), "updateAlexaGeneratorName")

    prova = (
        """
const campi = {
    'anteprima-invocazione': { innerText: '' },
    'alexa-generated-json': { value: '' }
};
const document = { getElementById: (id) => campi[id] || null };
function getAlexaInteractionModelJson() { return '{}'; }
"""
        + funzione
        + """
updateAlexaGeneratorName('Jarvis');
console.log(campi['anteprima-invocazione'].innerText);
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    detto = esito.stdout.strip()
    assert "jarvis" in detto, f"la frase non segue il nome scelto: {detto}"
    assert "kyra" not in detto, f"la frase ripete il nome di prima: {detto}"


def test_la_storia_dei_tool_non_si_perde_a_finestra_chiusa():
    """Il registro esce dalla colonna ma non dalla pagina.

    Scriveva direttamente nel pannello: tolto il pannello, ogni chiamata
    sarebbe finita nel vuoto e la finestra aperta dopo avrebbe mostrato una
    casa che non ha mai fatto niente. Serve proprio quando qualcosa non
    torna, cioe' sempre dopo, mai durante.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()
    prova = (
        """
const conta = { innerText: '' };
const document = { getElementById: (id) => (id === 'conta-tool' ? conta : null) };
let _toolInvocati = [];
function _disegnaToolInvocati() { throw new Error('la finestra e\\' chiusa'); }
"""
        + _funzione_javascript(testo, "logAction")
        + """
logAction('luce', { stanza: 'cucina' }, 'accesa');
logAction('meteo', { citta: 'Ancona' }, 'sereno');
console.log(JSON.stringify({
    quanti: _toolInvocati.length,
    primo: _toolInvocati[0].tool,
    conta: conta.innerText
}));
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())
    assert visto["quanti"] == 2, "le chiamate non restano da nessuna parte"
    assert visto["primo"] == "meteo", "la piu' recente non e' in cima"
    assert "2" in visto["conta"], f"il numero non si vede dalla colonna: {visto['conta']}"


def test_la_colonna_dice_cosa_scattera_e_in_che_ordine():
    """Cio' che e' entrato al posto della diagnostica.

    Tre cose che una lista ingenua confonde: una regola zittita non
    scattera', una su evento non ha un orario, e l'ordine di arrivo del
    server non e' l'ordine dell'orologio. Se la colonna deve raccontare
    adesso, deve raccontarlo giusto.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()
    prova = (
        # Il vero `sicurezza.js`, non un finto: da quando la colonna passa da
        # `_html`, provarla con un finto proverebbe il finto.
        _testo(CARTELLA_JS / "sicurezza.js")
        + """
const contenitore = { innerHTML: '' };
const document = { getElementById: () => contenitore };
function _quandoLeggibile(iso) { return 'quando:' + iso; }
function safeCreateIcons() {}
function switchTab() {}
"""
        + _funzione_javascript(testo, "disegnaProssimiScatti")
        + """
disegnaProssimiScatti([
    { nome: 'TARDI', attiva: true, prossimo: '2030-01-01T23:00:00' },
    { nome: 'ZITTITA', attiva: false, prossimo: '2030-01-01T06:00:00' },
    { nome: 'SUEVENTO', attiva: true, prossimo: null },
    { nome: 'PRESTO', attiva: true, prossimo: '2030-01-01T07:00:00' }
]);
console.log(JSON.stringify(String(contenitore.innerHTML)));
disegnaProssimiScatti([{ nome: 'ZITTITA', attiva: false, prossimo: '2030-01-01T06:00:00' }]);
console.log(JSON.stringify(String(contenitore.innerHTML)));
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    con_regole, senza_regole = (riga for riga in esito.stdout.strip().splitlines() if riga)

    assert "ZITTITA" not in con_regole, "una regola messa a tacere e' annunciata come imminente"
    assert "SUEVENTO" not in con_regole, "una regola su evento compare con un orario che non ha"
    assert con_regole.index("PRESTO") < con_regole.index("TARDI"), "gli scatti non sono in ordine di orologio"

    # Quando non scatta niente, la colonna non resta uno spazio bianco: dice
    # come si riempie. E' la stessa regola di tutte le altre liste (#127).
    assert "Niente in programma" in senza_regole, "la colonna vuota non dice niente"
    assert "switchTab" in senza_regole, "dal vuoto non si raggiunge cio' che lo riempie"


# Quanti elementi restava acceso a riposo la colonna, prima di questa
# riorganizzazione: 27 tag e 3 titoli. E' un cricchetto come quello
# dell'architettura — puo' scendere, non risalire.
TAG_NELLA_COLONNA = 19


TITOLI_NELLA_COLONNA = 1


def test_la_colonna_della_console_resta_leggera():
    """La misura, invece della sensazione.

    La scheda chiedeva un calo di almeno un terzo degli elementi a riposo.
    Misurato: i tag della colonna sono passati da 27 a 19 (-30%), i titoli
    da 3 a 1 (-67%), i pannelli accesi da 3 a 2, e le informazioni di
    diagnostica da 3 a nessuna. Il -30% non e' il terzo promesso: e' scritto
    qui perche' resti scritto quanto e' stato davvero, e non quanto era
    stato detto.

    Il numero qui sotto non e' un obiettivo: e' un tetto. Serve il giorno
    che qualcuno aggiunge un pannello «solo questo» a questa colonna.
    """
    colonna = re.sub(r"<!--.*?-->", "", _colonna_della_console(), flags=re.S)

    tag = len(re.findall(r"<(?!/)[a-zA-Z]", colonna))
    titoli = len(re.findall(r"<h\d", colonna))

    assert tag <= TAG_NELLA_COLONNA, (
        f"la colonna della console e' tornata a pesare: {tag} tag, il tetto e' "
        f"{TAG_NELLA_COLONNA}. Se il pannello nuovo racconta davvero adesso, "
        "abbassa il tetto togliendo altro; se no, non va qui."
    )
    assert titoli <= TITOLI_NELLA_COLONNA, (
        f"{titoli} titoli nella colonna: ogni titolo in piu' e' una cosa in "
        "piu' da leggere prima di trovare quella che serve"
    )


# --------------------------------------------- da otto ingressi a tre (#128)


# Le schede che devono restare al primo livello, e quelle che stanno dietro
# «Configurazione». Non e' un dettaglio di gusto: tre si usano ogni giorno,
# quattro si aprono una volta e poi quasi mai, e trattarle come voci gemelle
# e' la scelta che generava piu' affaticamento di qualunque altra.
PRIMO_LIVELLO = ["console", "automazioni", "aliases"]


DIETRO_LA_CONFIGURAZIONE = ["knowledge", "sources", "users", "settings", "cervello"]


def _barra_desktop(testo: str) -> str:
    inizio = testo.index("<!-- Desktop Navigation Tabs Bar")
    return testo[inizio : testo.index("<!-- Mobile Drawer Menu", inizio)]


def _cassetto_telefono(testo: str) -> str:
    inizio = testo.index("<!-- Mobile Drawer Menu")
    return testo[inizio : testo.index("</header>", inizio)]


def test_il_primo_livello_ha_tre_ingressi_piu_la_configurazione():
    """Otto schede dello stesso peso, ciascuna con un'etichetta da due parole,
    su una riga che riempiva tutta la larghezza.

    Ma non erano la stessa cosa: «parla alla casa» e «configura le fonti RSS»
    non si usano con la stessa frequenza, e metterle sulla stessa riga chiede
    di rileggerla per intero ogni volta.
    """
    barra = _senza_commenti_html(_barra_desktop(_frontend()))

    ingressi = re.findall(r'id="tab-btn-([a-z]+)"', barra)

    assert ingressi == [*PRIMO_LIVELLO, "configurazione"], (
        f"gli ingressi di primo livello sono {ingressi}: devono essere i tre di "
        "ogni giorno piu' l'unico ingresso di configurazione"
    )


def test_le_quattro_schede_di_configurazione_restano_raggiungibili():
    """Ridurre gli ingressi non e' togliere le schede.

    Una guardia che contasse solo i pulsanti sarebbe verde anche il giorno
    che qualcuno cancella le quattro schede invece di raggrupparle, ed e'
    l'errore piu' facile da fare riorganizzando una navigazione.
    """
    testo = _frontend()
    menu = testo[testo.index('id="menu-configurazione"') : testo.index("<!-- Mobile Drawer Menu")]

    for scheda in DIETRO_LA_CONFIGURAZIONE:
        assert f'id="tab-{scheda}"' in testo, f"la scheda {scheda} non esiste piu'"
        assert _gesto("switchTab", scheda) in menu, f"dal menu di configurazione non si arriva a {scheda}"


def test_dal_telefono_la_navigazione_e_una_sola():
    """Su telefono non c'e' spazio per un menu dentro un menu.

    Il cassetto resta un elenco solo, con le quattro di configurazione
    raggruppate sotto una riga che dice cosa sono — non una seconda
    navigazione scritta a parte.
    """
    cassetto = _senza_commenti_html(_cassetto_telefono(_frontend()))

    destinazioni = re.findall(r'data-gesto="switchTabMobile" data-testo="([a-z]+)"', cassetto)

    assert destinazioni == PRIMO_LIVELLO + DIETRO_LA_CONFIGURAZIONE, (
        f"dal telefono si arriva a {destinazioni}: manca qualcosa, o l'ordine "
        "non e' piu' «prima quelle di ogni giorno»"
    )
    assert "Configurazione" in cassetto, "il gruppo di configurazione non si presenta"


def test_l_editor_a_nodi_resta_al_primo_livello():
    """Il vincolo esplicito della scheda, e l'unico che il proprietario della
    casa ha messo per iscritto guardando l'analisi: *«lo condivido a pieno
    tranne la parte di rimuovere editor delle automazioni, quello rimane»*.

    Rami, condizioni, ritardi e sequenze non si esprimono in un modulo. Sta
    dentro «Automazioni e routine» perche' e' li' che appartiene, non per
    levarlo di mezzo: si apre da una scheda di primo livello, senza passare
    dalla configurazione.
    """
    testo = _frontend()

    inizio = testo.index('<div id="tab-automazioni"')
    scheda = testo[inizio : testo.index('<div id="tab-users"', inizio)]

    assert _gesto("openModularModeBuilder") in scheda, "l'editor non si apre da questa scheda"
    assert 'id="modes-list"' in scheda, "l'elenco delle routine non e' in questa scheda"
    assert 'id="regole-lista"' in scheda, "l'elenco delle automazioni non e' in questa scheda"

    barra = _barra_desktop(testo)
    assert 'id="tab-btn-automazioni"' in barra, "la scheda che contiene l'editor non e' al primo livello"


def test_le_vecchie_destinazioni_portano_ancora_da_qualche_parte():
    """Due schede diventate una lasciano dietro dei nomi.

    `switchTab('modes')` scritto in un punto qualunque della pagina — o un
    collegamento che qualcuno si e' salvato — non deve portare in una scheda
    che non esiste piu': porterebbe a una schermata bianca senza che niente
    lo spieghi. La traduzione sta in un posto solo, dove si vede.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()
    dichiarazione = testo[testo.index("const SCHEDE_UNITE = {") :]
    dichiarazione = dichiarazione[: dichiarazione.index("};") + 2]

    prova = dichiarazione + """
const mancanti = ['modes', 'regole'].filter(v => SCHEDE_UNITE[v] !== 'automazioni');
if (mancanti.length) { console.error('non tradotte: ' + mancanti); process.exit(1); }
console.log('ok');
"""

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    assert "tabId = SCHEDE_UNITE[tabId] || tabId;" in _senza_commenti(
        testo
    ), "la traduzione esiste ma `switchTab` non la usa"


def test_dentro_la_configurazione_la_barra_dice_ancora_dove_sei():
    """Le quattro schede raggruppate non hanno piu' un pulsante proprio.

    Senza questo, entrare in Impostazioni spegne ogni pulsante della barra: la
    navigazione smette di dire dov'e' chi la guarda, ed e' peggio della riga
    lunga da cui si e' partiti.
    """
    testo = _senza_commenti(_frontend())

    corpo = _funzione_javascript(testo, "switchTab")

    assert (
        "SCHEDE_DI_CONFIGURAZIONE.includes(tabId)" in corpo
    ), "dentro le quattro schede raggruppate non si accende niente"
    assert "tab-btn-configurazione" in corpo, "non si accende il loro ingresso"


def test_il_menu_di_configurazione_si_chiude():
    """Un menu che resta aperto dietro la schermata e' un pezzo di
    interfaccia che nessuno ha chiesto.

    Tre modi di chiuderlo, e tutti e tre servono: scegliendo una voce (o il
    menu copre cio' che si e' appena aperto), cliccando fuori, con Esc.
    """
    testo = _senza_commenti(_frontend())

    assert "function chiudiMenuConfigurazione(" in testo, "il menu non sa chiudersi"
    assert "chiudiMenuConfigurazione();" in _funzione_javascript(
        testo, "switchTab"
    ), "scegliendo una voce il menu resta aperto sopra la schermata scelta"
    assert "evento.key === 'Escape'" in testo, "Esc non chiude il menu"
    assert "menu.contains(evento.target)" in testo, "un clic fuori non chiude il menu"
    # Senza `stopPropagation`, il clic sul pulsante arriva anche al guardiano
    # del clic-fuori e il menu si chiude nello stesso istante in cui si apre.
    assert "evento.stopPropagation()" in _funzione_javascript(
        testo, "alternaMenuConfigurazione"
    ), "il menu si richiude da solo nell'istante in cui si apre"


def test_nessuna_etichetta_e_diventata_un_indovinello():
    """«Non togliere le scritte per fare posto alle icone».

    Un'icona senza etichetta e' un indovinello che si ripresenta ogni volta:
    si risparmia larghezza e si perde la mappa. Ogni ingresso di primo
    livello, su computer, porta delle parole.
    """
    barra = _senza_commenti_html(_barra_desktop(_frontend()))

    muti = []
    for pulsante in re.findall(r'<button[^>]*id="tab-btn-\w+".*?</button>', barra, re.S):
        nome = re.search(r'id="tab-btn-(\w+)"', pulsante).group(1)
        # Il testo del pulsante: tutto cio' che non e' un tag.
        parole = re.sub(r"<[^>]+>", " ", pulsante).strip()
        if len(parole) < 3:
            muti.append(nome)

    assert muti == [], f"questi ingressi sono solo un'icona: {muti}"


def test_la_barra_non_taglia_il_menu_di_configurazione():
    """Il menu si apriva e si vedeva una fetta alta tre righe, con le frecce
    di una barra di scorrimento a lato.

    `overflow-x-auto` sulla barra serviva a far scorrere otto schede quando
    non ci stavano. Con quattro non serve, e un contenitore che scorre
    **ritaglia tutto cio' che gli esce dai bordi**, menu a tendina compresi:
    il menu non era posizionato male, era chiuso dentro.

    E' lo stesso difetto della X dell'editor sigillata dentro
    `overflow-hidden` (#122), ricomparso dall'altra parte della pagina e
    scoperto nello stesso modo — guardando la schermata, non il codice.
    Questa guardia esiste perche' la terza volta non succeda.
    """
    barra = _senza_commenti_html(_barra_desktop(_frontend()))

    contenitore = re.search(r'<div class="([^"]*)"', barra).group(1)

    assert "overflow" not in contenitore, (
        f"la barra ritaglia cio' che le esce dai bordi, e il menu di "
        f"configurazione le esce dai bordi: {contenitore}"
    )
    # Se la riga non ci sta, deve andare a capo: l'alternativa a scorrere non
    # e' lasciare che l'ultimo ingresso finisca fuori schermo.
    assert "flex-wrap" in contenitore, "senza scorrimento e senza andare a capo, la riga si tronca"

    # E il menu deve stare davvero li' dentro: se qualcuno lo spostasse fuori
    # dalla barra, questa guardia guarderebbe il contenitore sbagliato.
    assert 'id="menu-configurazione"' in barra, "il menu non e' piu' dentro la barra"
