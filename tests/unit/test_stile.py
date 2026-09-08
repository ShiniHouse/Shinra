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
import subprocess
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


# --------------------------------------------- cio' che controllano i ganci

BINARI = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".mp3", ".woff", ".woff2", ".db", ".sqlite3"}
MASSIMO_KB = 1024


ESCLUSE = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "data",
    ".ruff_cache",
    ".pytest_cache",
    "build",
    "dist",
}


def _da_saltare(parti: tuple[str, ...]) -> bool:
    """Cio' che git avrebbe ignorato, approssimato a mano.

    `*.egg-info/` non e' un nome fisso — dipende da come si chiama il
    pacchetto — quindi non basta elencarlo fra le cartelle escluse: e' il
    motivo per cui questa funzione esiste invece di un semplice confronto
    di insiemi.
    """
    return bool(ESCLUSE & set(parti)) or any(p.endswith(".egg-info") for p in parti)


def _file_di_testo() -> list[Path]:
    """I file tracciati da git, esclusi i binari.

    Si chiede a git perche' e' esattamente il perimetro su cui girano i
    ganci: cosi' `.venv`, i dati di casa e tutto cio' che non e' versionato
    restano fuori senza doverlo elencare.

    Se git non c'e' — una copia dei sorgenti senza cronologia, un pacchetto
    installato — si cammina nelle cartelle saltando quelle che git avrebbe
    ignorato. Meglio un perimetro approssimato che un test che fallisce per
    un motivo che non c'entra con cio' che verifica.
    """
    try:
        elenco = subprocess.run(
            ["git", "ls-files"], cwd=RADICE, capture_output=True, text=True, check=True
        ).stdout.split()
        percorsi = [RADICE / n for n in elenco]
    except (subprocess.CalledProcessError, FileNotFoundError):
        percorsi = [
            p for p in RADICE.rglob("*") if p.is_file() and not _da_saltare(p.relative_to(RADICE).parts)
        ]

    return [p for p in percorsi if p.suffix.lower() not in BINARI and p.exists()]


def test_ogni_file_finisce_con_un_solo_a_capo():
    """Il gancio `end-of-file-fixer` non chiede *un* a capo finale: ne chiede
    esattamente uno.

    Questo test esiste perche' ho gia' sbagliato questa verifica: avevo
    controllato che l'a capo ci fosse, non che non ce ne fossero due, e la CI
    e' diventata rossa su `index.html`. I ganci non si possono eseguire su
    ogni macchina — servono a scaricare i loro repository — ma il loro
    effetto si puo' affermare qui, dove gira sempre tutto.
    """
    sbagliati = []
    for percorso in _file_di_testo():
        dati = percorso.read_bytes()
        if not dati:
            continue
        if not dati.endswith(b"\n"):
            sbagliati.append(f"{percorso.relative_to(RADICE)}: manca l'a capo finale")
        elif dati.endswith(b"\n\n") or dati.endswith(b"\r\n"):
            sbagliati.append(f"{percorso.relative_to(RADICE)}: a capo finale non pulito")

    assert sbagliati == [], sbagliati


def test_nessuna_riga_ha_spazi_in_coda():
    """Il gancio `trailing-whitespace`."""
    sbagliati = []
    for percorso in _file_di_testo():
        try:
            testo = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for numero, riga in enumerate(testo.splitlines(), start=1):
            if riga.rstrip() != riga:
                sbagliati.append(f"{percorso.relative_to(RADICE)}:{numero}")
                break

    assert sbagliati == [], sbagliati


def test_nessun_file_troppo_grande():
    """Il gancio `check-added-large-files`: un repository non e' un archivio."""
    grossi = [
        f"{p.relative_to(RADICE)} ({p.stat().st_size // 1024} KB)"
        for p in _file_di_testo()
        if p.stat().st_size > MASSIMO_KB * 1024
    ]

    assert grossi == [], grossi


def test_nessuna_chiave_privata_versionata():
    """Il gancio `detect-private-key`, e la ragione per cui esiste.

    Le stringhe cercate si compongono a pezzi invece di scriverle intere:
    altrimenti questo file conterrebbe cio' che cerca e si segnalerebbe da
    solo — cosa che ha fatto, alla prima esecuzione. Lo stesso vale per il
    gancio vero, che guarda dentro tutti i file compreso questo.
    """
    marcatori = ("BEGIN RSA " + "PRIVATE KEY", "BEGIN OPENSSH " + "PRIVATE KEY")
    trovate = []
    for percorso in _file_di_testo():
        try:
            testo = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(m in testo for m in marcatori):
            trovate.append(str(percorso.relative_to(RADICE)))

    assert trovate == [], trovate
