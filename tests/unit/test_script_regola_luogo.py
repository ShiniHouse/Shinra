"""`scripts/regola_luogo.py` (prova F3 della verifica): crea la regola vera, e la serratura su un luogo la fa rifiutare.

Lo script parla HTTP: qui lo si fa parlare con l'applicazione vera attraverso il client di prova, cosi' i nomi dei campi
(`tipo`, `servizio`, `luogo_id`...) sono quelli che il server accetta davvero e non quelli che chi scrive crede.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from shinra.infra.db import depositi
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import luoghi

PIN_DI_PROVA = "482913"  # lo stesso che imposta la fixture `cliente_autenticato`
PERCORSO = Path(__file__).resolve().parents[2] / "scripts" / "regola_luogo.py"


@pytest.fixture()
def script(cliente_autenticato, monkeypatch):
    spec = importlib.util.spec_from_file_location("regola_luogo", PERCORSO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    def chiedi(self, metodo, percorso, corpo=None):
        risposta = cliente_autenticato.request(metodo, percorso, json=corpo)
        try:
            return risposta.status_code, risposta.json()
        except ValueError:
            return risposta.status_code, None

    async def senza_home_assistant(_azioni):
        return None

    monkeypatch.setattr(modulo.Client, "chiedi", chiedi)
    monkeypatch.setattr(modulo.getpass, "getpass", lambda _p: PIN_DI_PROVA)
    monkeypatch.setattr("shinra.api.routes_regole._verifica_bersagli", senza_home_assistant)
    deposito.sostituisci_tutto([])
    depositi.regole.sostituisci_tutto([])
    luoghi.registra(
        {"nome": "Casa al mare", "latitudine": 44.12, "longitudine": 12.23, "origine": "telefono"}
    )
    yield modulo
    deposito.sostituisci_tutto([])
    depositi.regole.sostituisci_tutto([])


def test_crea_la_regola_all_arrivo_e_dice_se_puo_scattare(script, capsys):
    codice = script.main(
        ["--luogo", "casa al mare", "--persona", "person.alessio", "--lampada", "light.cucina"]
    )
    fuori = capsys.readouterr().out
    assert codice == 0, fuori
    [regola] = depositi.regole.elenco()
    assert regola["trigger"]["tipo"] == "luogo" and regola["trigger"]["evento"] == "arrivo"
    assert regola["trigger"]["entity_id"] == "person.alessio"
    assert regola["azioni"] == [{"tipo": "dispositivo", "entity_id": "light.cucina", "servizio": "turn_on"}]
    assert "Avviso:" in fuori and "Descrizione:" in fuori


def test_la_partenza_e_la_serratura_rifiutata(script, capsys):
    codice = script.main(
        ["--luogo", "Casa al mare", "--persona", "person.alessio", "--lampada", "light.cucina",
         "--evento", "partenza", "--rifiuto", "lock.ingresso"]
    )  # fmt: skip
    fuori = capsys.readouterr().out
    assert codice == 0, fuori
    assert "Serratura rifiutata come deve" in fuori
    assert len(depositi.regole.elenco()) == 1, "la serratura non deve essere stata salvata"
    assert depositi.regole.elenco()[0]["trigger"]["evento"] == "partenza"


def test_un_luogo_che_non_c_e_non_crea_niente(script, capsys):
    codice = script.main(["--luogo", "Marte", "--persona", "person.x", "--lampada", "light.x"])
    assert codice == 1 and depositi.regole.elenco() == []
    assert "Casa al mare" in capsys.readouterr().err, "deve dire quali luoghi ci sono"


def test_un_pin_sbagliato_non_va_avanti(script, monkeypatch, capsys):
    monkeypatch.setattr(script.getpass, "getpass", lambda _p: "000000")
    codice = script.main(["--luogo", "Casa al mare", "--persona", "person.x", "--lampada", "light.x"])
    # il client di prova e' gia' entrato, ma il login con PIN sbagliato risponde errore: lo script si ferma
    assert codice == 1 and depositi.regole.elenco() == []
