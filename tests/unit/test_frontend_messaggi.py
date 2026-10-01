"""I caricamenti, i messaggi e gli stati vuoti: nessun rifiuto deve sembrare un vuoto.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import re
import shutil

import pytest
from aiuti_frontend import (
    _esegui_con_node,
    _frontend,
    _funzione_javascript,
    _senza_commenti,
)


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
