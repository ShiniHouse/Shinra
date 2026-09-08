"""Ogni file del backlog dice qual e' la sua issue, e lo dice giusto.

I file di `docs/backlog/` diventano issue su GitHub, e il numero lo assegna
GitHub — non lo decidiamo noi. Finora l'unico riferimento era il numero nel
nome del file, che pero' e' soltanto un ordinamento: coincideva con quello
della issue solo perche' la prima importazione era andata in ordine.

Poi sono stati aggiunti tre file dopo quella importazione, e i numeri si sono
separati. `docs/backlog/v0.2.0/19-ruoli-e-permessi.md` e' diventata la issue
**#46**, mentre la #19 era gia' un'altra cosa: la connessione WebSocket a Home
Assistant, della v0.3.0. Due commit hanno scritto `Closes #19` e `Closes #20`
intendendo i file, e hanno chiuso come completate due issue della v0.3.0 che
nessuno aveva iniziato. Sono rimaste chiuse per giorni, e la milestone
v0.2.0 sembrava indietro mentre la v0.3.0 sembrava avviata.

Adesso il numero sta nell'intestazione, `import_backlog.py` ce lo scrive da
solo dopo aver creato la issue, e questo file impedisce che torni a divergere.

Riferimento: issue #16 (lo spostamento che ha portato a rileggere tutto).
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
BACKLOG = RADICE / "docs" / "backlog"


def schede() -> list[Path]:
    return sorted(f for f in BACKLOG.rglob("*.md") if f.name != "README.md")


def intestazione(percorso: Path) -> dict[str, str]:
    testo = percorso.read_text(encoding="utf-8")
    assert testo.startswith("---"), f"{percorso.name}: manca l'intestazione"
    testa = testo.split("---", 2)[1]
    campi = {}
    for riga in testa.strip().splitlines():
        if ":" in riga:
            chiave, valore = riga.split(":", 1)
            campi[chiave.strip()] = valore.strip().strip('"')
    return campi


def test_ci_sono_delle_schede():
    """Se la cartella cambia nome, tutto il resto smette di guardare."""
    assert len(schede()) > 30


def test_ogni_scheda_dichiara_il_numero_della_sua_issue():
    senza = [f.relative_to(BACKLOG).as_posix() for f in schede() if "issue" not in intestazione(f)]

    assert senza == [], (
        "queste schede non dicono a quale issue corrispondono: aggiungi `issue: NN` "
        f"all'intestazione — {senza}"
    )


def test_due_schede_non_puntano_alla_stessa_issue():
    visti: dict[str, str] = {}
    doppie = []
    for f in schede():
        numero = intestazione(f).get("issue")
        nome = f.relative_to(BACKLOG).as_posix()
        if numero in visti:
            doppie.append(f"#{numero}: {visti[numero]} e {nome}")
        visti[numero] = nome

    assert doppie == [], f"schede diverse che rivendicano la stessa issue: {doppie}"


def test_il_numero_nel_nome_del_file_e_quello_della_issue():
    """Il nome del file e l'intestazione devono dire la stessa cosa.

    Non e' pignoleria: finche' i due numeri coincidono, chi legge `19-...md`
    e scrive «issue #19» in un commento ha ragione. Quando divergono in
    silenzio, ha torto e non lo sa nessuno — ed e' esattamente cio' che e'
    successo.
    """
    disallineate = []
    for f in schede():
        prefisso = re.match(r"^(\d+)-", f.name)
        if not prefisso:
            continue
        dichiarato = intestazione(f).get("issue")
        # I file della v0.1.0 hanno il prefisso a due cifre («01-»): si
        # confrontano i numeri, non il modo in cui sono scritti.
        if dichiarato is None or int(dichiarato) != int(prefisso.group(1)):
            disallineate.append(f"{f.relative_to(BACKLOG).as_posix()} dichiara issue {dichiarato}")

    assert disallineate == [], (
        "il numero nel nome del file non e' quello della issue: rinomina il file, "
        f"non l'intestazione — {disallineate}"
    )
