"""La dashboard e' un file solo, e nessuno la guardava.

`web/templates/index.html` porta quasi cinquemila righe, di cui la gran parte
JavaScript scritto dentro un tag `<script>`. Non passa da nessun compilatore,
da nessun linter e da nessun test: un apostrofo di troppo dentro una stringa
— «puo' solo chiedere» — spegne l'intera pagina, e il server continua a
rispondere 200 come se niente fosse. E' successo mentre si scriveva questa
stessa schermata.

Questi test non provano il comportamento: per quello servirebbe un browser.
Provano le tre cose che si rompono davvero e in silenzio — la sintassi, gli
identificativi cercati e non trovati, le chiamate a rotte che non esistono —
piu' due guardie sulle scelte di questa versione.

Riferimento: issue #46 e #47.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent
PAGINA = RADICE / "web" / "templates" / "index.html"
ACCESSO = RADICE / "web" / "templates" / "accesso.html"
# Dalla #34 il foglio di stile e il copione stanno in file propri, uno per
# area. Le guardie non ne conoscono i nomi a memoria: li leggono dalla
# cartella, cosi' un pezzo nuovo entra nelle guardie il giorno che nasce
# invece del giorno che qualcuno si ricorda di aggiungerlo qui.
CARTELLA_CSS = RADICE / "web" / "static" / "css"
CARTELLA_JS = RADICE / "web" / "static" / "js"


def _fogli() -> list[Path]:
    return sorted(CARTELLA_CSS.glob("*.css"))


def _copioni() -> list[Path]:
    return sorted(CARTELLA_JS.glob("*.js"))


def _testo(percorso: Path) -> str:
    return percorso.read_text(encoding="utf-8")


def _senza_commenti(testo: str) -> str:
    """Il codice senza i commenti che lo spiegano.

    Serve a ogni guardia che cerca una stringa nel **codice**: un commento che
    spiega perche' una riga esiste contiene quasi sempre le parole di quella
    riga, e una guardia che le trova li' resta verde anche con la riga tolta.
    E' successo quattro volte in questo file — `illuminaNodiInErrore`,
    `overflow-hidden`, e due volte una frase di un messaggio — sempre allo
    stesso modo e sempre con lo stesso stupore.
    """
    return re.sub(r"//[^\n]*", "", testo)


def _senza_commenti_html(testo: str) -> str:
    """Lo stesso principio del precedente, per il markup.

    Un commento che spiega perche' un pulsante e' li' nomina il pulsante: una
    guardia che conta gli ingressi contando le occorrenze di `tab-btn-` ne
    troverebbe uno in piu' per ogni riga di spiegazione.
    """
    return re.sub(r"<!--.*?-->", "", testo, flags=re.S)


def _frontend() -> str:
    """Markup, foglio di stile e copione insieme.

    Dalla #34 vivono in file separati, uno per area. Una guardia che chiede
    «questa cosa esiste nel frontend?» guarda qui; una che dice **dove** deve
    stare guarda i file precisi — `_testo(PAGINA)` per il markup, `_stile()`
    per i colori, `_comportamento()` per il codice.
    """
    return "\n".join(_testo(p) for p in [PAGINA, *_fogli(), *_copioni()])


def _stile() -> str:
    """I fogli di stile, tutti insieme. Erano dentro la pagina fino alla #34."""
    foglio = "\n".join(_testo(p) for p in _fogli())
    assert len(foglio) > 5000, "il foglio di stile e' quasi vuoto: il test non guarda piu' niente"
    return foglio


def _comportamento() -> str:
    """I copioni, tutti insieme. Erano dentro la pagina fino alla #34."""
    copione = "\n".join(_testo(p) for p in _copioni())
    assert len(copione) > 50000, "il copione e' quasi vuoto: il test non guarda piu' niente"
    return copione


def _script_inline(testo: str) -> list[str]:
    """Solo gli script scritti nella pagina: quelli con `src` non sono nostri."""
    return re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", testo, re.S)


# ------------------------------------------------------------------ sintassi


def test_il_copione_e_sintatticamente_valido():
    """Le cinquemila righe che la #34 ha portato fuori dalla pagina.

    Finche' stavano dentro `index.html` le copriva
    `test_gli_script_inline_sono_sintatticamente_validi`. Spostandole, quella
    guardia ha smesso di vederle: un errore di sintassi li' dentro non da' un
    500, da' una pagina morta — niente schede, niente console, niente — e il
    server continua a rispondere 200.

    Ogni pezzo va controllato da solo: il browser li carica come copioni
    separati, quindi uno rotto ferma se stesso e basta — gli altri girano, e
    la dashboard resta viva a meta'. E' un guasto peggiore di una pagina
    morta, perche' sembra funzionare.

    Riferimento: issue #34.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    copioni = _copioni()
    assert len(copioni) > 10, f"copioni trovati: {[p.name for p in copioni]}"

    for percorso in copioni:
        esito = subprocess.run(
            ["node", "--check", str(percorso)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert esito.returncode == 0, f"{percorso.name} non si compila:\n{esito.stderr}"


@pytest.mark.parametrize("percorso", [PAGINA, ACCESSO], ids=lambda p: p.name)
def test_gli_script_inline_sono_sintatticamente_validi(percorso: Path):
    """Un errore di sintassi qui non da' un 500: da' una pagina morta.

    Il browser smette di eseguire lo script al primo errore, quindi non parte
    nulla — niente tab, niente console, niente. Il server intanto risponde
    200 e i test di backend restano tutti verdi.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    blocchi = _script_inline(_testo(percorso))
    assert blocchi, f"{percorso.name} non ha script inline: il test non guarda piu' niente"

    for numero, blocco in enumerate(blocchi):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(blocco)
            temporaneo = file.name
        try:
            esito = subprocess.run(
                ["node", "--check", temporaneo],
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            Path(temporaneo).unlink(missing_ok=True)
        assert (
            esito.returncode == 0
        ), f"script inline #{numero} di {percorso.name} non compila:\n{esito.stderr}"


# ------------------------------------------------------------ identificativi


def test_ogni_identificativo_cercato_dal_javascript_esiste():
    """`getElementById` di un identificativo che non c'e' restituisce `null`.

    Non solleva: la riga dopo fallisce, oppure — peggio — il codice e'
    difensivo (`if (el)`) e la funzione non fa semplicemente niente. E' cosi'
    che il pulsante «Blocca» e' rimasto assente per intere versioni mentre
    `checkAuthStatus` lo cercava a ogni caricamento.
    """
    testo = _frontend()
    cercati = set(re.findall(r"getElementById\(\s*['\"]([A-Za-z0-9_-]+)['\"]", testo))
    # Nella pagina, oppure creato a mano dal JavaScript con `.id = '...'`.
    esistenti = set(re.findall(r'\bid="([A-Za-z0-9_-]+)"', testo)) | set(
        re.findall(r"\.id\s*=\s*['\"]([A-Za-z0-9_-]+)['\"]", testo)
    )

    assert cercati, "nessun getElementById trovato: il test non guarda piu' niente"
    assert sorted(cercati - esistenti) == []


# ------------------------------------------------------------------- chiamate


def test_ogni_chiamata_api_della_pagina_corrisponde_a_una_rotta():
    """Una `fetch` su una rotta inesistente e' un 404 silenzioso.

    Il codice di questa pagina, quasi ovunque, non guarda `res.ok`: legge il
    corpo, non trova niente e lascia la sezione vuota. Sembra «non ci sono
    dati», non «ho sbagliato indirizzo». Rinominare una rotta lato server
    senza toccare la pagina si nota solo aprendola.
    """
    from shinra.api.app import app
    from tests.unit.test_autenticazione import rotte_api

    def normalizza(percorso: str) -> str:
        # `${qualcosa}` nel JavaScript e `{qualcosa}` in FastAPI sono la stessa
        # cosa: un parametro. Si confrontano le forme, non i valori.
        percorso = re.sub(r"\$\{[^}]*\}", "{x}", percorso)
        return percorso.split("?")[0].rstrip("/") or "/"

    chiamate = {normalizza(g) for g in re.findall(r"fetch\(\s*[`'\"](/api/[^`'\"]*)[`'\"]", _frontend())}
    rotte = {re.sub(r"\{[^}]*\}", "{x}", r.path).rstrip("/") or "/" for r in rotte_api(app)}

    assert chiamate, "nessuna chiamata trovata: il test non guarda piu' niente"
    assert sorted(c for c in chiamate if c not in rotte) == []


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

    assert "onPinMouseDown('${node.id}', event, 'vero')" in testo
    assert "onPinMouseDown('${node.id}', event, 'falso')" in testo
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
    assert "getTracks().forEach(t => t.stop())" in corpo, "il flusso del microfono non viene chiuso"


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

    assert "setTipoInnesco('${node.id}', this.value)" in testo, "non si puo' cambiare tipo di innesco"
    for tipo in ("orario", "alba", "tramonto", "stato", "evento"):
        assert f'value="{tipo}"' in testo, f"manca l'innesco «{tipo}» fra le scelte"


def test_cambiare_tipo_di_innesco_riparte_da_zero():
    """I campi di un innesco a orario non valgono per uno su soglia: lasciarli
    in giro produce una regola che porta dietro dati che nessuno legge."""
    testo = _frontend()

    corpo = testo[testo.index("function setTipoInnesco") : testo.index("function setDatoInnesco")]

    assert "node.data.trigger = predefiniti[tipo]" in corpo, "i campi del tipo precedente restano li'"


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
    assert "switchTab('automazioni')" in testo, "non ci si arriva dalla navigazione"
    assert "switchTabMobile('automazioni')" in testo, "dal telefono non ci si arriva"
    # Il **ramo**, non la riga esatta: fissare la riga vuol dire che chiunque
    # aggiunga un terzo pezzo alla scheda deve toccare questa guardia, e una
    # guardia che si tocca a ogni aggiunta smette di dire qualcosa.
    ramo = re.search(r"if \(tabId === 'automazioni'\)\s*\{([^}]*)\}", _senza_commenti(testo))
    assert ramo, "aprendola non carica niente"
    for carico in ("loadRegole()", "loadModes()"):
        assert carico in ramo.group(1), f"aprendola non chiama {carico}: mezza schermata resta vuota"
    assert "'automazioni': 'block'," in testo, "la scheda non comparirebbe mai"
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

    assert "alternaRegola('${r.id}', ${!r.attiva})" in testo, "non si puo' zittire una regola"
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
    scelta = corpo[corpo.index("${dalGrafo\n") :]
    righe = scelta[: scelta.index("</div>")].splitlines()
    ramo_generata = next(r for r in righe if r.strip().startswith("?"))
    ramo_a_mano = next(r for r in righe if r.strip().startswith(":"))

    assert "cancellaRegola" not in ramo_generata, "si offre di cancellare una regola che tornerebbe"
    assert "cancellaRegola" in ramo_a_mano, "una regola scritta a mano non si puo' piu' cancellare"
    assert "togli l\\'innesco" in ramo_generata, "non si dice come toglierla davvero"


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
    assert "scegliStanza(this.value)" in testo, "la scelta non viene salvata"
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
    assert "} catch (e) {" in corpo, "un errore della memoria del sito non viene raccolto"
    assert "return null;" in corpo, "senza memoria non si resta un dispositivo senza stanza"


def test_le_stanze_suggerite_vengono_dagli_alias():
    """Un secondo elenco di stanze divergerebbe dal primo, e «Cucina» contro
    «cucina » sono due stanze che non si incontreranno mai."""
    testo = _frontend()

    corpo = testo[testo.index("async function riempiStanzeNote") :][:900]

    assert "'/api/aliases'" in corpo, "le stanze suggerite non vengono dai dispositivi"
    assert "a.room" in corpo


# ------------------------------------------------- caricamenti e messaggi


def _funzione_javascript(testo: str, nome: str) -> str:
    """La funzione, dalla firma alla sua parentesi.

    Le funzioni del copione stanno a margine: la prima riga fatta di una sola
    parentesi chiusa e' la fine della funzione. Fino alla #34 stavano a otto
    spazi, perche' erano annidate dentro il `<script>` della pagina.

    Serve per darla a `node` ed eseguirla davvero, invece di cercare stringhe
    dentro al sorgente — che e' il modo in cui una guardia resta verde su una
    riga svuotata.
    """
    apertura = testo.index(f"function {nome}(")
    resto = testo[apertura:]
    chiusura = resto.index("\n}\n")
    return resto[: chiusura + len("\n}")]


def test_una_fetch_con_un_modulo_non_si_porta_dietro_un_content_type_json():
    """Il difetto per cui il microfono non ha mai trascritto niente.

    Un corpo `FormData` porta con se' il proprio Content-Type, e dentro c'e'
    il «boundary»: la stringa, inventata dal browser al momento dell'invio,
    che separa i pezzi del caricamento. `getAuthHeaders()` ci scriveva sopra
    `application/json`: il corpo restava multipart, ma l'etichetta diceva
    altro, e il server rispondeva 422.

    Nessun test poteva vederlo: la rotta era giusta, il suo test passava, e
    in casa non succedeva niente. La guardia sta qui perche' l'errore e' una
    riga che sembra giusta — `headers: getAuthHeaders()`, come tutte le altre
    fetch della pagina.
    """
    testo = _frontend()

    moduli = set(re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*new FormData\(", testo))
    assert moduli, "nessun FormData nella pagina: il test non guarda piu' niente"

    colpevoli = []
    for posizione in (m.start() for m in re.finditer(r"\bfetch\(", testo)):
        chiamata = testo[posizione : posizione + 400]
        if not any(re.search(rf"body:\s*{nome}\b", chiamata) for nome in moduli):
            continue
        if "getAuthHeaders(" in chiamata:
            colpevoli.append(chiamata.splitlines()[0].strip())

    assert colpevoli == [], (
        "una fetch manda un FormData con le intestazioni di sempre, "
        f"e fra quelle c'e' Content-Type: application/json — {colpevoli}"
    )


ROTTE_PRIMA_DELLA_SESSIONE = ("/api/auth/profili", "/api/auth/login")


def test_ogni_chiamata_all_api_porta_le_intestazioni_di_autenticazione():
    """Ventisette chiamate su settantatre partivano senza.

    Funzionavano lo stesso, ed e' questo che le ha nascoste: il browser di
    casa e' un dispositivo fidato, e `sessione_dalla_richiesta` ha una seconda
    strada che passa dal cookie. Su un browser non ancora fidato — il telefono
    di un ospite, una finestra anonima, la PWA appena installata — le stesse
    rotte rispondono 401.

    E il 401 non si vedeva: `dati.regole || []` trasforma un rifiuto in un
    elenco vuoto, e la schermata dice «non c'e' niente» invece di «non ho il
    permesso di vederlo».

    Le due eccezioni sono dichiarate per nome e non per comodita': si chiamano
    **prima** di avere una sessione, quindi un'intestazione di autenticazione
    li' non esiste ancora.

    Riferimento: issue #125.
    """
    testo = _frontend()

    colpevoli = []
    for m in re.finditer(r"fetch\(\s*[`'\"](/api/[^`'\"]*)", testo):
        if m.group(1) in ROTTE_PRIMA_DELLA_SESSIONE:
            continue
        chiamata = testo[m.start() : m.start() + 420]
        if "getAuthHeaders(" in chiamata or "intestazioniPerModulo(" in chiamata:
            continue
        colpevoli.append(f"riga {testo[: m.start()].count(chr(10)) + 1}: {m.group(1)}")

    assert colpevoli == [], (
        "queste chiamate partono senza intestazioni: funzionano solo da un "
        f"dispositivo gia' fidato — {colpevoli}"
    )


def test_un_rifiuto_dell_api_si_vede_invece_di_diventare_un_elenco_vuoto():
    """Il controllo sta attorno a `fetch`, una volta sola.

    Metterlo in ogni chiamata vorrebbe dire poterselo dimenticare alla
    prossima — ed e' la stessa ragione per cui il contesto del registro sta in
    un middleware e non nelle singole rotte.

    Le rotte di accesso restano fuori: un 401 su `/api/auth/login` vuol dire
    «PIN sbagliato», e chi sta entrando lo sta gia' leggendo sotto la tastiera.
    """
    testo = _frontend()

    apertura = testo.index("function sorvegliaIRifiuti()")
    corpo = testo[apertura : testo.index("function mostraRifiuto(")]
    corpo = re.sub(r"//[^\n]*", "", corpo)

    assert "window.fetch =" in corpo, "nessuno sorveglia le risposte"
    assert "401" in corpo and "403" in corpo, "il rifiuto non viene riconosciuto"
    assert "mostraRifiuto(" in corpo, "il rifiuto viene riconosciuto e non detto"
    assert (
        "'/api/auth/'" in corpo or '"/api/auth/"' in corpo
    ), "anche un PIN sbagliato farebbe comparire l'avviso"


def test_l_avviso_dice_che_il_vuoto_potrebbe_non_essere_vuoto():
    """«Sessione scaduta» da solo non basta.

    Chi legge un errore di sessione non collega da se' che l'elenco vuoto che
    ha sotto gli occhi potrebbe essere pieno. E' quella frase — non
    l'avviso — a chiudere la issue.
    """
    testo = _frontend()

    corpo = testo[testo.index("function mostraRifiuto(") : testo.index("function nascondiRifiuto(")]
    # I commenti si tolgono prima di guardare. E' la quarta volta in questo
    # file che una guardia trova nel commento la parola che cercava nel
    # codice, e resta verde con il codice svuotato: qui il commento spiega
    # **proprio** quella frase, quindi la conteneva.
    corpo = _senza_commenti(corpo)

    assert "vuote potrebbero non esserlo" in corpo, "l'avviso non dice cosa comporta"
    assert "riservato" in corpo, "un 403 viene raccontato come una sessione scaduta"


# Gli elenchi che possono restare vuoti **senza** doverlo dire, e perche'.
# Ognuno e' una scelta, non una dimenticanza: e' il motivo per cui stanno
# qui con un nome e una riga di spiegazione invece di essere saltati in
# silenzio dall'espressione regolare.
ELENCHI_CHE_POSSONO_TACERE = {
    "riempiStanzeNote": "e' un <datalist>: vuoto e' invisibile per costruzione",
    "renderKnowledgeTemplates": "l'elenco e' una costante scritta nella pagina",
    "renderSourcesCatalog": "idem: il catalogo delle fonti e' fisso",
    "renderCanvasElements": "la tela dell'editor nasce vuota, e la barra in basso lo spiega",
    "loadUsers": "c'e' sempre almeno l'amministratore",
    "loadRuoli": "`assicura_ruoli_predefiniti` garantisce i ruoli a ogni avvio",
}


def test_ogni_elenco_che_puo_restare_vuoto_dice_qualcosa():
    """Una lista vuota che non insegna la mossa dopo sembra rotta.

    «Non c'e' niente» e «non ho capito come si fa» hanno lo stesso aspetto,
    ed e' la domanda da cui e' nata la issue #127.

    Questa guardia **non** ha trovato un difetto: quando e' stata scritta, i
    sette elenchi che potevano essere vuoti avevano gia' tutti la loro frase.
    Serve a non perderli — sono la cosa piu' facile da dimenticare scrivendo
    la schermata successiva, perche' chi la scrive ha i dati sotto gli occhi
    e il caso vuoto non lo vede mai.

    Le eccezioni stanno in un elenco con il loro motivo: un elenco costante o
    un `<datalist>` non ha un caso vuoto da raccontare.
    """
    testo = _frontend()

    muti = []
    funzioni = list(re.finditer(r"\n(?:async )?function (\w+)\(", testo))
    confini = [m.start() for m in funzioni] + [len(testo)]
    for m, fine in zip(funzioni, confini[1:], strict=True):
        nome = m.group(1)
        corpo = _senza_commenti(testo[m.start() : fine])
        rende = re.search(r"innerHTML\s*\+?=\s*[^;]{0,160}\.map\(|push\([^;]{0,80}\.map\(", corpo, re.S)
        if not rende:
            continue
        if nome in ELENCHI_CHE_POSSONO_TACERE:
            continue
        # Il controllo va cercato **prima** del disegno, non nella funzione
        # intera: `renderRegole` guarda anche `vocali.length`, ma dopo, e una
        # guardia che accetta un controllo qualsiasi resterebbe verde togliendo
        # proprio quello che serve.
        prima = corpo[: rende.start()]
        guarda_il_vuoto = re.search(
            r"\.length\s*(?:===?\s*0|>\s*0|&&|\))|!\s*\w+(?:\.\w+)*\.length|!\s*\w+\s*\|\|", prima
        )
        if not guarda_il_vuoto:
            muti.append(nome)

    assert muti == [], (
        "questi elenchi possono presentarsi come uno spazio bianco: dai loro "
        f"una frase, oppure dichiarali in ELENCHI_CHE_POSSONO_TACERE col motivo — {muti}"
    )


def test_le_eccezioni_agli_stati_vuoti_esistono_ancora():
    """Un'eccezione per una funzione che non c'e' piu' e' un permesso che
    resta aperto su un nome libero: il giorno che qualcuno lo riusa, la
    guardia tace senza che nessuno l'abbia deciso."""
    testo = _frontend()

    fantasmi = [nome for nome in ELENCHI_CHE_POSSONO_TACERE if f"function {nome}(" not in testo]

    assert fantasmi == [], f"eccezioni per funzioni che non esistono piu': {fantasmi}"


def test_le_routine_a_innesco_vocale_si_vedono_fra_le_automazioni():
    """La cosa che mancava davvero.

    Chi ha disegnato due routine e le guarda dalla schermata delle automazioni
    non vede niente, perche' una routine a innesco vocale non e' una regola.
    Ma lui l'ha disegnata, se la ricorda, e il vuoto gli dice che non ha fatto
    niente. Il vuoto aveva anche ragione — nessuna automazione c'era — e
    proprio per questo e' peggio: e' una risposta esatta alla domanda
    sbagliata.

    Riferimento: issue #127.
    """
    testo = _frontend()

    corpo = _senza_commenti(
        testo[testo.index("function routineSoloVocali(") : testo.index("async function alternaRegola(")]
    )

    assert "'grafo:'" in corpo, "non si distingue una routine che ha gia' generato una regola"
    assert "partono solo se le chiami" in corpo, "le routine vocali non vengono nominate"
    assert "cambia l'innesco" in corpo, "non si dice come farle partire da sole"

    # E la schermata deve chiederle davvero, altrimenti l'elenco resta vuoto
    # per sempre e la guardia sopra prova una funzione che nessuno chiama.
    caricamento = _senza_commenti(
        testo[testo.index("async function loadRegole()") : testo.index("function quandoScatta(")]
    )
    assert "'/api/modes'" in caricamento, "la schermata non chiede le routine al server"


def _esegui_con_node(sorgente: str) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
        file.write(sorgente)
        temporaneo = file.name
    try:
        return subprocess.run(["node", temporaneo], capture_output=True, text=True, check=False)
    finally:
        Path(temporaneo).unlink(missing_ok=True)


def test_un_rifiuto_a_piu_voci_si_legge_invece_di_stampare_object_object():
    """L'altra meta' dello stesso difetto: quello che si vedeva.

    Quando e' la validazione a dire di no, FastAPI non risponde con una frase
    ma con l'elenco dei campi che non tornano, e ogni voce e' un oggetto.
    Darlo ad `alert()` com'era stampa «[object Object]»: nessuna indicazione
    di cosa sia successo, ne' di dove guardare. E' quello che la casa ha
    visto per giorni a ogni pressione del microfono.

    Il test esegue davvero la funzione con `node` invece di cercare stringhe
    nel sorgente: una guardia scritta come «la parola loc compare nel file»
    resterebbe verde con la funzione svuotata.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")

    funzione = _funzione_javascript(_frontend(), "_testoDelDettaglio")

    prova = funzione + """
function esigi(condizione, messaggio) {
    if (!condizione) { console.error(messaggio); process.exit(1); }
}

const validazione = _testoDelDettaglio(
    [{ loc: ['body', 'audio'], msg: 'Field required', type: 'missing' }], 422);
esigi(!validazione.includes('[object Object]'), 'la lista si stampa ancora come [object Object]');
esigi(validazione.includes('Field required'), 'il motivo del rifiuto non si legge');
esigi(validazione.includes('body > audio'), 'non si capisce quale campo manca');
// Non basta che le parole ci siano: rovesciare il JSON grezzo dentro un
// alert le contiene tutte, ed e' comunque illeggibile.
esigi(!validazione.includes('{'), 'il rifiuto si mostra come JSON grezzo');

esigi(_testoDelDettaglio('il ruolo e\\' assegnato a Thomas', 409)
        === 'il ruolo e\\' assegnato a Thomas',
      'una spiegazione gia\\' scritta viene alterata');

const oggetto = _testoDelDettaglio({ errore: 'ignoto' }, 500);
esigi(!oggetto.includes('[object Object]'), 'un oggetto solo si stampa come [object Object]');

esigi(_testoDelDettaglio(undefined, 503) === 'Errore 503',
      'senza dettaglio non resta nemmeno il codice');
"""

    esito = _esegui_con_node(prova)
    assert esito.returncode == 0, esito.stderr or esito.stdout


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

    assert "closeModal()" in corpo, "l'editor non si puo' piu' chiudere"
    assert "-top-3.5 -right-3.5" in corpo, "la chiusura non e' nell'angolo, fuori dal riquadro"

    # E la fetta attorno a «Salva» non deve contenere anche la chiusura.
    intorno = corpo[corpo.index("saveCanvasMode()") :][:600]
    assert "closeModal()" not in intorno, "la X e' tornata in fila accanto a «Salva»"


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


# ------------------------------------------- la colonna della console (#123)


def _colonna_della_console(testo: str) -> str:
    """La colonna di destra della console vocale: un terzo della prima
    schermata che si apre, e l'unica parte della pagina che sta accesa
    davanti a chi abita la casa senza che l'abbia chiesta."""
    inizio = testo.index("<!-- Right: Activity Logs & Active Timers -->")
    return testo[inizio : testo.index('<div id="tab-knowledge"', inizio)]


def test_la_colonna_della_console_non_porta_piu_la_diagnostica():
    """Il nome del modello e la frase di Alexa non riguardano chi abita qui.

    Stavano accesi un terzo dello schermo, sulla schermata che si apre per
    prima, e non cambiano da un'ora all'altra: il modello si sceglie una
    volta, la frase di invocazione si legge una volta nella vita. Nessuna
    delle due sparisce — si leggono in Impostazioni, che e' dove si va
    quando si vogliono cambiare.
    """
    colonna = _colonna_della_console(_frontend())

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
        """
const contenitore = { innerHTML: '' };
const document = { getElementById: () => contenitore };
function _testoSicuro(t) { return String(t === undefined || t === null ? '' : t); }
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
console.log(JSON.stringify(contenitore.innerHTML));
disegnaProssimiScatti([{ nome: 'ZITTITA', attiva: false, prossimo: '2030-01-01T06:00:00' }]);
console.log(JSON.stringify(contenitore.innerHTML));
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
    colonna = re.sub(r"<!--.*?-->", "", _colonna_della_console(_frontend()), flags=re.S)

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
DIETRO_LA_CONFIGURAZIONE = ["knowledge", "sources", "users", "settings"]


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
        assert f"switchTab('{scheda}')" in menu, f"dal menu di configurazione non si arriva a {scheda}"


def test_dal_telefono_la_navigazione_e_una_sola():
    """Su telefono non c'e' spazio per un menu dentro un menu.

    Il cassetto resta un elenco solo, con le quattro di configurazione
    raggruppate sotto una riga che dice cosa sono — non una seconda
    navigazione scritta a parte.
    """
    cassetto = _senza_commenti_html(_cassetto_telefono(_frontend()))

    destinazioni = re.findall(r"switchTabMobile\('([a-z]+)'\)", cassetto)

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

    assert "openModularModeBuilder()" in scheda, "l'editor non si apre da questa scheda"
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


# ----------------------------------- Impostazioni a sezioni richiudibili (#124)


def _scheda_impostazioni(testo: str) -> str:
    inizio = testo.index('<div id="tab-settings"')
    return testo[inizio : testo.index("</main>", inizio)]


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
    scheda = _senza_commenti_html(_scheda_impostazioni(_frontend()))

    sezioni = re.findall(r'<details class="sezione-impostazioni" data-sezione="(\w+)"([^>]*)>', scheda)

    assert len(sezioni) >= 8, f"le sezioni sono {len(sezioni)}: la scheda non e' stata divisa"

    aperte = [nome for nome, resto in sezioni if "open" in resto]
    assert len(aperte) == 1, f"all'arrivo sono aperte {len(aperte)} sezioni: {aperte}"
    assert aperte[0] == sezioni[0][0], "l'unica aperta non e' la prima"


def test_ogni_sezione_dice_cosa_contiene_anche_da_chiusa():
    """Una sezione chiusa che non dice cosa c'e' dentro e' un cassetto senza
    etichetta: si aprono tutti finche' non salta fuori quello giusto, che e'
    esattamente cio' da cui si voleva uscire."""
    scheda = _senza_commenti_html(_scheda_impostazioni(_frontend()))

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
    scheda = _senza_commenti_html(_scheda_impostazioni(testo))

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
    scheda = _scheda_impostazioni(_frontend())

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
const _canvasState = { nodes: [], edges: [], name: '' };
function openModularModeBuilder() {
    _canvasState.name = 'Nuova Routine';
    _canvasState.nodes = [
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
const nodo = _canvasState.nodes.find(n => n.type === 'trigger');
console.log(JSON.stringify({ innesco: nodo.data.trigger, nome: _canvasState.name }));
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

    assert "openModularModeBuilder()" in scheda, "l'editor non si apre piu' da questa scheda"
    assert 'id="modes-list"' in scheda, "l'elenco delle routine e' sparito"
    assert 'id="scorciatoia"' in scheda, "la scorciatoia non e' qui"

    # E i pezzi dell'editor sono tutti al loro posto: rami, condizioni,
    # ritardi e sequenze non si esprimono in un modulo.
    for pezzo in ("addCanvasNode('condizione')", "addCanvasNode('delay')", "addCanvasNode('tts')"):
        assert pezzo in testo, f"l'editor ha perso un pezzo: {pezzo}"


# ------------------------------------------- i nomi delle icone (issue #139)

ICONE = RADICE / "tests" / "dati" / "icone-lucide.txt"


def _icone_valide() -> tuple[str, set[str]]:
    """La versione dichiarata e le chiavi delle icone, dall'elenco generato."""
    versione = ""
    nomi: set[str] = set()
    for riga in ICONE.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#"):
            continue
        if riga.startswith("versione:"):
            versione = riga.split(":", 1)[1].strip()
            continue
        nomi.add(riga)
    return versione, nomi


def _in_pascal(nome: str) -> str:
    """La stessa conversione che fa lucide, copiata dal suo bundle:

        t.replace(/(\\w)(\\w*)(_|-|\\s*)/g, (d, c, p) => c.toUpperCase() + p.toLowerCase())

    Cioe': ogni gruppo di caratteri di parola diventa Iniziale+resto minuscolo,
    e il separatore sparisce. Riprodurla — invece di inventare una conversione
    kebab «ragionevole» — e' l'unico modo perche' la guardia dica la stessa
    cosa che dira' il browser.
    """
    return re.sub(
        r"(\w)(\w*)(_|-|\s*)",
        lambda t: t.group(1).upper() + t.group(2).lower(),
        nome,
    )


def _nomi_di_icona_nella_pagina(testo: str) -> set[str]:
    """Ogni nome che puo' finire in `data-lucide`, anche quelli scelti a runtime.

    Un ternario dentro un'interpolazione — `${isDay ? 'sun-medium' : 'moon'}` —
    ne nasconde due, e sbagliarne uno si vede solo di notte.
    """
    nomi: set[str] = set()
    for valore in re.findall(r'data-lucide="([^"]*)"', testo):
        if "$" in valore or "{" in valore:
            # Le costanti dentro l'interpolazione: quelle si possono guardare.
            nomi.update(re.findall(r"'([a-z0-9][a-z0-9-]*)'", valore))
            continue
        nomi.add(valore)
    # Anche quelli scritti con `setAttribute('data-lucide', 'x')`.
    nomi.update(re.findall(r"setAttribute\('data-lucide',\s*'([^']+)'\)", testo))
    return {n for n in nomi if n}


def test_l_elenco_delle_icone_parla_della_versione_fissata():
    """Un elenco che parla di un'altra versione e' peggio di nessun elenco:
    direbbe di si' a nomi che il browser non conosce, e di no a nomi validi."""
    versione_elenco, nomi = _icone_valide()

    assert len(nomi) > 800, f"l'elenco ha solo {len(nomi)} nomi: rigeneralo"

    trovato = re.search(r"lucide@([\d.]+)/dist/umd/lucide\.min\.js", _frontend())
    assert trovato, "la pagina non fissa piu' una versione di lucide"

    assert trovato.group(1) == versione_elenco, (
        f"la pagina usa lucide {trovato.group(1)} e l'elenco parla della "
        f"{versione_elenco}: rigeneralo con `python scripts/aggiorna_icone.py`"
    )


def test_ogni_icona_della_pagina_esiste_davvero():
    """Un nome sbagliato non da' errore: da' un buco.

    Lucide non trova la chiave, scrive un avviso nella console e lascia il tag
    vuoto. Nel sorgente il nome c'e', quindi nessuna guardia che legge il
    sorgente se ne accorge — e infatti in una sola giornata sono passati
    `house` (invece di `home`) e `wand-sparkles`, che in questa versione non
    esiste. Tutti e due visti guardando la schermata renderizzata.

    Questa guardia fa la stessa cosa che fa il browser: prende il nome scritto
    nell'attributo, lo converte con la funzione di lucide, e lo cerca fra le
    chiavi vere.

    Riferimento: issue #139.
    """
    _, chiavi = _icone_valide()

    testo = _frontend()
    usate = _nomi_di_icona_nella_pagina(testo)

    assert len(usate) > 40, f"solo {len(usate)} icone trovate: il test non guarda piu' niente"

    buchi = sorted(n for n in usate if _in_pascal(n) not in chiavi)

    assert buchi == [], f"questi nomi non esistono in lucide e lasciano un buco al loro posto: {buchi}"


def test_la_guardia_delle_icone_riconosce_i_due_nomi_che_l_hanno_ingannata():
    """La prova che l'oracolo e' un oracolo.

    Se `house` e `wand-sparkles` risultassero validi, la guardia di sopra
    sarebbe verde su entrambi i difetti che l'hanno motivata — e non varrebbe
    niente. Costa due righe saperlo.
    """
    _, chiavi = _icone_valide()

    for buono in ("home", "chevron-down", "sparkles", "shield-check"):
        assert _in_pascal(buono) in chiavi, f"«{buono}» dovrebbe essere valido"

    for cattivo in ("house", "wand-sparkles", "casa-mia"):
        assert _in_pascal(cattivo) not in chiavi, f"«{cattivo}» non dovrebbe essere valido"


# ------------------------------------------ la pagina scomposta (issue #34)


def test_la_pagina_non_porta_piu_dentro_il_copione_e_il_foglio():
    """Settemilaquattrocento righe in un file solo.

    Markup, CSS e JavaScript insieme vogliono dire che l'ambito di qualunque
    cosa e' tutto, e che ogni modifica all'interfaccia costa piu' del dovuto.
    E' il freno principale alle altre schede rimaste.

    Restano in linea due copioni, e devono restarci: configurano Tailwind e
    rimediano a lucide che non carica, tutti e due **prima** che la pagina si
    disegni. Un file esterno arriverebbe troppo tardi.
    """
    pagina = _testo(PAGINA)

    assert "<style>" not in pagina, "il foglio di stile e' tornato dentro la pagina"

    inline = _script_inline(pagina)
    assert len(inline) == 2, (
        f"i copioni in linea sono {len(inline)}: devono restare solo i due del "
        "`<head>`, che girano prima del disegno"
    )
    for blocco in inline:
        assert len(blocco) < 2000, "un copione in linea e' cresciuto: va in un file suo"

    assert (
        len(pagina.splitlines()) < 1400
    ), f"la pagina e' {len(pagina.splitlines())} righe: era 7.438 e deve scendere, non risalire"


def test_i_fogli_e_i_copioni_esistono_e_non_sono_vuoti():
    """Una guardia che controllasse solo l'assenza dalla pagina sarebbe verde
    anche il giorno che qualcuno cancella i file invece di collegarli."""
    fogli, copioni = _fogli(), _copioni()

    assert len(fogli) >= 4, f"fogli di stile trovati: {[p.name for p in fogli]}"
    assert len(copioni) >= 15, f"copioni trovati: {[p.name for p in copioni]}"

    for percorso in [*fogli, *copioni]:
        righe = len(_testo(percorso).splitlines())
        assert righe > 30, f"{percorso.name} ha {righe} righe: o e' vuoto, o non doveva nascere"

    assert len(_stile().splitlines()) > 700, "il foglio di stile complessivo si e' svuotato"
    assert len(_comportamento().splitlines()) > 5000, "il copione complessivo si e' svuotato"


def test_nessun_pezzo_del_frontend_supera_le_cinquecento_righe():
    """Il criterio di accettazione della #34, scritto come guardia.

    Il numero non e' magico: e' la soglia oltre la quale un file smette di
    entrare in testa tutto insieme, e si torna a modificarlo cercando col
    trova invece di leggerlo. La pagina unica ne aveva 7.438.

    Riferimento: issue #34.
    """
    lunghi = {}
    for percorso in [PAGINA, ACCESSO, *_fogli(), *_copioni()]:
        righe = len(_testo(percorso).splitlines())
        if righe > 500:
            lunghi[percorso.name] = righe

    # `index.html` e' l'unico ancora sopra: e' markup, e va spezzato in
    # template inclusi, non in moduli. Finche' non succede resta segnato qui,
    # cosi' la guardia morde su tutto il resto invece di essere spenta.
    lunghi.pop("index.html", None)

    assert not lunghi, f"file oltre le cinquecento righe: {lunghi}"


def _collegamenti(pagina: str) -> list[str]:
    """Gli indirizzi statici che la pagina collega, nell'ordine in cui stanno."""
    return re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"?]+)', _senza_commenti_html(pagina))


def test_la_pagina_collega_tutti_i_pezzi_e_nessun_altro():
    """Un pezzo nuovo che nessuno collega e' codice morto; un pezzo tolto e
    lasciato collegato e' un 404 a ogni apertura.

    Il modo di sbagliare e' sempre lo stesso: si spezza un file, si scrive il
    pezzo nuovo, e ci si dimentica della riga nel `<head>`. Il sintomo e' una
    meta' della dashboard che smette di rispondere ai clic, senza un errore
    in console che lo dica.

    Riferimento: issue #34.
    """
    collegati = _collegamenti(_testo(PAGINA))
    sul_disco = [f"/static/css/{p.name}" for p in _fogli()] + [f"/static/js/{p.name}" for p in _copioni()]

    assert sorted(collegati) == sorted(sul_disco), (
        f"scollegati (esistono ma la pagina non li carica): {sorted(set(sul_disco) - set(collegati))}\n"
        f"fantasmi (collegati ma non esistono): {sorted(set(collegati) - set(sul_disco))}"
    )


def test_i_copioni_si_caricano_nell_ordine_in_cui_furono_scritti():
    """L'ordine non e' un dettaglio estetico.

    Sono copioni normali, non moduli: il codice in cima a ognuno gira quando
    il file arriva. `avvio.js` legge la palette e la applica prima che il
    resto esista; `impostazioni.js` in coda registra l'ascolto del `load`.
    Invertirli non da' un errore di sintassi — da' una pagina che si disegna
    col tema sbagliato per un istante, o che non si disegna affatto.
    """
    ordine = [p.split("/")[-1] for p in _collegamenti(_testo(PAGINA)) if p.endswith(".js")]

    assert ordine[0] == "avvio.js", f"il primo copione e' {ordine[0]}"
    assert ordine[-1] == "impostazioni.js", f"l'ultimo copione e' {ordine[-1]}"
    assert ordine.index("navigazione.js") < ordine.index("tela.js"), (
        "navigazione.js dichiara le costanti delle schede che gli altri leggono: " "deve arrivare prima"
    )
    assert len(ordine) == len(set(ordine)), f"un copione e' collegato due volte: {ordine}"


def test_la_pagina_li_collega_con_la_versione_attaccata():
    """Il browser tiene i file statici finche' non cambia l'indirizzo.

    Con il copione dentro la pagina il problema non c'era: la pagina si
    rivalida a ogni apertura. Portandolo fuori si e' aperta una superficie di
    cache nuova, e una dashboard che gira su JavaScript vecchio dopo un
    aggiornamento e' esattamente il genere di guasto che fa perdere un
    pomeriggio — e' gia' successo con la pagina intera.

    La versione cambia a ogni commit: attaccarla all'indirizzo basta.
    """
    pagina = _testo(PAGINA)
    indirizzi = _collegamenti(pagina)
    assert len(indirizzi) > 15, f"collegamenti trovati: {indirizzi}"

    for indirizzo in indirizzi:
        collegamento = re.search(rf'{re.escape(indirizzo)}\?v=([^"]+)"', pagina)
        assert collegamento, f"{indirizzo} e' collegato senza la versione attaccata"
        assert "versione" in collegamento.group(1), (
            f"{indirizzo} porta una versione fissa invece di quella vera: " f"{collegamento.group(1)}"
        )


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
    attesi = len(_fogli()) + len(_copioni())
    assert len(indirizzi) == attesi, f"collegamenti trovati: {len(indirizzi)}, file sul disco: {attesi}"

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
