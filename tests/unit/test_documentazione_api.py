"""Il riferimento delle API dice quello che il server risponde (issue #38).

`docs/API.md` non si scrive: lo genera `scripts/genera_api.py` leggendo le
rotte vere. Questi test tengono due promesse:

- il file nel repository coincide con quello che lo script produrrebbe adesso
  (aggiungere una rotta senza rigenerarlo fa fallire la suite);
- ogni rotta dice cosa fa, e chi la puo' chiamare e' quello che il codice
  impone davvero, non quello che qualcuno ricorda.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent
SCRIPT = RADICE / "scripts" / "genera_api.py"
DOCUMENTO = RADICE / "docs" / "API.md"


@pytest.fixture(scope="module")
def genera_api():
    spec = importlib.util.spec_from_file_location("genera_api", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_il_riferimento_nel_repository_e_aggiornato(genera_api):
    atteso = genera_api.genera()
    attuale = DOCUMENTO.read_text(encoding="utf-8")

    assert attuale == atteso, (
        "docs/API.md e' rimasto indietro rispetto alle rotte: "
        "esegui  python scripts/genera_api.py  e includi il file nella modifica"
    )


def test_il_riferimento_non_e_quasi_vuoto(genera_api):
    """Se FastAPI cambiasse la forma con cui tiene i router inclusi, il
    generatore non troverebbe piu' le rotte e scriverebbe un file quasi vuoto
    — che poi coinciderebbe con se stesso, e il test di sopra resterebbe
    verde. Questo no."""
    righe = genera_api.righe()

    assert len(righe) > 60, f"rotte trovate: {len(righe)}"
    percorsi = {percorso for _, _, percorso, _, _ in righe}
    for atteso in ("/api/chat", "/api/users", "/api/regole", "/api/auth/login", "/api/alexa"):
        assert atteso in percorsi, f"{atteso} non compare nel riferimento"


def test_ogni_rotta_dice_cosa_fa(genera_api):
    senza = [
        f"{metodo} {percorso}" for _, metodo, percorso, _, riassunto in genera_api.righe() if not riassunto
    ]

    assert senza == [], (
        f"rotte senza una riga di spiegazione: {senza}. "
        "La riga e' la prima frase della documentazione della funzione che risponde."
    )


def test_le_rotte_pubbliche_sono_quelle_dichiarate(genera_api):
    """Una rotta pubblica e' una scelta, e l'elenco completo deve stare in una
    riga che si legge: se un'altra ci entra per distrazione, qui si vede."""
    pubbliche = sorted(f"{m} {p}" for _, m, p, chi, _ in genera_api.righe() if chi == "pubblica")

    attese_fra_le_pubbliche = {"POST /api/auth/login", "GET /health", "POST /api/alexa"}
    assert attese_fra_le_pubbliche <= set(pubbliche), "manca una rotta pubblica che deve esserlo"

    sensibili = ("/api/users", "/api/settings", "/api/knowledge", "/api/aliases", "/api/modes", "/api/regole")
    trapelate = [r for r in pubbliche if any(f" {s}" in r for s in sensibili)]
    assert trapelate == [], f"rotte sensibili senza autenticazione: {trapelate}"


def test_i_permessi_del_riferimento_esistono_davvero(genera_api):
    """La colonna «Chi» legge il permesso dalla dipendenza. Se il nome non
    fosse uno di quelli del catalogo, la rotta starebbe proteggendo da un
    permesso che nessun ruolo ha: sarebbe chiusa a tutti tranne a chi ha `*`."""
    from shinra.services import permessi

    catalogo = {
        getattr(permessi, n) for n in dir(permessi) if n.isupper() and isinstance(getattr(permessi, n), str)
    }
    citati = set()
    for _, _, _, chi, _ in genera_api.righe():
        if chi.startswith("permesso "):
            citati |= {p.strip("` ") for p in chi.removeprefix("permesso ").split(",")}

    sconosciuti = sorted(citati - catalogo)
    assert sconosciuti == [], f"permessi citati che non sono nel catalogo: {sconosciuti}"
