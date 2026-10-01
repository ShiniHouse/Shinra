"""La vetrina del progetto: le immagini che i documenti citano esistono davvero.

Una versione precedente di questo file controllava anche che i documenti dicessero
quante righe ha `index.html` e quanto e' lungo il file JavaScript piu' lungo. Nasceva da
un difetto vero: la `ROADMAP` ha detto per settimane che `index.html` era di 7.438 righe,
molto dopo che era stato scomposto. Ma la cura era peggiore del male: ogni modifica al
frontend obbligava a riscrivere lo stesso numero in quattro documenti, per un dato che il
codice stesso sa dire meglio. I documenti ora non scrivono piu' numeri che cambiano a ogni
commit: dicono la proprieta' («nessun file oltre le cinquecento righe»), e la proprieta' ha
una guardia vera (`test_nessun_pezzo_del_frontend_supera_le_cinquecento_righe`).

Resta il controllo che conta per chi apre il progetto: un `<img>` rotto nel README e' la
prima cosa che vede, e nessuno se ne accorge finche' non la vede qualcun altro.
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
README = RADICE / "README.md"
ROADMAP = RADICE / "docs" / "ROADMAP.md"
STORIA = RADICE / "docs" / "storia-delle-fasi.md"

DOCUMENTI = (README, ROADMAP, STORIA)


# Sia `<img src="...">` sia `![...](...)`.
IMMAGINI = re.compile(r"<img[^>]*\bsrc=\"([^\"]+)\"|!\[[^\]]*\]\(([^)]+)\)")


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
