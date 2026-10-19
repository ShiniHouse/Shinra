"""Il sogno nota le abitudini e le propone (#261): dal registro vero, per profilo, una volta sola."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shinra.infra.db.motore import sessione
from shinra.infra.db.proposte import proposte
from shinra.services import proposte_del_sogno as sogno

ADESSO = datetime(2026, 10, 19, 3, 0, tzinfo=timezone.utc)
LUCE = {"parametri": {"entity_id": "light.cucina", "action": "turn_on"}}


@pytest.fixture(autouse=True)
def pulito():
    for chi in ("alessio", "sonia", "guest"):
        proposte.dimentica_profilo(chi)
    yield
    for chi in ("alessio", "sonia", "guest"):
        proposte.dimentica_profilo(chi)


def scrivi(attore, giorni_fa, azione="tool.control_device", dettagli=None, esito="ok"):
    from shinra.infra.db.modelli import VoceRegistro

    # Le sette locali di quel giorno, cosi' la prova non dipende dal fuso della macchina.
    locale = (ADESSO - timedelta(days=giorni_fa)).astimezone().replace(hour=7, minute=30, tzinfo=None)
    utc = locale.astimezone().astimezone(timezone.utc).replace(tzinfo=None)
    with sessione() as s:
        s.add(
            VoceRegistro(
                momento=utc,
                attore=attore,
                canale="web",
                azione=azione,
                dettagli=dettagli or LUCE,
                esito=esito,
            )
        )


def test_quattro_mattine_diventano_una_proposta_con_le_prove():
    for g in (1, 2, 3, 5):
        scrivi("alessio", g)
    conta = sogno.proponi_abitudini(ADESSO)
    assert conta == {"viste": 1, "scritte": 1}
    (p,) = proposte.del_profilo("alessio")
    assert p["tipo"] == "abitudine" and p["dati"]["bersaglio"] == "light.cucina"
    assert len(p["dati"]["giorni"]) == 4 and p["dati"]["orario"] == "07:30"


def test_la_notte_dopo_non_riscrive_la_stessa_proposta():
    for g in (1, 2, 3, 5):
        scrivi("alessio", g)
    sogno.proponi_abitudini(ADESSO)
    assert sogno.proponi_abitudini(ADESSO + timedelta(days=1))["scritte"] == 0
    assert len(proposte.del_profilo("alessio")) == 1


def test_le_proposte_vanno_a_chi_ha_l_abitudine():
    for g in (1, 2, 3, 5):
        scrivi("alessio", g)
    for g in (1, 2):
        scrivi("sonia", g)
    sogno.proponi_abitudini(ADESSO)
    assert len(proposte.del_profilo("alessio")) == 1 and proposte.del_profilo("sonia") == []


def test_gli_ospiti_non_hanno_proposte():
    for g in (1, 2, 3, 5):
        scrivi("guest", g)
    assert sogno.proponi_abitudini(ADESSO)["scritte"] == 0


def test_il_log_non_dice_cosa_fai(monkeypatch):
    righe = []
    monkeypatch.setattr(sogno.logger, "info", lambda m, *a, **k: righe.append(m % a))
    for g in (1, 2, 3, 5):
        scrivi("alessio", g)
    sogno.proponi_abitudini(ADESSO)
    assert righe and not any("cucina" in r or "alessio" in r for r in righe)


async def test_il_compito_notturno_non_ha_bisogno_del_modello(monkeypatch):
    chiamate = []
    from shinra.services.compito_notturno import CompitoNotturno

    async def finto(self, nome, compito, tetto, **kw):
        chiamate.append((nome, kw.get("serve_il_modello")))

    monkeypatch.setattr(CompitoNotturno, "esegui", finto)
    await sogno._notte()
    assert chiamate == [("sogno_abitudini", False)]
