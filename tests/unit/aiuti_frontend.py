"""Gli aiuti condivisi delle guardie del frontend.

Stavano in cima a `test_interfaccia.py`, un file di quattromila righe: nel dividerlo per area, quelli usati
da piu' di un file sono venuti qui. Il resto del loro commento e' rimasto con ciascuno.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

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


# Il punto d'ingresso dei moduli: importa le aree per i loro effetti e non
# contiene codice suo. Le guardie "per area" non lo contano fra le aree.
INGRESSO = "principale.js"


def _copioni() -> list[Path]:
    """Le aree: i moduli della dashboard, senza il punto d'ingresso."""
    return sorted(p for p in CARTELLA_JS.glob("*.js") if p.name != INGRESSO)


_IMPORT = re.compile(r"^import\s+(?:\{[^}]*\}\s+from\s+)?'[^']+';\n", re.M)


def _testo_grezzo(percorso: Path) -> str:
    return percorso.read_text(encoding="utf-8")


def _testo(percorso: Path) -> str:
    """Il testo di un file. Per i moduli, come se fossero copioni.

    Dalla #34 le aree sono moduli ES: `import` in cima, `export` davanti a cio'
    che condividono. Le guardie di questo file cercano funzioni, dichiarazioni
    e pezzi di markup nel sorgente, e molte mandano in esecuzione una funzione
    estratta per nome con un mondo finto attorno: per tutte, `import` ed
    `export` sono rumore che non cambia cio' che il codice fa. Si tolgono qui,
    una volta sola, invece che in cento espressioni regolari.

    Le guardie che parlano proprio dei moduli — `_testo_grezzo` — leggono il
    file com'e'.
    """
    testo = _testo_grezzo(percorso)
    if percorso.suffix == ".js" and percorso.parent == CARTELLA_JS:
        testo = _IMPORT.sub("", testo)
        testo = re.sub(
            r"^export\s+(?=(?:async\s+)?(?:function|const|let|var|class)\b)", "", testo, flags=re.M
        )
    return testo


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


def _gesto(nome: str, testo: str | None = None, quando: str = "gesto") -> str:
    """Come il markup chiede un gesto, dalla #34.

    Prima le guardie cercavano `switchTab('console')`, perche' la chiamata
    stava scritta dentro un `onclick`. Adesso il markup **nomina** il gesto e
    non esegue niente, e com'e' scritto lo sa questa funzione sola: il giorno
    che la forma cambia non ci sono sei guardie da rincorrere una per una.

    `quando` e' l'evento: `gesto` per il clic, `al-cambio`, `mentre-scrivi`,
    `all-invio` per gli altri tre.
    """
    pezzo = f'data-{quando}="{nome}"'
    return pezzo if testo is None else f'{pezzo} data-testo="{testo}"'


def _script_inline(testo: str) -> list[str]:
    """Solo gli script scritti nella pagina: quelli con `src` non sono nostri.

    Nemmeno l'import map lo e': e' JSON dentro un `<script type="importmap">`,
    non codice che gira, e `node --check` lo rifiuterebbe. Ha i suoi test.
    """
    return re.findall(r'<script(?![^>]*\bsrc=)(?![^>]*type="importmap")[^>]*>(.*?)</script>', testo, re.S)


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
