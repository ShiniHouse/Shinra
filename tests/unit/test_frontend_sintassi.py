"""La sintassi del frontend, gli identificativi cercati, le rotte chiamate, ESLint e i nomi delle icone.

Venivano da `test_interfaccia.py`, che aveva quattromila righe: i test sono gli stessi, divisi per area.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from aiuti_frontend import (
    ACCESSO,
    PAGINA,
    RADICE,
    _copioni,
    _frontend,
    _script_inline,
    _testo,
    _testo_grezzo,
)

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

    trovato = re.search(r"/static/vendor/lucide-([\d.]+)\.min\.js", _frontend())
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


def test_eslint_tratta_i_copioni_come_moduli():
    """La configurazione non ha piu' un elenco di nomi globali.

    Quando i copioni si chiamavano fra loro passando per lo spazio globale,
    ESLint andava informato di quali fossero i nostri nomi, e la
    configurazione li imparava leggendo la cartella. Adesso ogni file dichiara
    `import` ed `export`, e ESLint li segue da se': un nome che non e' ne'
    locale, ne' importato, ne' del browser e' un errore.

    La guardia **esegue** la configurazione e le chiede cosa applica ai moduli,
    invece di cercare parole nel sorgente: deve essere `module` — con `script`
    un `import` e' un errore di sintassi — e non deve regalare nomi nostri
    come globali, perche' sarebbe il modo di far tacere `no-undef`.
    """
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")
    if not (RADICE / "node_modules").exists():
        pytest.skip("attrezzi del frontend non installati: `npm install` per averli. In CI ci sono")

    lettura = """
import config from './eslint.config.js';
const blocco = config.find(c => c.files && c.files.includes('web/static/js/*.js'));
console.log(JSON.stringify({
    tipo: blocco.languageOptions.sourceType,
    globali: Object.keys(blocco.languageOptions.globals),
    regole: blocco.rules,
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

    assert (
        visto["tipo"] == "module"
    ), f"i copioni sono letti come «{visto['tipo']}»: gli `import` non compilano"
    for nome in ("document", "fetch", "lucide"):
        assert nome in visto["globali"], f"ESLint non sa che `{nome}` esiste: gridera' su codice giusto"
    nostri = {
        n
        for p in _copioni()
        for n in re.findall(r"^export\s+(?:async\s+)?(?:function|const|let)\s+(\w+)", _testo_grezzo(p), re.M)
    }
    regalati = sorted(nostri & set(visto["globali"]))
    assert regalati == [], f"nomi nostri regalati come globali: {regalati}"
    assert (
        visto["regole"].get("no-import-assign") == "error"
    ), "un'area puo' riassegnare una variabile di un'altra"


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
