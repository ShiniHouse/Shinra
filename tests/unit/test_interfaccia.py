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


def _script_inline(testo: str) -> list[str]:
    """Solo gli script scritti nella pagina: quelli con `src` non sono nostri."""
    return re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", testo, re.S)


# ------------------------------------------------------------------ sintassi


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
    testo = _testo(PAGINA)
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

    chiamate = {normalizza(g) for g in re.findall(r"fetch\(\s*[`'\"](/api/[^`'\"]*)[`'\"]", _testo(PAGINA))}
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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    assert ".port-pin {" in testo, "i pin dei cavi non hanno nessuno stile: sarebbero invisibili"
    for regola in (".port-pin-in", ".port-pin-out", ".port-pin-vero", ".port-pin-falso"):
        assert regola in testo, f"manca la posizione di {regola}"


def test_una_condizione_ha_due_uscite_distinte():
    """Un'uscita sola non e' una condizione: e' un filtro che a volte ferma
    tutto, e chi lo disegna si aspetta due strade."""
    testo = _testo(PAGINA)

    assert "onPinMouseDown('${node.id}', event, 'vero')" in testo
    assert "onPinMouseDown('${node.id}', event, 'falso')" in testo
    assert "nuovo.ramo = ramo" in testo, "il ramo non viene scritto sull'arco"


def test_il_salvataggio_mostra_cosa_non_va_e_dove():
    """«Il grafo non e' valido» manda a guardarne trenta, e chi ne ha
    disegnati trenta non lo fa: salva lo stesso, o rinuncia."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    apertura = testo.index("async function simulateCanvasFlow()")
    corpo = testo[apertura : testo.index("function spegniLaSimulazione")]

    assert "'/api/modes/simula'" in corpo, "la simulazione non chiede niente al server"
    assert "esito.visitati" in corpo, "la pagina non usa i nodi che il server dice di aver percorso"
    assert "queue" not in corpo, "e' tornata una visita del grafo dentro la pagina"


def test_la_simulazione_accende_un_ramo_solo():
    """Il ramo non percorso deve restare spento: due rami accesi dicono che
    succedono due cose che si escludono a vicenda."""
    testo = _testo(PAGINA)

    apertura = testo.index("async function simulateCanvasFlow()")
    corpo = testo[apertura : testo.index("function spegniLaSimulazione")]

    assert "e.ramo === scelta.ramo" in corpo, "i cavi si accendono senza guardare il ramo scelto"
    assert "visitati.includes(e.to)" in corpo, "si accende anche un cavo verso un nodo mai raggiunto"


def test_la_simulazione_dice_perche_ha_scelto_quel_ramo():
    """Il ramo preso senza il perche' e' indistinguibile da un ramo preso a
    caso."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    assert "setTipoInnesco('${node.id}', this.value)" in testo, "non si puo' cambiare tipo di innesco"
    for tipo in ("orario", "alba", "tramonto", "stato", "evento"):
        assert f'value="{tipo}"' in testo, f"manca l'innesco «{tipo}» fra le scelte"


def test_cambiare_tipo_di_innesco_riparte_da_zero():
    """I campi di un innesco a orario non valgono per uno su soglia: lasciarli
    in giro produce una regola che porta dietro dati che nessuno legge."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    assert 'id="tab-automazioni"' in testo, "la scheda non esiste"
    assert "switchTab('automazioni')" in testo, "non ci si arriva dalla navigazione"
    assert "switchTabMobile('automazioni')" in testo, "dal telefono non ci si arriva"
    assert (
        "if (tabId === 'automazioni') { loadRegole(); loadModes(); }" in testo
    ), "aprendola non carica niente, o ne carica solo meta'"
    assert "'automazioni': 'block'," in testo, "la scheda non comparirebbe mai"
    assert 'id="regole-lista"' in testo, "l'elenco delle automazioni non c'e' piu'"


def test_una_regola_dice_quando_scattera_la_prossima_volta():
    """E' la domanda con cui si arriva a questa schermata, sempre: «e allora
    perche' non e' successo niente?»."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    corpo = testo[testo.index("function quandoScatta") : testo.index("function renderRegole")]

    assert "regola.aspetta_un_evento" in corpo, "le due si leggerebbero uguali"


def test_una_regola_si_puo_zittire_senza_cancellarla():
    testo = _testo(PAGINA)

    assert "alternaRegola('${r.id}', ${!r.attiva})" in testo, "non si puo' zittire una regola"
    assert "'/api/regole/${id}'" in testo.replace("`", "'"), "lo stato non torna al server"


def test_di_una_regola_generata_non_si_offre_la_cancellazione():
    """Cancellarla non servirebbe a niente: risalvando la routine tornerebbe
    identica. Offrire un pulsante che non ottiene quello che promette e'
    peggio che non offrirlo."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    corpo = testo[testo.index("async function provaRegola") : testo.index("async function cancellaRegola")]

    # Anche qui il ramo, non il nome: `} else if (false) {` lasciava
    # `esito.motivo` scritto nella riga sotto, e la guardia restava verde.
    assert "} else if (esito.motivo) {" in corpo, "il motivo del rifiuto non viene mai mostrato"
    assert "/prova" in corpo


def test_senza_automazioni_la_schermata_dice_come_farne_una():
    """Un elenco vuoto e basta lascia chi guarda esattamente dov'era."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    corpo = testo[testo.index("const res = await fetch('/api/chat'") :][:800]

    assert "satellite: satelliteDiQuestoDispositivo()" in corpo, "la stanza non arriva al server"


def test_la_stanza_si_puo_cambiare_da_dove_si_parla():
    """Il telefono che si sposta di stanza cambia risposta: nasconderlo in un
    pannello di impostazioni vorrebbe dire che nessuno lo aggiorna mai."""
    testo = _testo(PAGINA)

    assert 'id="scelta-stanza"' in testo, "non si puo' scegliere la stanza"
    assert "scegliStanza(this.value)" in testo, "la scelta non viene salvata"
    # Sta nella barra del microfono, non fra le impostazioni.
    barra = testo[testo.index('id="chat-form"') : testo.index("<!-- Right: Activity Logs")]
    assert 'id="scelta-stanza"' in barra, "la stanza e' finita lontano da dove si parla"


def test_la_memoria_della_stanza_non_fa_esplodere_la_pagina():
    """In navigazione privata `localStorage` solleva invece di rispondere. Una
    dashboard che non si apre perche' non puo' ricordare una stanza sarebbe un
    prezzo assurdo per una comodita'."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    corpo = testo[testo.index("async function riempiStanzeNote") :][:900]

    assert "'/api/aliases'" in corpo, "le stanze suggerite non vengono dai dispositivi"
    assert "a.room" in corpo


# ------------------------------------------------- caricamenti e messaggi


def _funzione_javascript(testo: str, nome: str) -> str:
    """La funzione scritta nella pagina, dalla firma alla sua parentesi.

    Tutte le funzioni della pagina stanno a otto spazi di rientro dentro il
    `<script>`: la prima riga fatta di otto spazi e una parentesi chiusa e'
    la fine della funzione. Serve per darla a `node` ed eseguirla davvero,
    invece di cercare stringhe dentro al sorgente.
    """
    apertura = testo.index(f"function {nome}(")
    resto = testo[apertura:]
    chiusura = resto.index("\n        }\n")
    return resto[: chiusura + len("\n        }")]


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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

    muti = []
    funzioni = list(re.finditer(r"\n {8}(?:async )?function (\w+)\(", testo))
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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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

    funzione = _funzione_javascript(_testo(PAGINA), "_testoDelDettaglio")

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


def _stile(testo: str) -> str:
    """Il foglio di stile scritto nella pagina."""
    blocco = re.search(r"<style>(.*?)</style>", testo, re.S)
    assert blocco, "la pagina non ha piu' un blocco <style>: il test non guarda piu' niente"
    return blocco.group(1)


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
    testo = _testo(PAGINA)
    stile = _stile(testo)

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
    testo = _testo(PAGINA)
    stile = _stile(testo)

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
    testo = _testo(PAGINA)
    stile = _stile(testo)

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
    testo = _testo(PAGINA)

    apertura = testo.index("function renderFlowCanvasModal()")
    corpo = testo[apertura : testo.index("function initCanvasInteractions")]

    assert "closeModal()" in corpo, "l'editor non si puo' piu' chiudere"
    assert "-top-3.5 -right-3.5" in corpo, "la chiusura non e' nell'angolo, fuori dal riquadro"

    # E la fetta attorno a «Salva» non deve contenere anche la chiusura.
    intorno = corpo[corpo.index("saveCanvasMode()") :][:600]
    assert "closeModal()" not in intorno, "la X e' tornata in fila accanto a «Salva»"


def test_la_finestra_larga_non_taglia_cio_che_sporge():
    """La X nell'angolo esiste solo se la finestra la lascia sporgere."""
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)
    stile = _stile(testo)

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
    testo = _testo(PAGINA)

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
    testo = _testo(PAGINA)

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
    colonna = _colonna_della_console(_testo(PAGINA))

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
    testo = _testo(PAGINA)
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

    funzione = _funzione_javascript(_testo(PAGINA), "updateAlexaGeneratorName")

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

    testo = _testo(PAGINA)
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

    testo = _testo(PAGINA)
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
    colonna = re.sub(r"<!--.*?-->", "", _colonna_della_console(_testo(PAGINA)), flags=re.S)

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
    barra = _senza_commenti_html(_barra_desktop(_testo(PAGINA)))

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
    testo = _testo(PAGINA)
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
    cassetto = _senza_commenti_html(_cassetto_telefono(_testo(PAGINA)))

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
    testo = _testo(PAGINA)

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

    testo = _testo(PAGINA)
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
    testo = _senza_commenti(_testo(PAGINA))

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
    testo = _senza_commenti(_testo(PAGINA))

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
    barra = _senza_commenti_html(_barra_desktop(_testo(PAGINA)))

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
    barra = _senza_commenti_html(_barra_desktop(_testo(PAGINA)))

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
