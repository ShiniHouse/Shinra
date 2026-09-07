"""Gli strumenti di stile devono essere gli stessi ovunque.

I ganci pre-commit installano la versione fissata in
`.pre-commit-config.yaml`; la CI installa quella dichiarata in
`pyproject.toml`. Finche' i ganci non hanno girato anche in CI, nessuno si e'
accorto che erano diverse: black 24 e black 26 formattano in modo diverso,
quindi lo stesso file risultava a posto per una parte e da riformattare per
l'altra. Un controllo che da' due risposte non e' un controllo.

Riferimento: issue #18.
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent


def _versione_nei_ganci(repository: str) -> str:
    testo = (RADICE / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    trovata = re.search(rf"{re.escape(repository)}\s*\n\s*rev:\s*v?([0-9.]+)", testo)
    assert trovata, f"{repository} non compare in .pre-commit-config.yaml"
    return trovata.group(1)


def _versione_in_pyproject(pacchetto: str) -> str:
    testo = (RADICE / "pyproject.toml").read_text(encoding="utf-8")
    trovata = re.search(rf'"{pacchetto}==([0-9.]+)"', testo)
    assert trovata, (
        f"{pacchetto} in pyproject.toml deve essere fissato con `==`, non con `>=`: "
        "un minimo lascia che la CI installi una versione diversa da quella dei ganci"
    )
    return trovata.group(1)


def test_ruff_e_la_stessa_versione_ovunque():
    assert _versione_nei_ganci("astral-sh/ruff-pre-commit") == _versione_in_pyproject("ruff")


def test_black_e_la_stessa_versione_ovunque():
    assert _versione_nei_ganci("psf/black") == _versione_in_pyproject("black")
