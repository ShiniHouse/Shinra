"""La schermata delle automazioni e la scorciatoia per le regole.

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
    _senza_commenti,
    _senza_commenti_html,
)

# ------------------------------------------- la schermata delle automazioni


def test_le_automazioni_hanno_una_schermata():
    """Il motore delle regole e' esistito per due versioni senza nessuna
    schermata: l'API c'era, la dashboard no.

    Non era un dettaglio estetico. Una casa che agisce da sola e non sa dire
    perche' e' una casa che si spegne, e finche' le regole non si vedevano
    l'unico modo di chiedere «perche' non e' successo niente?» era leggere i
    log del server.

    Dalla #128 la scheda si chiama «Automazioni e routine» e contiene anche
    il costruttore a nodi: sono la stessa cosa vista da due lati. Quello che
    questa guardia difende non cambia — che la schermata esista, che ci si
    arrivi da computer e da telefono, e che aprendola si carichi qualcosa.
    """
    testo = _frontend()

    assert 'id="tab-automazioni"' in testo, "la scheda non esiste"
    assert _gesto("switchTab", "automazioni") in testo, "non ci si arriva dalla navigazione"
    assert _gesto("switchTabMobile", "automazioni") in testo, "dal telefono non ci si arriva"
    # Il **ramo**, non la riga esatta: fissare la riga vuol dire che chiunque
    # aggiunga un terzo pezzo alla scheda deve toccare questa guardia, e una
    # guardia che si tocca a ogni aggiunta smette di dire qualcosa.
    ramo = re.search(r"if \(tabId === 'automazioni'\)\s*\{([^}]*)\}", _senza_commenti(testo))
    assert ramo, "aprendola non carica niente"
    for carico in ("loadRegole()", "loadModes()"):
        assert carico in ramo.group(1), f"aprendola non chiama {carico}: mezza schermata resta vuota"
    # La chiave, comunque sia scritta: Prettier toglie gli apici a quelle che
    # non ne hanno bisogno, e la guardia non deve avere un'opinione in merito.
    assert re.search(
        r"['\"]?automazioni['\"]?\s*:\s*['\"]block['\"]", testo
    ), "la scheda non comparirebbe mai"
    assert 'id="regole-lista"' in testo, "l'elenco delle automazioni non c'e' piu'"


def test_una_regola_dice_quando_scattera_la_prossima_volta():
    """E' la domanda con cui si arriva a questa schermata, sempre: «e allora
    perche' non e' successo niente?»."""
    testo = _frontend()

    corpo = testo[testo.index("function quandoScatta") : testo.index("function renderRegole")]

    # Il **ramo**, non il nome della variabile. Cercare `regola.prossimo` e
    # basta lasciava passare un `if (false)` con la lettura ancora li' dentro:
    # e' la stessa guardia debole gia' vista con `illuminaNodiInErrore`.
    assert "if (regola.prossimo) {" in corpo, "il prossimo scatto non viene mai mostrato"
    assert "non scatterà" in corpo, "una regola che non scattera' mai non lo dice"


def test_aspettare_un_evento_non_si_confonde_con_non_scattare_mai():
    """Tre stati che una schermata ingenua fa diventare uno.

    Una regola su evento senza prossimo scatto sta benissimo: aspetta. Una
    regola all'alba senza prossimo scatto e' il difetto che le ha tenute ferme
    per due versioni. Mostrarle uguali vorrebbe dire nascondere di nuovo
    quello che questa schermata esiste per far vedere.
    """
    testo = _frontend()

    corpo = testo[testo.index("function quandoScatta") : testo.index("function renderRegole")]

    assert "regola.aspetta_un_evento" in corpo, "le due si leggerebbero uguali"


def test_una_regola_si_puo_zittire_senza_cancellarla():
    testo = _frontend()

    # Si guarda che il gesto esista e che porti lo stato rovesciato, non
    # come e' scritto il resto dell'elenco degli argomenti.
    assert re.search(
        r'data-gesto="alternaRegola" data-args="\$\{_args\(.*?,\s*!r\.attiva\)\}"', testo
    ), "non si puo' zittire una regola"
    assert "'/api/regole/${id}'" in testo.replace("`", "'"), "lo stato non torna al server"


def test_di_una_regola_generata_non_si_offre_la_cancellazione():
    """Cancellarla non servirebbe a niente: risalvando la routine tornerebbe
    identica. Offrire un pulsante che non ottiene quello che promette e'
    peggio che non offrirlo."""
    testo = _frontend()

    corpo = testo[testo.index("function renderRegole") : testo.index("async function alternaRegola")]

    assert (
        "const dalGrafo = String(r.origine || '').startsWith('grafo:')" in corpo
    ), "non si distingue una regola generata da una scritta a mano"
    # Il ternario dei pulsanti, non quello dell'etichetta: e' quello scritto
    # su piu' righe. Il ramo vero comincia per `?`, il falso per `:`.
    # Prettier rientra la condizione sulla riga dopo `${`, quindi si cerca
    # l'apertura e poi la prima riga che porta `dalGrafo` da sola.
    scelta = corpo[re.search(r"\$\{\s*\n\s*dalGrafo\b", corpo).start() :]
    righe = scelta[: scelta.index("</div>")].splitlines()
    ramo_generata = next(r for r in righe if r.strip().startswith("?"))
    ramo_a_mano = next(r for r in righe if r.strip().startswith(":"))

    assert "cancellaRegola" not in ramo_generata, "si offre di cancellare una regola che tornerebbe"
    assert "cancellaRegola" in ramo_a_mano, "una regola scritta a mano non si puo' piu' cancellare"
    # `_grezzo(` finisce sulla riga del `?`, e la frase su quella dopo: si
    # guarda il ramo intero, che e' quello che il lettore vede.
    assert "togli l\\'innesco" in scelta[: scelta.index("</div>")], "non si dice come toglierla davvero"


def test_la_prova_di_una_regola_dice_perche_non_e_scattata():
    """«Prova» esegue saltando l'innesco **ma non le condizioni**: serve
    proprio a rispondere a «perche' non scatta?», e una prova che ignorasse
    anche le condizioni risponderebbe sempre di si'."""
    testo = _frontend()

    corpo = testo[testo.index("async function provaRegola") : testo.index("async function cancellaRegola")]

    # Anche qui il ramo, non il nome: `} else if (false) {` lasciava
    # `esito.motivo` scritto nella riga sotto, e la guardia restava verde.
    assert "} else if (esito.motivo) {" in corpo, "il motivo del rifiuto non viene mai mostrato"
    assert "/prova" in corpo


def test_senza_automazioni_la_schermata_dice_come_farne_una():
    """Un elenco vuoto e basta lascia chi guarda esattamente dov'era."""
    testo = _frontend()

    corpo = testo[testo.index("function renderRegole") : testo.index("async function alternaRegola")]

    assert "if (!regole.length)" in corpo, "nessuno stato vuoto"
    assert "innesco" in corpo, "lo stato vuoto non dice da dove nascono le automazioni"


# --------------------------------------- la scorciatoia per le regole (#126)


def _corpo_della_scorciatoia(campi: dict) -> dict:
    """Il corpo che il modulo manderebbe, costruito dalle **sue** funzioni.

    Riscriverlo qui a mano proverebbe la mia idea di cosa manda, non cio' che
    manda. E' la differenza fra un test e una ripetizione.
    """
    testo = _frontend()

    sorgente = (
        "const campi = "
        + json.dumps({k: {"value": v} for k, v in campi.items()})
        + ";\nconst document = { getElementById: (id) => campi[id] || null };\n"
        + _funzione_javascript(testo, "inniescoDallaScorciatoia")
        + "\n"
        + _funzione_javascript(testo, "_azioneDallaScorciatoia")
        + "\n"
        + _funzione_javascript(testo, "nomeDallaScorciatoia")
        + """
const innesco = inniescoDallaScorciatoia();
const azione = _azioneDallaScorciatoia();
console.log(JSON.stringify({
    nome: nomeDallaScorciatoia(innesco, azione),
    trigger: innesco,
    condizioni: [],
    azioni: [azione]
}));
"""
    )

    esito = _esegui_con_node(sorgente)
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout.strip())


def test_alle_23_spegni_tutto_si_crea_senza_aprire_l_editor(cliente_autenticato):
    """Il primo criterio della scheda, provato fino in fondo.

    Non «il modulo esiste»: il corpo che il modulo manda viene costruito
    eseguendo le sue funzioni, spedito alla rotta vera, e poi si guarda se la
    regola c'e' e **quando scattera'**. Una regola che nasce e non ha un
    prossimo scatto e' una regola che non scattera' mai, ed e' il difetto che
    ha tenuto ferme le regole del sole per due versioni.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    corpo = _corpo_della_scorciatoia(
        {
            "scorciatoia-quando": "orario",
            "scorciatoia-ora": "23:00",
            "scorciatoia-cosa": "dispositivo",
            "scorciatoia-dispositivo": "light.salotto",
            "scorciatoia-servizio": "turn_off",
        }
    )

    risposta = cliente_autenticato.post("/api/regole", json=corpo)
    assert risposta.status_code == 200, risposta.text

    elenco = cliente_autenticato.get("/api/regole").json()["regole"]
    nate = [r for r in elenco if r["nome"] == corpo["nome"]]

    assert nate, f"la regola non compare nell'elenco: {[r['nome'] for r in elenco]}"
    regola = nate[0]
    assert regola["prossimo"], "nata senza un prossimo scatto: non scattera' mai"
    assert regola["prossimo"].endswith("23:00:00"), f"scatterebbe alle {regola['prossimo']}, non alle 23"
    # E deve spegnere **quella** luce. Un'azione che non dice su cosa agire
    # scatta, riesce e non fa niente: e' il modo piu' silenzioso di avere
    # un'automazione finta, ed e' quello che questa guardia non vedeva finche'
    # una mutazione non le ha svuotato l'entita' sotto il naso.
    assert regola["azioni"] == [
        {"tipo": "dispositivo", "entity_id": "light.salotto", "servizio": "turn_off"}
    ], regola["azioni"]
    # Indistinguibile dalle altre: stessa riga, stessa prova, stesso elenco.
    assert regola["descrizione"], "senza descrizione, nell'elenco e' una riga muta"


def test_il_nome_della_scorciatoia_dice_cosa_fa():
    """«Nuova regola 3» costringe ad aprirla per ricordarsi cos'era."""
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    corpo = _corpo_della_scorciatoia(
        {
            "scorciatoia-quando": "tramonto",
            "scorciatoia-scarto": "-15",
            "scorciatoia-cosa": "modalita",
            "scorciatoia-modalita": "Buonanotte",
        }
    )

    assert "tramonto" in corpo["nome"].lower(), corpo["nome"]
    assert "Buonanotte" in corpo["nome"], corpo["nome"]
    assert corpo["trigger"] == {"tipo": "tramonto", "scarto_minuti": -15}


def test_il_rifiuto_del_server_si_legge_nella_schermata(cliente_autenticato):
    """La rotta sa gia' dire perche' no, e lo dice meglio di qualunque
    controllo riscritto nella pagina.

    Due cose insieme: che il server rifiuti davvero cio' che non potrebbe
    scattare, e che la pagina abbia dove scriverlo — un riquadro, non un
    `alert`, che si chiude senza lasciare traccia di cosa non andava.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    corpo = _corpo_della_scorciatoia(
        {
            "scorciatoia-quando": "stato",
            "scorciatoia-cosa": "avviso",
            "scorciatoia-testo": "occhio",
        }
    )
    # Un trigger su stato senza entita': il server lo sa, la pagina no.
    rifiuto = cliente_autenticato.post("/api/regole", json=corpo)

    assert rifiuto.status_code == 400, rifiuto.text
    assert "entita" in rifiuto.json()["detail"].lower()

    pagina = _senza_commenti_html(_frontend())
    assert 'id="scorciatoia-esito"' in pagina, "il rifiuto non ha dove farsi leggere"

    corpo_js = _senza_commenti(_funzione_javascript(_frontend(), "creaScorciatoia"))
    assert "_mostraEsitoScorciatoia" in corpo_js, "il rifiuto non viene mostrato"
    assert "alert(" not in corpo_js, "il rifiuto finisce in un avviso di sistema"
    assert "dati.detail" in corpo_js, "viene mostrato un messaggio inventato qui, non il motivo del server"


def test_passare_all_editor_non_perde_quello_che_hai_scritto():
    """«Serve qualcosa di piu' complicato?» non deve voler dire «ricomincia».

    Chi ha gia' scelto «al tramonto» e scopre di aver bisogno di una
    condizione non deve ritrovarsi una tela vuota: sarebbe la ragione per cui
    nessuno userebbe piu' la scorciatoia.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    testo = _frontend()

    prova = (
        """
const campi = {
    'scorciatoia-quando': { value: 'tramonto' },
    'scorciatoia-scarto': { value: '30' },
    'scorciatoia-nome': { value: 'Sera in giardino' }
};
const document = { getElementById: (id) => campi[id] || null };
// La tela **non** si sostituisce con un oggetto scritto qui: si usa quella
// vera, che `_esegui_con_node` porta dentro insieme al contenitore. Una
// copia locale resterebbe giusta anche il giorno che `Stato.tela` nasce
// `null` — e quel giorno l'editor non si aprirebbe piu' in casa, con questo
// test verde.
function openModularModeBuilder() {
    Stato.tela.name = 'Nuova Routine';
    Stato.tela.nodes = [
        { id: 'node_trig', type: 'trigger', data: { phrases: ['modalita relax'] } },
        { id: 'node_ha1', type: 'ha_device', data: {} }
    ];
}
function renderFlowCanvasModal() {}
"""
        + _funzione_javascript(testo, "inniescoDallaScorciatoia")
        + "\n"
        + _funzione_javascript(testo, "apriEditorDallaScorciatoia")
        + """
apriEditorDallaScorciatoia();
const nodo = Stato.tela.nodes.find(n => n.type === 'trigger');
console.log(JSON.stringify({ innesco: nodo.data.trigger, nome: Stato.tela.name }));
"""
    )

    esito = _esegui_con_node(prova)

    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert visto["innesco"] == {
        "tipo": "tramonto",
        "scarto_minuti": 30,
    }, f"l'editor si apre con {visto['innesco']}: quello che avevi scelto e' andato perso"
    assert visto["nome"] == "Sera in giardino", "anche il nome e' andato perso"


def test_la_scorciatoia_non_ha_tolto_niente_all_editor():
    """Il vincolo della scheda, e l'unico messo per iscritto dal proprietario
    della casa: *«l'editor delle automazioni rimane»*.

    Questa e' una porta in piu' sulla stessa stanza. Una guardia che
    guardasse solo il modulo nuovo sarebbe verde anche il giorno che qualcuno
    decide che adesso la scorciatoia basta.
    """
    testo = _frontend()
    scheda = _senza_commenti_html(
        testo[testo.index('<div id="tab-automazioni"') : testo.index('<div id="tab-users"')]
    )

    assert _gesto("openModularModeBuilder") in scheda, "l'editor non si apre piu' da questa scheda"
    assert 'id="modes-list"' in scheda, "l'elenco delle routine e' sparito"
    assert 'id="scorciatoia"' in scheda, "la scorciatoia non e' qui"

    # E i pezzi dell'editor sono tutti al loro posto: rami, condizioni,
    # ritardi e sequenze non si esprimono in un modulo.
    for tipo in ("condizione", "delay", "tts"):
        pezzo = 'data-gesto="addCanvasNode" data-args="${_args(\'' + tipo + "')}\""
        assert pezzo in testo, f"l'editor ha perso un pezzo: {tipo}"
