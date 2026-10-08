"""#205: timer e promemoria capiscono piu' di una lingua.

Il parser del «quando» aveva le parole italiane dentro: «domani», «stasera», i nomi dei giorni. In inglese la frase
andava al modello, che e' il percorso lento e meno affidabile per la cosa che si dice piu' spesso in cucina. Adesso le
parole stanno nel file della lingua e il dominio non ne conosce nessuna.
"""

import ast
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from shinra import percorsi
from shinra.domain import quando
from shinra.services.intenti.lingue import LinguaIncompleta, schemi
from shinra.services.timer_engine import timer_engine

# Giovedi' 8 ottobre 2026, le 15:00.
ADESSO = datetime(2026, 10, 8, 15, 0)
IT = schemi("it").tempo
EN = schemi("en").tempo


# ---------------------------------------------- stesse frasi, stesso risultato


def test_lo_stesso_timer_in_italiano_e_in_inglese() -> None:
    it = timer_engine.parse_timer_or_reminder("metti un timer di dieci minuti per la pasta", schemi("it"))
    en = timer_engine.parse_timer_or_reminder("set a timer for ten minutes for the pasta", schemi("en"))

    assert it["duration_seconds"] == en["duration_seconds"] == 600
    assert it["type"] == en["type"] == "timer"
    assert it["label"].lower().endswith("pasta") and en["label"].lower().endswith("pasta")


def test_lo_stesso_promemoria_in_italiano_e_in_inglese() -> None:
    it = timer_engine.parse_timer_or_reminder(
        "ricordami domani mattina di chiamare il dentista", schemi("it")
    )
    en = timer_engine.parse_timer_or_reminder("remind me tomorrow morning to call the dentist", schemi("en"))

    assert it["remind_at"] == en["remind_at"], "non e' lo stesso istante"
    assert it["text"] == "Chiamare il dentista"
    assert en["text"] == "Call the dentist"
    assert it["formatted_time"] == "domani alle 09:00" and en["formatted_time"] == "tomorrow at 09:00"


def test_mezz_ora_in_inglese() -> None:
    letto = timer_engine.parse_timer_or_reminder("set a timer for half an hour", schemi("en"))
    assert letto["duration_seconds"] == 1800


def test_una_frase_italiana_non_e_un_timer_in_inglese() -> None:
    """Ogni lingua capisce le sue parole: a una frase che non e' sua risponde `None`, e va al modello."""
    assert timer_engine.parse_timer_or_reminder("metti un timer di dieci minuti", schemi("en")) is None


@pytest.mark.parametrize(
    "frase, atteso",
    [
        ("in half an hour", datetime(2026, 10, 8, 15, 30)),
        ("in two days", datetime(2026, 10, 10, 9, 0)),
        ("in an hour", datetime(2026, 10, 8, 16, 0)),
        ("tomorrow", datetime(2026, 10, 9, 9, 0)),
        ("tomorrow at 8 pm", datetime(2026, 10, 9, 20, 0)),
        ("the day after tomorrow in the evening", datetime(2026, 10, 10, 20, 0)),
        ("tonight", datetime(2026, 10, 8, 20, 0)),
        ("saturday", datetime(2026, 10, 10, 9, 0)),
        ("next thursday", datetime(2026, 10, 15, 9, 0)),
        ("at 6:30 pm", datetime(2026, 10, 8, 18, 30)),
        ("at 9 am", datetime(2026, 10, 9, 9, 0)),
        ("on the 15th", datetime(2026, 10, 15, 9, 0)),
        ("on the 3rd of november", datetime(2026, 11, 3, 9, 0)),
        ("on march 15th", datetime(2027, 3, 15, 9, 0)),
    ],
)
def test_il_quando_in_inglese(frase, atteso) -> None:
    assert quando.quando(frase, ADESSO, lessico=EN) == atteso


def test_in_inglese_una_frase_senza_ora_non_inventa_niente() -> None:
    assert quando.quando("call the dentist", ADESSO, lessico=EN) is None


def test_il_titolo_si_ripulisce_dall_ora_anche_in_inglese() -> None:
    testo, momento = quando.separa("call the dentist tomorrow morning", lessico=EN)
    assert testo == "call the dentist"
    assert momento is not None


def test_cena_con_marco_e_un_titolo_in_italiano_e_dinner_with_marco_in_inglese() -> None:
    """La stessa distinzione fra un pasto-ora e un pasto-titolo vale in entrambe."""
    assert quando.separa("cena con Marco", lessico=IT)[1] is None
    assert quando.separa("dinner with Marco", lessico=EN)[1] is None
    assert quando.separa("call me after dinner", lessico=EN)[1] is not None


def test_descrivi_parla_la_lingua_giusta() -> None:
    momento = datetime(2026, 10, 10, 20, 0)
    assert quando.descrivi(momento, ADESSO, lessico=IT) == "dopodomani alle 20:00"
    assert quando.descrivi(momento, ADESSO, lessico=EN) == "the day after tomorrow at 20:00"


# --------------------------------------------- una lingua inventata da un test


def _lingua_inventata() -> dict:
    """Una lingua che non e' l'italiano ne' l'inglese, per provare che il dominio non conosce nessuna."""
    return {
        "numeri": {"duo": 2, "tri": 3},
        "momenti": {
            "morning": ["matu"],
            "noon": ["mezu"],
            "afternoon": ["pomu"],
            "evening": ["seru", "cenu"],
            "night": ["nocu"],
        },
        "pasti": ["cenu"],
        "prima_dei_pasti": "(?:a)",
        "settimana": ["uno", "duoo", "trii", "quaa", "cinn", "seii", "setu"],
        "mesi": [f"mese{n}" for n in range(1, 13)],
        "word_today": "oji",
        "word_tomorrow": "morgu",
        "word_day_after_tomorrow": "dopomorgu",
        "next_weekday": "{giorno}\\s+sequ",
        "fra": "dentu",
        "unita": {
            "minutes": "minu",
            "hours": "oru",
            "days": "diu",
            "weeks": "setti",
            "months": "mesu",
        },
        "mezz_ora": "dentu\\s+mezzu",
        "alle": "aule",
        "dopo_mezzogiorno": "pm",
        "date": ["\\b(?:ilu)\\s+(?P<giorno>\\d{1,2})\\b"],
        "extra": ["\\bxx\\b"],
        "servizio_finale": "xa",
        "frasi": {
            "today": "oji {ora}",
            "tomorrow": "morgu {ora}",
            "day_after_tomorrow": "dopomorgu {ora}",
            "weekday": "{giorno} {ora}",
            "date": "{data} {ora}",
        },
    }


def test_una_lingua_inventata_capisce_le_sue_parole_e_non_quelle_italiane() -> None:
    inventata = quando.compila(_lingua_inventata())

    assert quando.quando("morgu seru", ADESSO, lessico=inventata) == datetime(2026, 10, 9, 20, 0)
    assert quando.quando("dentu duo oru", ADESSO, lessico=inventata) == datetime(2026, 10, 8, 17, 0)
    assert quando.quando("domani sera", ADESSO, lessico=inventata) is None, "ha capito l'italiano"
    assert quando.quando("tomorrow evening", ADESSO, lessico=inventata) is None, "ha capito l'inglese"


def test_un_lessico_a_meta_dice_per_nome_cosa_manca() -> None:
    dati = _lingua_inventata()
    del dati["fra"]
    dati["unita"].pop("weeks")
    dati["mesi"] = ["solo", "due"]

    with pytest.raises(quando.LessicoIncompleto) as errore:
        quando.compila(dati)

    messaggio = str(errore.value)
    assert "fra" in messaggio and "unita.weeks" in messaggio and "mesi" in messaggio


def test_il_caricatore_dice_quale_voce_del_tempo_manca(tmp_path, monkeypatch) -> None:
    """Una lingua senza la sezione `tempo` non si offre a meta': si dice per nome."""
    from shinra.services.intenti import lingue

    dati = yaml.safe_load((lingue.CARTELLA / "en.yaml").read_text(encoding="utf-8"))
    del dati["tempo"]["domani" if "domani" in dati["tempo"] else "word_tomorrow"]
    (tmp_path / "xx.yaml").write_text(yaml.safe_dump(dati, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(lingue, "CARTELLA", tmp_path)
    lingue._compila.cache_clear()
    try:
        with pytest.raises(LinguaIncompleta, match="word_tomorrow"):
            lingue._compila("xx")
    finally:
        lingue._compila.cache_clear()


# ------------------------------------- nessuna parola di tempo nel dominio


def _stringhe_del_codice(file: Path) -> set[str]:
    """Le stringhe del modulo, senza le docstring: quello che il codice puo' usare davvero."""
    albero = ast.parse(file.read_text(encoding="utf-8"))
    documentazione = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            primo = nodo.body[0] if nodo.body else None
            if isinstance(primo, ast.Expr) and isinstance(primo.value, ast.Constant):
                documentazione.add(id(primo.value))
    return {
        n.value.lower()
        for n in ast.walk(albero)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in documentazione
    }


def test_nessuna_parola_di_tempo_resta_nel_dominio() -> None:
    """Il criterio della #205: le parole stanno nei file delle lingue, non in `domain/quando.py`."""
    it = yaml.safe_load((percorsi.RADICE / "src/shinra/services/intenti/lingue/it.yaml").read_text("utf-8"))[
        "tempo"
    ]
    parole = set(it["numeri"]) | set(it["settimana"]) | set(it["mesi"]) | set(it["pasti"])
    parole |= {p for elenco in it["momenti"].values() for p in elenco}
    parole |= {it["word_today"], it["word_tomorrow"], it["word_day_after_tomorrow"]}

    nel_codice = _stringhe_del_codice(percorsi.RADICE / "src/shinra/domain/quando.py")
    rimaste = sorted(parole & nel_codice)

    assert rimaste == [], f"parole italiane rimaste in domain/quando.py: {rimaste}"


@pytest.mark.parametrize("lingua", ["it", "en"])
def test_ogni_lingua_ha_il_suo_lessico_del_tempo(lingua) -> None:
    lessico = schemi(lingua).tempo
    assert lessico.giorni_della_settimana and len(lessico.mesi) == 12
    assert schemi(lingua).timer["parola"]
