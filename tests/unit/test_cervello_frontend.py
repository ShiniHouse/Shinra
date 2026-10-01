"""Il motore e il disegno del Cervello, provati senza browser dove si puo' (issue #186).

Il layout (`cervello_fisica.js`) non tocca il DOM, quindi gira sotto `node`: si
puo' dire con certezza che e' deterministico, che si assesta e che dispone i nodi
a gruppi. Il resto — il canvas, il clic, la tastiera — lo prova un browser vero in
`tests/gesti/cervello.spec.mjs`.

Qui stanno anche le due guardie sul codice che nessun browser vede:

- niente indirizzi esterni: la casa non deve dipendere da internet per disegnarsi;
- il nome di un nodo non diventa mai markup nel canvas.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent.parent
JS = RADICE / "web" / "static" / "js"
FILE_DEL_CERVELLO = ("cervello.js", "cervello_disegno.js", "cervello_fisica.js", "cervello_stile.js")


def _node(programma: str) -> dict:
    if shutil.which("node") is None:
        pytest.skip("node non disponibile: in CI c'e'")
    modulo = (JS / "cervello_fisica.js").as_uri()
    codice = f"import * as f from {json.dumps(modulo)};\n{programma}"
    esito = subprocess.run(
        ["node", "--input-type=module", "-e", codice], capture_output=True, text=True, check=False, timeout=60
    )
    assert esito.returncode == 0, esito.stderr
    return json.loads(esito.stdout.strip().splitlines()[-1])


PREPARA = """
const clusters = ['a', 'b', 'c', 'd'].map((id) => ({ id }));
const nodi = [];
for (const c of clusters) for (let i = 0; i < 40; i++) nodi.push({ id: c.id + i, cluster: c.id });
const cavi = nodi.filter((_, i) => i % 3 === 0).map((n, i, tutti) => ({ da: n.id, a: tutti[(i + 1) % tutti.length].id }));
const disposto = () => f.disponi(f.creaSimulazione(nodi, cavi, clusters, { larghezza: 900, altezza: 600 }));
"""


def test_lo_stesso_grafo_si_dispone_sempre_allo_stesso_modo():
    """Una scheda che cambia faccia a ogni apertura non si impara."""
    visto = _node(PREPARA + """
const a = disposto(), b = disposto();
console.log(JSON.stringify({ uguali: a.punti.every((p, i) => p.x === b.punti[i].x && p.y === b.punti[i].y) }));
""")
    assert visto["uguali"] is True


def test_si_assesta_e_non_produce_numeri_impossibili():
    visto = _node(PREPARA + """
const s = disposto();
console.log(JSON.stringify({
    quieta: f.quieta(s),
    nonNumeri: s.punti.some((p) => !Number.isFinite(p.x) || !Number.isFinite(p.y)),
    quanti: s.punti.length,
}));
""")
    assert visto == {"quieta": True, "nonNumeri": False, "quanti": 160}


def test_i_nodi_di_un_cluster_stanno_vicini_al_loro_centro():
    """E' cio' che fa leggere il grafo come gruppi con un nome: la distanza media
    dal centro del proprio cluster deve essere molto minore di quella dai centri
    degli altri."""
    visto = _node(PREPARA + """
const s = disposto();
let proprio = 0, altrui = 0, nAltrui = 0;
for (const p of s.punti) {
    for (const [id, c] of Object.entries(s.centri)) {
        const d = Math.hypot(p.x - c.x, p.y - c.y);
        if (id === p.nodo.cluster) proprio += d; else { altrui += d; nAltrui++; }
    }
}
console.log(JSON.stringify({ proprio: proprio / s.punti.length, altrui: altrui / nAltrui }));
""")
    assert visto["proprio"] * 2 < visto["altrui"], visto


def test_un_nodo_fisso_non_si_muove():
    """Quello che si sta trascinando non deve scappare da sotto il dito."""
    visto = _node(PREPARA + """
const s = f.creaSimulazione(nodi, cavi, clusters);
const p = s.punti[0]; p.fisso = true; const x = p.x, y = p.y;
for (let i = 0; i < 80; i++) f.passo(s);
console.log(JSON.stringify({ fermo: p.x === x && p.y === y }));
""")
    assert visto["fermo"] is True


def test_due_nodi_sullo_stesso_punto_si_separano_senza_numeri_impossibili():
    visto = _node("""
const s = f.creaSimulazione([{ id: 'x', cluster: 'a' }, { id: 'y', cluster: 'a' }], [], [{ id: 'a' }]);
s.punti.forEach((p) => { p.x = 100; p.y = 100; });
for (let i = 0; i < 60; i++) f.passo(s);
console.log(JSON.stringify({ separati: Math.hypot(s.punti[0].x - s.punti[1].x, s.punti[0].y - s.punti[1].y) > 1,
    finiti: s.punti.every((p) => Number.isFinite(p.x)) }));
""")
    assert visto == {"separati": True, "finiti": True}


def test_le_frecce_scelgono_il_vicino_nella_direzione_giusta():
    visto = _node("""
const nodi = [{ id: 'c', cluster: 'a' }, { id: 'dx', cluster: 'a' }, { id: 'sx', cluster: 'a' }, { id: 'su', cluster: 'a' }];
const s = f.creaSimulazione(nodi, [], [{ id: 'a' }]);
const pos = { c: [0, 0], dx: [50, 5], sx: [-60, 0], su: [0, -40] };
s.punti.forEach((p) => { [p.x, p.y] = pos[p.id]; });
const da = s.perId.get('c');
console.log(JSON.stringify({
    destra: f.vicinoVerso(s, da, 'destra')?.id, sinistra: f.vicinoVerso(s, da, 'sinistra')?.id,
    su: f.vicinoVerso(s, da, 'su')?.id, giu: f.vicinoVerso(s, da, 'giu')?.id ?? null,
}));
""")
    assert visto == {"destra": "dx", "sinistra": "sx", "su": "su", "giu": None}


def test_il_cervello_non_chiede_niente_a_host_esterni():
    """«La casa non deve dipendere da internet per disegnarsi»: nessun indirizzo
    http(s) nel codice, ne' una libreria caricata da un CDN. Si guarda il codice
    senza commenti, perche' un commento puo' nominare un sito."""
    colpevoli = []
    for nome in FILE_DEL_CERVELLO:
        codice = (JS / nome).read_text(encoding="utf-8")
        codice = re.sub(r"/\*.*?\*/", "", codice, flags=re.S)
        codice = "\n".join(
            riga.split("//", 1)[0] if "http" not in riga.split("//", 1)[0] else riga
            for riga in codice.splitlines()
        )
        for trovato in re.findall(r"https?://[^\s'\"`)]+", codice):
            colpevoli.append(f"{nome}: {trovato}")

    assert colpevoli == [], f"il Cervello nomina host esterni: {colpevoli}"


def test_il_canvas_scrive_testo_e_mai_markup():
    """Un nome di dispositivo come `<img onerror=...>` e' una stringa qualunque:
    nel disegno passa da `fillText`, e non esiste nessun `innerHTML` ne'
    `insertAdjacentHTML` in cui possa diventare codice."""
    disegno = (JS / "cervello_disegno.js").read_text(encoding="utf-8")
    codice = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", disegno, flags=re.S))

    assert "fillText" in codice
    assert "innerHTML" not in codice and "insertAdjacentHTML" not in codice and "outerHTML" not in codice


def test_nessun_file_del_cervello_supera_le_cinquecento_righe():
    lunghi = {n: len((JS / n).read_text(encoding="utf-8").splitlines()) for n in FILE_DEL_CERVELLO}

    assert all(righe <= 500 for righe in lunghi.values()), lunghi
