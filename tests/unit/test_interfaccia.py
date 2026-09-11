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

    Riferimento: issue #27.
    """
    testo = _testo(PAGINA)

    assert 'id="tab-regole"' in testo, "la scheda non esiste"
    assert "switchTab('regole')" in testo, "non ci si arriva dalla navigazione"
    assert "switchTabMobile('regole')" in testo, "dal telefono non ci si arriva"
    assert "if (tabId === 'regole') loadRegole();" in testo, "aprendola non carica niente"
    assert "'regole':    'block'," in testo, "la scheda non comparirebbe mai"


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
