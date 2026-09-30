"""Nessun file del backend supera le cinquecento righe (issue #196).

Nel frontend il tetto c'era gia', applicato da un test. Nel backend tre file lo
superavano di molto — `skills/registry.py` (854 righe), `api/routes_admin.py`
(889) e `api/app.py` (726) — e sono proprio i posti dove gli agenti della
`0.6.0` avrebbero messo le mani di piu'. Adesso sono divisi per dominio e per
area, e questo test tiene il conto.

Le eccezioni sono elencate **una per una**, con il massimo che possono
raggiungere e il perche', come il debito noto di `test_architettura.py`:

- un file in elenco non puo' crescere oltre il suo massimo;
- un file in elenco che scende sotto il tetto va tolto dall'elenco, e il test
  lo dice: l'elenco puo' solo accorciarsi.
"""

from __future__ import annotations

from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent.parent
SORGENTI = RADICE / "src" / "shinra"
TETTO = 500

# percorso (da `src/shinra/`) -> (massimo, motivo)
ECCEZIONI: dict[str, tuple[int, str]] = {
    "infra/db/depositi.py": (
        710,
        "Fuori dal perimetro della #196, che nomina tre file. Tetto congelato alla misura di oggi. "
        "Spezzarlo in un pacchetto cambierebbe il modo in cui tutto il progetto scrive `depositi.xxx`: "
        "si fa con una scheda sua, non di passaggio.",
    ),
    "services/interview_engine.py": (
        600,
        "Fuori dal perimetro della #196. Tetto congelato. La #209 e la #210 riscrivono il motore "
        "dell'intervista: si divide li', mentre lo si riscrive, non prima.",
    ),
    "services/regole.py": (
        540,
        "Fuori dal perimetro della #196. Tetto congelato alla misura di oggi (534 righe): si divide "
        "la prossima volta che lo si tocca per altro.",
    ),
    "domain/grafo.py": (
        525,
        "Fuori dal perimetro della #196. Tetto congelato alla misura di oggi (520 righe): si divide "
        "la prossima volta che lo si tocca per altro.",
    ),
    "infra/db/modelli.py": (
        515,
        "Fuori dal perimetro della #196. Tetto congelato alla misura di oggi (508 righe): gli schemi "
        "di tutte le tabelle, si divide quando una tabella nuova lo porta oltre.",
    ),
}


def _righe(percorso: Path) -> int:
    return len(percorso.read_text(encoding="utf-8").splitlines())


def _file() -> dict[str, int]:
    return {p.relative_to(SORGENTI).as_posix(): _righe(p) for p in sorted(SORGENTI.rglob("*.py"))}


def test_nessun_file_del_backend_supera_il_tetto_senza_essere_in_elenco():
    sopra = {f: n for f, n in _file().items() if n > TETTO and f not in ECCEZIONI}

    assert sopra == {}, (
        f"file oltre le {TETTO} righe e non in elenco: {sopra}. "
        "Dividili per area, o aggiungili a ECCEZIONI con il motivo — ma prima prova a dividerli."
    )


def test_un_file_in_elenco_non_cresce_oltre_il_suo_massimo():
    righe = _file()
    cresciuti = {
        f: (righe[f], massimo) for f, (massimo, _) in ECCEZIONI.items() if f in righe and righe[f] > massimo
    }

    assert cresciuti == {}, f"file in elenco che hanno superato il loro massimo (righe, massimo): {cresciuti}"


def test_un_file_rientrato_nel_tetto_esce_dall_elenco():
    righe = _file()
    superflue = [f for f in ECCEZIONI if f not in righe or righe[f] <= TETTO]

    assert superflue == [], (
        f"queste eccezioni non servono piu' (il file e' sotto {TETTO} righe o non esiste): {superflue}. "
        "Toglile dall'elenco: e' cosi' che l'elenco si accorcia."
    )


def test_ogni_eccezione_ha_un_motivo():
    senza = [f for f, (_, motivo) in ECCEZIONI.items() if len(motivo.strip()) < 40]

    assert senza == [], f"eccezioni senza una ragione scritta: {senza}"
