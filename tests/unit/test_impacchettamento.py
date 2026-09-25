"""Cio' che non e' `.py` deve entrare nel pacchetto, o esiste solo qui.

I test girano sul sorgente, e `pip install -e .` lascia il pacchetto dov'e':
in sviluppo un file di dati accanto al codice si trova sempre. Un'installazione
vera — `pip install .`, che e' quella dell'immagine Docker — copia invece solo
i `.py` piu' cio' che `package-data` dichiara.

Il difetto che ha fatto nascere questo file: `services/intenti/lingue/it.yaml`,
gli schemi con cui Shinra capisce una frase, non era dichiarato. Nell'immagine
Shinra sarebbe partita, avrebbe risposto 200, avrebbe lasciato entrare — e poi
**nessun intento** avrebbe funzionato. Nemmeno il lavoro della CI che avvia
l'immagine e prova ad accedere se ne sarebbe accorto: quel file si legge alla
prima frase, non all'avvio.

Il `pyproject.toml` si legge con un'espressione regolare e non con `tomllib`:
quello esiste dal 3.11, e la CI prova anche il 3.10. E' gia' costato un giro
rosso una volta.

Riferimento: issue #36.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
PACCHETTO = RADICE / "src" / "shinra"
PYPROJECT = RADICE / "pyproject.toml"

# Roba di lavorazione, non file del pacchetto.
IGNORATI = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")


def _dichiarati() -> list[str]:
    """Gli schemi elencati sotto `[tool.setuptools.package-data]` per `shinra`."""
    testo = PYPROJECT.read_text(encoding="utf-8")
    sezione = re.search(r"^\[tool\.setuptools\.package-data\]\s*\n(.*?)(?=^\[|\Z)", testo, re.M | re.S)
    assert sezione, "`pyproject.toml` non dichiara piu' nessun file di dati del pacchetto"

    riga = re.search(r"^\s*shinra\s*=\s*\[(.*?)\]", sezione.group(1), re.M | re.S)
    assert riga, "la voce `shinra` e' sparita da `package-data`"
    return re.findall(r'"([^"]+)"', riga.group(1))


def _non_python() -> list[Path]:
    return sorted(
        f
        for f in PACCHETTO.rglob("*")
        if f.is_file() and f.suffix != ".py" and not any(p in f.parts for p in IGNORATI)
    )


def test_ogni_file_non_python_del_pacchetto_e_dichiarato():
    """Il difetto, scritto come guardia.

    Si confrontano i file veri con gli schemi dichiarati, non con un elenco
    scritto a mano: un file nuovo entra in questo controllo il giorno che
    nasce, non il giorno che qualcuno si ricorda di aggiungerlo.
    """
    schemi = _dichiarati()
    file = _non_python()
    assert file, "nessun file di dati nel pacchetto: la guardia non guarda piu' niente"

    scoperti = []
    for percorso in file:
        relativo = percorso.relative_to(PACCHETTO).as_posix()
        if not any(fnmatch.fnmatch(relativo, schema) for schema in schemi):
            scoperti.append(relativo)

    assert scoperti == [], (
        "questi file non entrano in un'installazione vera — `pip install .` li "
        "lascia fuori, e in produzione mancano senza che niente lo dica: "
        f"{scoperti}. Dichiarali in `[tool.setuptools.package-data]`."
    )


def test_nessuno_schema_dichiarato_resta_senza_file():
    """L'altro verso: uno schema che non prende piu' niente e' una riga che
    dice una cosa non vera, e il giorno che serve davvero nessuno si fida."""
    file = [f.relative_to(PACCHETTO).as_posix() for f in _non_python()]
    vuoti = [s for s in _dichiarati() if not any(fnmatch.fnmatch(f, s) for f in file)]
    assert vuoti == [], f"schemi di `package-data` che non prendono nessun file: {vuoti}"


def test_la_lingua_di_ripiego_e_dentro_il_pacchetto():
    """La piu' importante delle due, detta per nome.

    Senza l'italiano Shinra non capisce nessuna frase: il caricatore ripiega
    su `it` quando la lingua configurata non c'e', e se manca anche quello
    solleva. In un'immagine dove il file non e' entrato, ogni richiesta che
    passa da un intento diventa un errore.
    """
    schemi = _dichiarati()
    relativo = "services/intenti/lingue/it.yaml"
    assert (PACCHETTO / relativo).is_file(), "l'italiano non c'e' piu' nel sorgente"
    assert any(fnmatch.fnmatch(relativo, s) for s in schemi), (
        "l'italiano non entra in un'installazione vera: Shinra partirebbe, "
        "risponderebbe 200, e non capirebbe piu' nessuna frase"
    )
