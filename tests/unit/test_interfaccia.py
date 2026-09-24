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
# Dalla #34 anche il markup sta in pezzi: `index.html` tiene il `<head>`,
# l'ossatura e i collegamenti, e include un file per area. Stessa regola dei
# fogli e dei copioni — la cartella si legge, i nomi non si sanno a memoria.
CARTELLA_PARTI = RADICE / "web" / "templates" / "parti"
# Il file che dichiara `Stato`, il contenitore di cio' che attraversa le aree
# (#34). Sta qui in cima perche' lo legge anche `_esegui_con_node`, che deve
# dichiararlo prima di eseguire una funzione che lo usa.
CONTENITORE = "stato.js"


def _fogli() -> list[Path]:
    return sorted(CARTELLA_CSS.glob("*.css"))


def _parti() -> list[Path]:
    return sorted(CARTELLA_PARTI.glob("*.html"))


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


def _markup() -> str:
    """Tutto il markup della dashboard: l'ossatura piu' i pezzi inclusi.

    Dalla #34 `index.html` non contiene piu' le schede: le include. Una
    guardia che cerca un elemento nella pagina deve guardare qui, non
    `_testo(PAGINA)` — quella adesso vede solo il `<head>`, i collegamenti e
    dieci righe di `{% include %}`.
    """
    pezzi = _parti()
    assert len(pezzi) >= 5, f"i pezzi del markup sono spariti: {[p.name for p in pezzi]}"
    return "\n".join(_testo(p) for p in [PAGINA, *pezzi])


def _frontend() -> str:
    """Markup, foglio di stile e copione insieme.

    Dalla #34 vivono in file separati, uno per area. Una guardia che chiede
    «questa cosa esiste nel frontend?» guarda qui; una che dice **dove** deve
    stare guarda i file precisi — `_markup()` per il markup, `_stile()` per i
    colori, `_comportamento()` per il codice.
    """
    return "\n".join([_markup(), *(_testo(p) for p in [*_fogli(), *_copioni()])])


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


# Solo i due file che hanno davvero copioni in linea: i pezzi di `parti/` sono
# markup e basta, e che restino tali lo verifica
# `test_i_copioni_in_linea_sono_solo_quelli_che_devono_girare_prima_del_disegno`.
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

    # Da quando l'identificativo passa da `_perAttributoJs`, fra le
    # parentesi non c'e' piu' un apice scritto a mano: si guarda che la
    # chiamata esista e che porti lo stato rovesciato, non come e' scritta.
    assert re.search(r"alternaRegola\(.*?,\s*\$\{!r\.attiva\}\)", testo), "non si puo' zittire una regola"
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
    # `async` sta prima di `function`: dimenticarlo qui da' una funzione che
    # non compila, perche' il suo corpo ha degli `await` dentro una funzione
    # che non e' piu' asincrona. Il messaggio di node parla di moduli e manda
    # a cercare dalla parte sbagliata.
    if testo[:apertura].endswith("async "):
        apertura -= len("async ")
    resto = testo[apertura:]
    chiusura = resto.index("\n}\n")
    return resto[: chiusura + len("\n}")]


def _riga_javascript(testo: str, inizio: str) -> str:
    """La riga che comincia cosi'. Serve a portarsi dietro una costante
    quando si esegue una funzione che la legge: riscriverla qui vorrebbe
    dire provare una copia, che resta giusta anche quando l'originale non
    lo e' piu'."""
    for riga in testo.splitlines():
        if riga.strip().startswith(inizio):
            return riga.strip()
    raise AssertionError(f"riga che comincia con {inizio!r} non trovata")


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
    """Esegue il pezzo di copione dato, con `Stato` gia' dichiarato.

    Il contenitore si prende dal file vero invece di scriverne una copia qui:
    una copia resta giusta anche il giorno che l'originale non lo e' piu', ed
    e' il motivo per cui esiste anche `_riga_javascript`. Costa una
    dichiarazione in cima al file temporaneo, e in cambio un campo tolto da
    `stato.js` fa fallire i test che lo usavano invece di lasciarli verdi.
    """
    contenitore = _testo(CARTELLA_JS / CONTENITORE)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
        file.write(contenitore + "\n" + sorgente)
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


def _pezzo(nome: str) -> str:
    """Il markup di un'area sola.

    Dalla #34 ogni scheda sta in un file suo, e una guardia che riguarda una
    scheda legge quel file. Non e' pignoleria: `_markup()` unisce i pezzi in
    ordine alfabetico, quindi «da qui fino alla scheda dopo» li' dentro non
    vuol dire piu' niente.
    """
    percorso = CARTELLA_PARTI / f"{nome}.html"
    assert percorso.is_file(), f"il pezzo `{nome}.html` non esiste: i pezzi sono {[p.name for p in _parti()]}"
    return _testo(percorso)


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

    Restano in linea tre copioni, e devono restarci: decidono il tema,
    configurano Tailwind e rimediano a lucide che non carica — tutti e tre
    **prima** che la pagina si disegni. Un file esterno arriverebbe troppo
    tardi, ed e' esattamente il difetto della #152: il tema stava in un file,
    veniva deciso su `load`, e per mezzo secondo la pagina era scura anche a
    mezzogiorno.

    Il numero e' fissato apposta. Ogni copione in linea in piu' e' codice che
    nessun linter guarda e nessun file raccoglie: se ne serve un quarto, lo si
    aggiunge qui con la sua ragione scritta, invece di lasciarlo crescere.
    """
    pagina = _testo(PAGINA)

    assert "<style>" not in _markup(), "il foglio di stile e' tornato dentro la pagina"

    inline = _script_inline(pagina)
    assert len(inline) == 3, (
        f"i copioni in linea sono {len(inline)}: devono restare solo i tre del "
        "`<head>`, che girano prima del disegno"
    )
    for blocco in inline:
        assert len(blocco) < 2000, "un copione in linea e' cresciuto: va in un file suo"

    # I pezzi inclusi sono markup e basta: un copione in linea li' dentro non
    # sta nel `<head>`, quindi non ha la ragione che giustifica gli altri tre,
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

    # `stato.js` sta davanti a tutti: e' una sola dichiarazione, e ogni altra
    # area ne legge i campi. Un file che arrivasse prima e leggesse `Stato`
    # in cima troverebbe un nome che non esiste ancora.
    # Poi `sicurezza.js`, che dichiara `_html` — usato da tutti per disegnare.
    # Nessuno dei due esegue niente al caricamento.
    assert ordine[0] == "stato.js", f"il primo copione e' {ordine[0]}"
    assert ordine[1] == "sicurezza.js", f"il secondo copione e' {ordine[1]}"
    assert ordine[2] == "avvio.js", f"il terzo copione e' {ordine[2]}"
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


# ---------------------------------------------------------------- ESLint

ESLINT = RADICE / "eslint.config.js"
FLUSSO_CI = RADICE / ".github" / "workflows" / "ci.yml"
PACCHETTO = RADICE / "package.json"


def test_i_copioni_passano_da_eslint_in_ci():
    """Un controllo che gira solo sulla macchina di chi scrive non esiste.

    ESLint e' entrato perche' `node --check` vede la sintassi e basta: un
    nome scritto male compila benissimo e muore al clic. Il primo giro ne ha
    trovato uno che era in produzione — `_currentUserId` in `timer.js`, che
    rendeva inutile il pulsante «+ Timer».

    `--max-warnings 0` non e' pignoleria: un elenco di avvisi che nessuno
    guarda e' peggio di nessun elenco, perche' l'errore vero ci si nasconde
    dentro.

    Riferimento: issue #34.
    """
    ci = FLUSSO_CI.read_text(encoding="utf-8")

    assert "eslint" in ci, "la CI non fa girare ESLint"
    assert "--max-warnings 0" in ci, "ESLint gira ma gli avvisi non fanno fallire niente"
    assert "npm ci" in ci, "senza `npm ci` la versione di ESLint cambia sotto i piedi a ogni giro"

    pacchetto = json.loads(_testo(PACCHETTO))
    fissata = pacchetto["devDependencies"]["eslint"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", fissata), f"la versione di ESLint non e' fissata: {fissata}"

    assert (RADICE / "package-lock.json").exists(), "senza il lock il controllo non e' ripetibile"


def test_eslint_non_ha_niente_da_ridire():
    """Lo stesso controllo della CI, qui, per chi lavora in locale.

    Salta se gli attrezzi non sono installati: `npm install` non e' un
    requisito per far girare i test di un progetto Python.
    """
    eseguibile = RADICE / "node_modules" / ".bin" / "eslint"
    if not eseguibile.exists():
        pytest.skip("ESLint non installato: `npm install` per averlo. In CI c'e'")

    esito = subprocess.run(
        [str(eseguibile), "--max-warnings", "0", "web/static/js/"],
        cwd=RADICE,
        capture_output=True,
        text=True,
        check=False,
    )

    assert esito.returncode == 0, f"ESLint ha da ridire:\n{esito.stdout}\n{esito.stderr}"


def test_eslint_impara_i_nomi_globali_dalla_cartella():
    """La configurazione non tiene un elenco di nomi scritto a mano.

    I copioni sono file separati che si chiamano fra loro passando per lo
    spazio globale: ESLint, che guarda un file per volta, va informato di
    quali sono i nostri nomi. Se l'elenco fosse fisso, il giorno dopo
    sarebbe vecchio — e il modo in cui invecchia e' il peggiore: `no-undef`
    comincia a gridare su codice giusto, qualcuno la spegne per far passare
    la CI, e da quel momento non guarda piu' niente.

    La guardia **esegue** la configurazione e le chiede cosa ha imparato,
    invece di cercare `readdirSync` nel sorgente.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")
    # La configurazione importa `globals`, che sta negli attrezzi.
    if not (RADICE / "node_modules").exists():
        pytest.skip("attrezzi del frontend non installati: `npm install` per averli. In CI ci sono")

    # `timer.js` deve conoscere un nome dichiarato da un altro file: `Stato`,
    # che sta in `stato.js` e da cui `timer.js` legge i timer accesi. Prima
    # della #34 qui c'era `activeUserId`, che era il nome che mancava davvero
    # quando questa guardia e' nata.
    lettura = """
import config from './eslint.config.js';
const per = (f) => config.find(c => c.files && c.files.includes('web/static/js/' + f));
const nomi = (f) => Object.keys(per(f).languageOptions.globals);
console.log(JSON.stringify({
    timer: nomi('timer.js'),
    quanti: config.filter(c => c.files && c.files[0].startsWith('web/static/js/')).length,
}));
"""
    prova = RADICE / "_prova_eslint.mjs"
    prova.write_text(lettura, encoding="utf-8")
    try:
        esito = subprocess.run(["node", str(prova)], cwd=RADICE, capture_output=True, text=True, check=False)
    finally:
        prova.unlink(missing_ok=True)

    assert esito.returncode == 0, esito.stderr
    visto = json.loads(esito.stdout.strip())

    assert visto["quanti"] == len(_copioni()), (
        f"la configurazione copre {visto['quanti']} copioni, sul disco ce ne sono " f"{len(_copioni())}"
    )
    for nome in ("Stato", "getAuthHeaders", "document", "fetch"):
        assert nome in visto["timer"], f"ESLint non sa che `{nome}` esiste: gridera' su codice giusto"
    assert "saveNewTimerManual" not in visto["timer"], (
        "i nomi che timer.js dichiara da se' gli vengono dati anche come globali: " "e' una ridichiarazione"
    )


def test_le_regole_di_eslint_sono_accese_davvero():
    """Una guardia che dice «ESLint non ha da ridire» resta verde anche il
    giorno che qualcuno spegne le regole per far passare la CI.

    E' successo il contrario, in questo file, altre volte: la guardia cercava
    una stringa e la trovava in un commento. Qui il rischio e' lo stesso a
    rovescio, e si chiude allo stesso modo — dandole da mangiare del codice
    rotto e pretendendo che se ne accorga.

    Il codice rotto non tocca il disco: passa dallo standard input con il
    nome di un file vero, cosi' prende le sue regole senza esistere.
    """
    eseguibile = RADICE / "node_modules" / ".bin" / "eslint"
    if not eseguibile.exists():
        pytest.skip("ESLint non installato: `npm install` per averlo. In CI c'e'")

    rotture = {
        "no-undef": "function prova() { return nomeCheNessunoHaMaiDichiarato; }",
        "valid-typeof": "function prova(x) { return typeof x === 'strng'; }",
        "no-unreachable": "function prova() { return 1; const mai = 2; return mai; }",
        "no-dupe-keys": "function prova() { return { a: 1, a: 2 }; }",
        "no-unused-vars": "function prova() { const inutile = 1; return 2; }",
    }

    for regola, sorgente in rotture.items():
        esito = subprocess.run(
            [str(eseguibile), "--stdin", "--stdin-filename", "web/static/js/timer.js"],
            input=sorgente,
            cwd=RADICE,
            capture_output=True,
            text=True,
            check=False,
        )
        assert regola in esito.stdout, f"`{regola}` non e' accesa: ESLint non dice niente su:\n{sorgente}"


def test_i_copioni_passano_anche_da_prettier():
    """La formattazione a mano di un file da cinquemila righe era un costo a
    ogni modifica: due righe vicine scritte da due mani diverse, rientri che
    non tornano, e una diff che mescola cio' che cambia con cio' che si e'
    solo spostato.

    Prettier non trova guasti — quello e' ESLint. Toglie di mezzo la
    discussione.

    Riferimento: issue #34.
    """
    ci = FLUSSO_CI.read_text(encoding="utf-8")
    assert "prettier --check" in ci, "la CI non controlla la formattazione del frontend"

    pacchetto = json.loads(_testo(PACCHETTO))
    fissata = pacchetto["devDependencies"]["prettier"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", fissata), f"la versione di Prettier non e' fissata: {fissata}"

    eseguibile = RADICE / "node_modules" / ".bin" / "prettier"
    if not eseguibile.exists():
        pytest.skip("Prettier non installato: `npm install` per averlo. In CI c'e'")

    esito = subprocess.run(
        [str(eseguibile), "--check", "web/static/"],
        cwd=RADICE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert esito.returncode == 0, f"da riformattare:\n{esito.stdout}\n{esito.stderr}"


def test_prettier_non_tocca_il_python():
    """Due formattatori sullo stesso file litigherebbero a ogni giro di CI,
    e il perdente sarebbe sempre chi ha fatto l'ultimo commit.

    Del Python decide black. Prettier sta sotto `web/static/` e basta.
    """
    ignorati = _testo(RADICE / ".prettierignore")
    for cartella in ("src/", "tests/", "scripts/", "docs/", "node_modules/"):
        assert cartella in ignorati, f"Prettier potrebbe mettere mano a {cartella}"

    ci = FLUSSO_CI.read_text(encoding="utf-8")
    comando = next(r for r in ci.splitlines() if "prettier --check" in r)
    assert "web/static/" in comando, f"Prettier in CI non e' limitato al frontend: {comando.strip()}"


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
    apiceNudaNellAttributo: /onclick="speakText\\([^"]*'[^"]*\\)"/.test(disegnato),
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
    ], "un apice chiude la stringa dentro l'onclick e ne apre un'altra"


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
    perAttributoJs: String(_html`<b onclick="fai(${_grezzo(_perAttributoJs("un'apice \" e virgolette"))})"></b>`),
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
    assert (
        "'" not in visto["perAttributoJs"]
        and '"' not in visto["perAttributoJs"].split("fai(")[1].split(")")[0]
    )


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

    Quindi l'argomento deve essere una stringa scritta li' — apici e
    nient'altro — oppure `_perAttributoJs(...)`, che ripulisce a modo suo.

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
            calcolato = argomento.startswith("_perAttributoJs(")
            if not (letterale or calcolato):
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
        r"<circle[^>]*onclick=\"deleteCanvasEdge", _senza_commenti_html(_testo(CARTELLA_JS / "tela_nodi.js"))
    )
    assert crocetta, "la crocetta che stacca un cavo non c'e' piu'"
    assert "pointer-events-auto" in crocetta.group(
        0
    ), "la crocetta non riprende gli eventi: il piano dei cavi non ne fa passare nessuno"


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
                          'preparaSezioniImpostazioni']) {
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
    for piu_lento in ('<link rel="stylesheet"', "cdn.tailwindcss.com", "fonts.googleapis.com", "<body"):
        assert pagina.index(piu_lento) > tema, (
            f"«{piu_lento}» viene prima della decisione sul tema: "
            "la pagina si disegna scura e poi cambia colore."
        )


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
    import re

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
