"""`scripts/registro.py` legge il registro dal server (issue #195).

La dashboard non mostra il registro delle azioni; per sapere se una regola e' scattata davvero, o se una conferma e'
stata chiesta, serve poter leggerlo dalla riga di comando. Lo script non scrive: qui si prova che dice quello che c'e'.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from shinra.services import registro

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "registro.py"


def _script():
    spec = importlib.util.spec_from_file_location("script_registro", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_mostra_le_voci_dalla_piu_vecchia_alla_piu_recente(capsys):
    registro.registra("regola.eseguita", esito="ok", dettagli={"nome": "Luce al tramonto"})
    registro.registra("conferma.richiesta", esito="ok", dettagli={"tool": "comanda_serratura"})

    codice = _script().main(["--ore", "1"])

    uscita = capsys.readouterr().out
    assert codice == 0
    assert uscita.index("regola.eseguita") < uscita.index("conferma.richiesta")
    assert "Luce al tramonto" in uscita and "comanda_serratura" in uscita


def test_il_filtro_sull_azione_cerca_una_parte_del_nome(capsys):
    registro.registra("regola.eseguita", esito="ok")
    registro.registra("regola.saltata", esito="saltata")
    registro.registra("conferma.richiesta", esito="ok")

    _script().main(["--azione", "regola"])

    uscita = capsys.readouterr().out
    assert "regola.eseguita" in uscita and "regola.saltata" in uscita
    assert "conferma.richiesta" not in uscita


def test_senza_voci_lo_dice_e_non_finge_che_vada_bene(capsys):
    codice = _script().main(["--azione", "una.cosa.che.non.esiste"])

    assert codice == 1
    assert "Nessuna voce" in capsys.readouterr().err


def test_l_ora_del_registro_e_utc_e_si_mostra_in_ora_locale():
    """Il registro salva l'ora in UTC senza il fuso: letta come locale, una regola delle 21:30 compariva alle 19:30."""
    from datetime import datetime, timezone

    atteso = datetime(2026, 10, 7, 19, 30, 15, tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

    assert _script()._in_ora_locale("2026-10-07T19:30:15") == atteso
    assert (
        _script()._in_ora_locale("2026-10-07T19:30:15+00:00") == atteso
    ), "con il fuso dichiarato vale lo stesso"
