"""Il registro delle decisioni dice la verita' su se stesso.

Gli ADR servono a rispondere fra sei mesi a «perche' e' fatto cosi'?». Ma un
indice scritto a mano invecchia in silenzio come ogni altro dato scritto a
mano: l'**0005** — SQLAlchemy sincrono — e' stato scritto, salvato, e non e'
mai entrato nella tabella del README. Per settimane il registro ha dichiarato
quattro decisioni su cinque, e chi cercava «perche' non async?» non trovava
niente e concludeva che nessuno ci avesse pensato.

E' la stessa forma della #158, che rese rumorosi i numeri misurati nei
documenti. Qui i dati sono i file stessi.

Riferimento: issue #34 (l'ADR 0006 e' quello che ha fatto scoprire il buco).
"""

from __future__ import annotations

import re
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
CARTELLA = RADICE / "docs" / "adr"
INDICE = CARTELLA / "README.md"

# `| [0003](0003-scheduler-persistente.md) | Titolo | Accettato |`
RIGA = re.compile(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|([^|]*)\|\s*([^|]*?)\s*\|", re.M)

STATI = ("Accettato", "Proposto")


def _schede() -> list[Path]:
    return sorted(f for f in CARTELLA.glob("*.md") if f.name != "README.md")


def _nell_indice() -> dict[str, tuple[str, str, str]]:
    """Dal numero alla terna (file, titolo, stato), come la dichiara l'indice."""
    return {
        numero: (percorso.strip(), titolo.strip(), stato)
        for numero, percorso, titolo, stato in RIGA.findall(INDICE.read_text(encoding="utf-8"))
    }


def _intestazione(percorso: Path) -> tuple[str, str]:
    """Il titolo e lo stato come li dichiara la scheda stessa."""
    testo = percorso.read_text(encoding="utf-8")
    titolo = re.search(r"^#\s*\d{4}\s*—\s*(.+)$", testo, re.M)
    stato = re.search(r"^-\s*\*\*Stato:\*\*\s*(.+?)\s*$", testo, re.M)
    assert titolo, f"{percorso.name}: manca il titolo `# NNNN — ...`"
    assert stato, f"{percorso.name}: manca la riga dello stato"
    return titolo.group(1).strip(), stato.group(1).strip()


def test_ci_sono_delle_decisioni():
    """Se la cartella cambia nome, tutto il resto smette di guardare."""
    assert len(_schede()) >= 5, f"schede trovate: {[f.name for f in _schede()]}"
    assert len(_nell_indice()) >= 5, "l'indice non elenca piu' niente"


def test_ogni_decisione_sta_nell_indice():
    """Il difetto vero: l'0005 c'era sul disco e non nell'indice."""
    indice = _nell_indice()
    mancanti = [f.name for f in _schede() if f.name[:4] not in indice]
    assert mancanti == [], (
        f"queste decisioni esistono ma il registro non le elenca: {mancanti}. "
        "Chi cerca il perche' di una scelta non le trova, e conclude che "
        "nessuno ci abbia pensato."
    )


def test_l_indice_non_elenca_decisioni_che_non_esistono():
    fantasmi = [
        f"#{numero} -> {percorso}"
        for numero, (percorso, _, _) in _nell_indice().items()
        if not (CARTELLA / percorso).is_file()
    ]
    assert fantasmi == [], f"l'indice punta a file che non ci sono: {fantasmi}"


def test_l_indice_dice_il_titolo_e_lo_stato_veri():
    """Un indice puo' invecchiare anche restando completo: basta che una
    decisione passi a «Sostituito da» e la tabella continui a dirla accettata.
    Titolo e stato si leggono dalla scheda, non si riscrivono qui."""
    indice = _nell_indice()
    sbagliati = []
    for scheda in _schede():
        numero = scheda.name[:4]
        if numero not in indice:
            continue
        _, titolo_indice, stato_indice = indice[numero]
        titolo_vero, stato_vero = _intestazione(scheda)
        if titolo_indice != titolo_vero:
            sbagliati.append(f"#{numero}: l'indice dice «{titolo_indice}», la scheda «{titolo_vero}»")
        if stato_indice != stato_vero:
            sbagliati.append(f"#{numero}: l'indice dice «{stato_indice}», la scheda «{stato_vero}»")

    assert sbagliati == [], sbagliati


def test_nessun_numero_e_usato_due_volte():
    """«Numerazione progressiva a quattro cifre, mai riutilizzata», dice il
    registro di se stesso. Due schede con lo stesso numero renderebbero
    ambiguo ogni riferimento gia' scritto altrove."""
    numeri = [f.name[:4] for f in _schede()]
    assert len(numeri) == len(set(numeri)), f"numeri ripetuti: {numeri}"


def test_ogni_decisione_dichiara_uno_stato_previsto():
    strani = []
    for scheda in _schede():
        _, stato = _intestazione(scheda)
        if stato not in STATI and not stato.startswith("Sostituito da "):
            strani.append(f"{scheda.name}: stato «{stato}»")
    assert strani == [], f"stati non previsti dal registro: {strani}"
