"""L'elenco delle automazioni, come lo legge la schermata.

Il campo che conta e' `prossimo`. Senza, la schermata elenca regole; con, la
schermata risponde alla domanda con cui ci si arriva sempre — «e allora
perche' non e' successo niente?». Una regola attiva e senza prossimo scatto e'
esattamente il difetto che ha tenuto ferme le regole del sole per due
versioni, e adesso si vede.

Il secondo che conta e' `aspetta_un_evento`, che tiene separate due cose che
si somigliano e non lo sono: una regola su evento senza prossimo scatto sta
benissimo, una regola all'alba senza prossimo scatto e' rotta.

Riferimento: issue #27, issue #28.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.infra.db import depositi
from shinra.infra.homeassistant.stati import cache_stati
from shinra.services.regole import motore_regole

FRA_OTTO_ORE = (datetime.now().astimezone() + timedelta(hours=8)).replace(microsecond=0)

SUN = {
    "entity_id": "sun.sun",
    "state": "below_horizon",
    "attributes": {
        "next_rising": FRA_OTTO_ORE.isoformat(),
        "next_setting": (FRA_OTTO_ORE + timedelta(hours=12)).isoformat(),
    },
}


@pytest.fixture(autouse=True)
def casa_pulita():
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()
    yield
    depositi.regole.sostituisci_tutto([])
    cache_stati.svuota()


def _regola(nome: str, trigger: dict, attiva: bool = True) -> str:
    voce = motore_regole.crea(
        {
            "nome": nome,
            "attiva": attiva,
            "trigger": trigger,
            "azioni": [{"tipo": "modalita", "modalita": "x"}],
        }
    )
    return str(voce["id"])


def _elenco(cliente) -> dict[str, dict]:
    risposta = cliente.get("/api/regole")
    assert risposta.status_code == 200
    return {r["id"]: r for r in risposta.json()["regole"]}


def test_una_regola_a_orario_si_crea_e_dice_quando_scattera(cliente_autenticato):
    """Con lo scheduler **acceso** — ed e' il punto.

    Questo test e' nato fallendo con un `TypeError: can't compare
    offset-naive and offset-aware datetimes`. `riprogramma_tutte` calcolava
    l'orario a partire da un `datetime.now()` senza fuso, e lo scheduler lo
    confronta con un `datetime.now(timezone.utc)`: creare una regola a orario
    — o salvare una routine con un innesco a orario — sollevava l'eccezione e
    rispondeva 500.

    Nessuno dei test esistenti lo vedeva perche' li' lo scheduler e' spento e
    `_programma` esce prima del confronto. Qui l'applicazione e' avviata sul
    serio, quindi il difetto si vede.
    """
    identificativo = _regola("Sette", {"tipo": "orario", "ora": "07:00"})

    voce = _elenco(cliente_autenticato)[identificativo]

    assert voce["prossimo"] is not None
    assert datetime.fromisoformat(voce["prossimo"]).hour == 7


def test_una_regola_all_alba_dice_quando_scattera(cliente_autenticato):
    """La prova che l'elenco usa davvero l'ora del sole: senza, il campo
    resterebbe vuoto e la schermata direbbe «non scattera'» di una regola
    perfettamente sana."""
    cache_stati.sostituisci([SUN])
    identificativo = _regola("Alba", {"tipo": "alba"})

    voce = _elenco(cliente_autenticato)[identificativo]

    assert voce["prossimo"] is not None
    assert datetime.fromisoformat(voce["prossimo"]) == FRA_OTTO_ORE


def test_senza_il_sole_una_regola_all_alba_non_ha_un_prossimo(cliente_autenticato):
    """Ed e' l'informazione utile: quella regola non scattera'."""
    identificativo = _regola("Alba", {"tipo": "alba"})

    voce = _elenco(cliente_autenticato)[identificativo]

    assert voce["prossimo"] is None
    assert voce["aspetta_un_evento"] is False


def test_una_regola_su_evento_aspetta_e_non_e_rotta(cliente_autenticato):
    """Le due si distinguono qui, non a occhio: senza `aspetta_un_evento` la
    schermata direbbe «non scattera'» di una regola che sta solo aspettando."""
    identificativo = _regola("Su evento", {"tipo": "evento", "evento": "casa.vuota"})

    voce = _elenco(cliente_autenticato)[identificativo]

    assert voce["prossimo"] is None
    assert voce["aspetta_un_evento"] is True


def test_una_regola_su_stato_aspetta_anche_lei(cliente_autenticato):
    identificativo = _regola("Freddo", {"tipo": "stato", "entity_id": "sensor.t", "valore": 15})

    assert _elenco(cliente_autenticato)[identificativo]["aspetta_un_evento"] is True


def test_una_regola_zittita_non_promette_niente(cliente_autenticato):
    """Una regola disattivata che continuasse ad annunciare il prossimo
    scatto direbbe una cosa falsa: quella regola non fara' niente."""
    identificativo = _regola("Sette", {"tipo": "orario", "ora": "07:00"}, attiva=False)

    voce = _elenco(cliente_autenticato)[identificativo]

    assert voce["prossimo"] is None


def test_l_elenco_dice_da_dove_viene_una_regola(cliente_autenticato):
    """La schermata deve poter distinguere una regola generata da un disegno:
    cancellarla non servirebbe a niente, perche' risalvando la routine
    tornerebbe identica."""
    motore_regole.sincronizza_dal_grafo(
        {
            "id": "m1",
            "name": "Buonanotte",
            "nodes": [{"id": "t", "type": "trigger", "data": {"trigger": {"tipo": "alba"}}}],
        }
    )

    origini = [r["origine"] for r in _elenco(cliente_autenticato).values()]

    assert origini == ["grafo:m1"]


def test_l_elenco_descrive_a_parole_quando_scatta(cliente_autenticato):
    identificativo = _regola("Sera", {"tipo": "tramonto"})

    assert "tramonto" in _elenco(cliente_autenticato)[identificativo]["descrizione"]
