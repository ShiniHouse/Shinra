"""La radice del progetto si calcola in un posto solo.

Nove moduli se la calcolavano da soli con `Path(__file__)` e una catena di
`.parent` lunga quanto la loro posizione nell'albero. Il numero giusto
dipendeva da dove stava il file, e nessuno lo diceva.

Il punto non e' l'eleganza. Sbagliare quel numero non solleva niente:
`DATA_DIR` punta una cartella che non esiste, `mkdir(parents=True)` la crea,
e il servizio riparte con un database vuoto — nessun errore, solo la casa
che ha dimenticato tutto. Con lo spostamento sotto `src/shinra/` (issue #16)
la profondita' di ogni modulo cambia: nove numeri da correggere a mano sono
nove occasioni di sbagliare in silenzio, e questo file impedisce che
tornino.

Riferimento: issue #16.
"""

from __future__ import annotations

import re
from pathlib import Path

from core import percorsi

RADICE_VERA = Path(__file__).resolve().parent.parent.parent


# ------------------------------------------------------------- dove punta


def test_la_radice_e_la_cartella_del_progetto():
    assert percorsi.RADICE == RADICE_VERA
    assert (percorsi.RADICE / "pyproject.toml").exists()


def test_ogni_percorso_sta_dentro_la_radice():
    """Un percorso che esce dalla radice e' il sintomo di una catena
    sbagliata: `parent` di troppo e si finisce nella cartella superiore, che
    in produzione e' `/opt` e in sviluppo e' la cartella di casa."""
    nomi = [n for n in dir(percorsi) if n.isupper() and isinstance(getattr(percorsi, n), Path)]
    assert nomi, "nessun percorso esposto: il test non guarda piu' niente"

    for nome in nomi:
        valore = getattr(percorsi, nome)
        if nome == "RADICE":
            continue
        assert percorsi.RADICE in valore.parents, f"{nome} esce dalla radice: {valore}"


def test_le_cartelle_che_devono_esistere_esistono():
    assert percorsi.CONFIGURAZIONE.is_dir()
    assert percorsi.MODELLI_HTML.is_dir()
    assert percorsi.STATICI.is_dir()


def test_la_variabile_di_ambiente_ha_la_precedenza(monkeypatch, tmp_path):
    """Serve a chi installa il pacchetto sul serio e tiene i dati altrove."""
    monkeypatch.setenv("SHINRA_RADICE", str(tmp_path))

    assert percorsi._radice() == tmp_path.resolve()


def test_senza_variabile_si_risale_fino_al_segnale(monkeypatch):
    monkeypatch.delenv("SHINRA_RADICE", raising=False)

    assert percorsi._radice() == RADICE_VERA


# ------------------------------------------- e nessun altro se la ricalcola


# Questi tre trovano la radice *per poterla mettere in `sys.path`*: devono
# farlo prima di poter importare qualunque cosa del progetto, quindi non
# possono chiedere a `core.percorsi`. E' un avvio, non un percorso di dati.
# Dopo la #16 il pacchetto sara' installato e spariranno anche loro.
AVVIO = {
    "core/percorsi.py",
    "migrazioni/env.py",
    "scripts/esporta_json.py",
    "scripts/imposta_pin.py",
    "scripts/import_backlog.py",
    "scripts/migra_da_json.py",
}

CATENA = re.compile(r"Path\(__file__\)\.resolve\(\)(?:\.parent)+")


def test_nessun_modulo_calcola_la_radice_per_conto_suo():
    colpevoli = []
    for file in sorted(RADICE_VERA.glob("**/*.py")):
        relativo = file.relative_to(RADICE_VERA).as_posix()
        if relativo in AVVIO or relativo.startswith((".venv/", "tests/", "build/")):
            continue
        if CATENA.search(file.read_text(encoding="utf-8")):
            colpevoli.append(relativo)

    assert colpevoli == [], (
        "questi moduli si calcolano la radice da soli invece di chiederla a " f"core.percorsi: {colpevoli}"
    )


def test_percorsi_non_dipende_da_niente_del_progetto():
    """`config.settings` lo importa: se un giorno importasse `config`
    indietro, l'applicazione non partirebbe piu' e il messaggio parlerebbe
    di import circolari invece che di percorsi."""
    testo = (RADICE_VERA / "core" / "percorsi.py").read_text(encoding="utf-8")

    interni = re.findall(r"^\s*(?:from|import)\s+(core|config|server|integrations)\b", testo, re.M)
    assert interni == [], f"core/percorsi.py importa dal progetto: {interni}"
