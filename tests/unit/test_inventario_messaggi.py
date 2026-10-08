"""L'inventario dei messaggi italiani negli strumenti (#207).

Gli strumenti che il modello chiama (`skills/`) restituiscono frasi italiane scritte nel codice. Il modello le rilegge e
di solito le traduce, ma quando una frase arriva alla persona cosi' com'e' resta italiana. Questo test **le conta**.

E' un debito che cala, non un divieto: ogni file ha il numero di frasi che aveva quando e' nato l'inventario, e il test
fallisce se il numero **sale** (una frase italiana nuova in uno strumento) e **anche se scende** senza che qui si scriva
(cosi' il tetto si abbassa e non si risale). Il giorno che tutti sono a zero, la regola diventa assoluta.

Cosa conta come «un messaggio che arriva alla persona»: la stringa passata a `_riuscito(...)`/`_fallito(...)`, e il valore
delle chiavi `message`, `messaggio`, `error`, `errore` di un dizionario restituito. Cosa conta come italiano: una parola
italiana comune (non, sono, della...) o una lettera accentata.
"""

import ast
import re
from pathlib import Path

from shinra import percorsi

SKILLS = percorsi.RADICE / "src" / "shinra" / "skills"

CHIAMATE = {"_riuscito", "_fallito"}
CHIAVI = {"message", "messaggio", "error", "errore"}

# Parole che un testo inglese non ha e che uno italiano ha quasi sempre; piu' le lettere accentate.
ITALIANO = re.compile(
    r"\b(non|sono|della|delle|del|dei|nel|nella|per|con|che|una|uno|il|lo|la|le|gli|di|da|in|ho|hai|puoi|dimmi|"
    r"nessun|nessuna|trovo|riesco|serratura|chiusa|aperta|luce|casa|dispositivo|azione|prevista|stato|"
    r"troppo|gia|piu|quale|quali|aprire|chiudere|riuscito|riferisci|impostato|ricordero|segnato|scadenza)\b"
    r"|[àèéìòù]",
    re.IGNORECASE,
)


def _testo(nodo: ast.AST) -> str:
    """Le parti fisse di una stringa, anche se e' una f-string o una somma di stringhe."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return nodo.value
    if isinstance(nodo, ast.JoinedStr):
        return " ".join(_testo(v) for v in nodo.values if isinstance(v, ast.Constant))
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Add):
        return _testo(nodo.left) + " " + _testo(nodo.right)
    return ""


def messaggi_italiani(file: Path) -> list[tuple[int, str]]:
    """Le frasi italiane che questo file restituisce alla persona: (riga, testo)."""
    albero = ast.parse(file.read_text(encoding="utf-8"))
    trovati: dict[int, str] = {}
    for nodo in ast.walk(albero):
        candidati: list[ast.AST] = []
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id in CHIAMATE:
            candidati += nodo.args[:1]
        if isinstance(nodo, ast.Dict):
            candidati += [v for k, v in zip(nodo.keys, nodo.values, strict=True) if _chiave(k) in CHIAVI]
        for c in candidati:
            testo = _testo(c).strip()
            if testo and ITALIANO.search(testo):
                trovati[c.lineno] = testo
    return sorted(trovati.items())


def _chiave(nodo: ast.AST | None) -> str:
    return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else ""


# Il debito, file per file: quante frasi italiane restituisce ciascuno strumento. Si abbassa quando un file viene tradotto.
DEBITO: dict[str, int] = {
    "calendario.py": 4,
    "clima.py": 8,
    "domini_casa.py": 18,  # la serratura e' tradotta (#207); restano media player, aspirapolvere, ventilatore
    "energia.py": 9,
    "ha_tools.py": 5,
    "liste.py": 9,
    "manutenzione.py": 11,
    "news_search.py": 3,
    "registry.py": 1,
    "reminders.py": 5,
    "sicurezza_casa.py": 10,
    "simulazione.py": 4,
    "tapparelle.py": 4,
    "weather.py": 2,
    "wikipedia_tool.py": 2,
}


def _conteggi() -> dict[str, int]:
    return {f.name: len(messaggi_italiani(f)) for f in sorted(SKILLS.glob("*.py")) if messaggi_italiani(f)}


def test_nessuno_strumento_ha_piu_frasi_italiane_di_prima() -> None:
    attuali = _conteggi()
    saliti = {f: (DEBITO.get(f, 0), n) for f, n in attuali.items() if n > DEBITO.get(f, 0)}
    assert saliti == {}, (
        "frasi italiane in piu' negli strumenti (prima, adesso): "
        f"{saliti} — la frase va nel file della lingua (`messaggi`), non nel codice"
    )


def test_il_debito_scritto_e_quello_vero() -> None:
    """Se un file ha meno frasi italiane di quelle scritte qui, il tetto si abbassa."""
    attuali = _conteggi()
    scesi = {f: (n, attuali.get(f, 0)) for f, n in DEBITO.items() if attuali.get(f, 0) < n}
    assert scesi == {}, f"abbassa il debito in questo file (scritto, vero): {scesi}"
