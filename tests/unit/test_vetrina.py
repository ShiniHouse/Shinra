"""I numeri che i documenti dichiarano sono quelli veri, adesso.

La `docs/ROADMAP.md` ha detto per settimane che `index.html` era di **7.438
righe**. Era vero quando fu scritta. Nel frattempo il file e' stato scomposto
e ne contava 1.257, ma la riga era prosa: nessuno la rileggeva, niente la
faceva fallire, e la vetrina del progetto raccontava una struttura che non
esisteva piu'.

Stesso difetto, stessa forma: un dato misurato scritto a mano in un documento
invecchia in silenzio. Questo file lo rende rumoroso — se `index.html` cambia
lunghezza, o se un file JavaScript diventa il piu' lungo al posto di un altro,
i test falliscono e dicono quale documento va aggiornato.

Guarda anche che le immagini citate esistano davvero: un `<img>` rotto nel
README e' la prima cosa che vede chi apre il progetto, e nessuno se ne accorge
finche' non la vede qualcun altro.
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
README = RADICE / "README.md"
ROADMAP = RADICE / "docs" / "ROADMAP.md"
SCHEDA_34 = RADICE / "docs" / "backlog" / "v0.5.0" / "34-frontend-modulare.md"

INDEX = RADICE / "web" / "templates" / "index.html"
CARTELLA_JS = RADICE / "web" / "static" / "js"

DOCUMENTI = (README, ROADMAP, SCHEDA_34)

# «`index.html` e' passato da 7.438 righe a **1.257**» nella prosa del README,
# e la riga «| `web/templates/index.html` | 7.438 righe | **1.257** |» nelle
# due tabelle. Il numero catturato e' sempre quello di adesso.
RIGHE_DI_INDEX = re.compile(
    r"index\.html`?\s*(?:\||e' passato da|è passato da)[^|*]*\|?\s*" r"(?:a\s*)?\*\*([\d.]+)\*\*"
)

# «il piu' lungo di **451** righe», in tutti e tre i documenti.
IL_PIU_LUNGO = re.compile(r"il pi[uù]'? lungo di\s+\*\*([\d.]+)\*\*\s+righe")

# Sia `<img src="...">` sia `![...](...)`.
IMMAGINI = re.compile(r"<img[^>]*\bsrc=\"([^\"]+)\"|!\[[^\]]*\]\(([^)]+)\)")


def _numero(scritto: str) -> int:
    """`1.257` -> 1257. I documenti separano le migliaia col punto."""
    return int(scritto.replace(".", ""))


def _righe(percorso: Path) -> int:
    return len(percorso.read_text(encoding="utf-8").splitlines())


def _righe_del_js_piu_lungo() -> int:
    return max(_righe(f) for f in CARTELLA_JS.glob("*.js"))


def test_i_documenti_dicono_quante_righe_ha_index_html():
    vero = _righe(INDEX)
    trovati = 0
    for documento in DOCUMENTI:
        for dichiarato in RIGHE_DI_INDEX.findall(documento.read_text(encoding="utf-8")):
            trovati += 1
            assert _numero(dichiarato) == vero, (
                f"{documento.relative_to(RADICE)} dice che index.html ha "
                f"{dichiarato} righe, ma ne ha {vero}. Aggiorna il documento."
            )
    assert trovati >= 3, (
        "la dichiarazione sulle righe di index.html e' sparita dai documenti: "
        f"trovate {trovati} occorrenze su almeno 3 attese. Se il testo e' stato "
        "riscritto, aggiorna anche l'espressione regolare qui sopra — "
        "altrimenti questa guardia non guarda piu' niente."
    )


def test_i_documenti_dicono_quanto_e_lungo_il_file_javascript_piu_lungo():
    vero = _righe_del_js_piu_lungo()
    trovati = 0
    for documento in DOCUMENTI:
        for dichiarato in IL_PIU_LUNGO.findall(documento.read_text(encoding="utf-8")):
            trovati += 1
            assert _numero(dichiarato) == vero, (
                f"{documento.relative_to(RADICE)} dice che il file JavaScript "
                f"piu' lungo ha {dichiarato} righe, ma ne ha {vero}. "
                "Aggiorna il documento."
            )
    assert trovati >= 3, (
        "la dichiarazione sul file JavaScript piu' lungo e' sparita dai "
        f"documenti: trovate {trovati} occorrenze su almeno 3 attese."
    )


def test_le_immagini_dei_documenti_esistono():
    for documento in DOCUMENTI:
        testo = documento.read_text(encoding="utf-8")
        for da_tag, da_markdown in IMMAGINI.findall(testo):
            riferimento = da_tag or da_markdown
            if riferimento.startswith(("http://", "https://", "data:", "#")):
                continue
            percorso = (documento.parent / riferimento).resolve()
            assert percorso.is_file(), (
                f"{documento.relative_to(RADICE)} mostra `{riferimento}`, " "che non esiste."
            )


def test_la_vetrina_del_readme_mostra_una_schermata():
    testo = README.read_text(encoding="utf-8")
    riferimenti = [(da_tag or da_markdown) for da_tag, da_markdown in IMMAGINI.findall(testo)]
    assert any(
        r.startswith("docs/screenshots/") for r in riferimenti
    ), "il README non mostra piu' nessuna schermata del prodotto."
