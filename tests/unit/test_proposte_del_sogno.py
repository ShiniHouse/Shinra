"""Il deposito delle proposte del sogno (#263): private, senza doppioni, e chi dice no non lo risente."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from shinra.infra.db.proposte import ACCETTATA, NUOVA, SCARTATA, proposte
from shinra.services import salvataggio

ORA = datetime(2026, 10, 19, 3, 0)
SCADE = ORA + timedelta(days=14)


@pytest.fixture(autouse=True)
def pulito():
    for chi in ("alessio", "sonia", ""):
        proposte.dimentica_profilo(chi)
    yield
    for chi in ("alessio", "sonia", ""):
        proposte.dimentica_profilo(chi)


def proponi(profilo="alessio", chiave="k1", quando=ORA):
    return proposte.proponi(profilo, "abitudine", chiave, {"a": 1}, quando, quando + timedelta(days=14))


def test_una_proposta_nuova_si_scrive_e_si_rilegge():
    p = proponi()
    assert p is not None and p["stato"] == NUOVA and p["dati"] == {"a": 1}
    assert [x["id"] for x in proposte.del_profilo("alessio")] == [p["id"]]


def test_ognuno_vede_solo_le_sue():
    proponi("alessio", "k1")
    proponi("sonia", "k2")
    assert [x["chiave"] for x in proposte.del_profilo("alessio")] == ["k1"]
    assert [x["chiave"] for x in proposte.del_profilo("sonia")] == ["k2"]


def test_la_stessa_proposta_non_si_scrive_due_volte():
    assert proponi() is not None
    assert proponi(quando=ORA + timedelta(days=1)) is None
    assert proposte.conta() == 1


def test_la_stessa_chiave_per_un_altro_profilo_e_un_altra_proposta():
    assert proponi("alessio") is not None and proponi("sonia") is not None


def test_chi_scarta_non_se_la_sente_riproporre():
    p = proponi()
    assert proposte.decidi(p["id"], SCARTATA, ORA)
    assert proponi(quando=ORA + timedelta(days=1)) is None
    assert proposte.del_profilo("alessio") == []


def test_una_proposta_decisa_non_cambia_piu():
    p = proponi()
    assert proposte.decidi(p["id"], ACCETTATA, ORA)
    assert not proposte.decidi(p["id"], SCARTATA, ORA)
    assert proposte.trova(p["id"])["stato"] == ACCETTATA


def test_uno_stato_inventato_non_si_accetta():
    p = proponi()
    assert not proposte.decidi(p["id"], "boh", ORA)
    assert not proposte.decidi("non_esiste", ACCETTATA, ORA)


def test_dopo_la_scadenza_se_ne_puo_scrivere_una_nuova():
    proponi()
    assert proposte.purga_scadute(SCADE + timedelta(days=1)) == 1
    assert proponi(quando=SCADE + timedelta(days=1)) is not None


def test_scaduta_ma_non_ancora_purgata_non_blocca_la_nuova():
    proponi()
    assert proponi(quando=SCADE + timedelta(days=1)) is not None


def test_dimenticare_un_profilo_lascia_stare_gli_altri():
    proponi("alessio")
    proponi("sonia")
    assert proposte.dimentica_profilo("alessio") == 1
    assert proposte.del_profilo("sonia")


def test_le_proposte_non_stanno_nei_salvataggi():
    assert "proposte_del_sogno" in salvataggio.FUORI
