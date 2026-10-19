"""La scheda del sogno (#263, #262): le proposte sono di chi le riceve, e accettarne una non accende niente."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from shinra.api import routes_sogno
from shinra.domain import abitudini
from shinra.infra.db import depositi
from shinra.infra.db.proposte import proposte
from shinra.services import permessi, registro
from shinra.services.permessi import PermessoNegato
from shinra.services.user_manager import UserProfile

ADMIN = UserProfile(id="alessio", name="Alessio", role="admin")
ADULTA = UserProfile(id="sonia", name="Sonia", role="adult")
BAMBINO = UserProfile(id="marco", name="Marco", role="child", age_group="child")
ORA = datetime(2026, 10, 19, 3, 0)

LUCE = {
    "strumento": "control_device",
    "bersaglio": "light.cucina",
    "verbo": "turn_on",
    "orario": "07:30",
    "giorni": ["2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17"],
}


@pytest.fixture(autouse=True)
def pulito():
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    for chi in ("alessio", "sonia", "marco"):
        proposte.dimentica_profilo(chi)
    prima = {r["id"] for r in depositi.regole.elenco()}
    yield
    for chi in ("alessio", "sonia", "marco"):
        proposte.dimentica_profilo(chi)
    for r in depositi.regole.elenco():
        if r["id"] not in prima:
            depositi.regole.cancella(r["id"])


@pytest.fixture
def come(monkeypatch):
    stato = {"u": ADMIN}
    monkeypatch.setattr(routes_sogno, "utente_corrente", lambda request: stato["u"])
    return stato


def proponi(chi, dati=None, chiave="k"):
    return proposte.proponi(chi, "abitudine", chiave, dati or LUCE, ORA, ORA + timedelta(days=14))


async def test_ognuno_vede_solo_le_sue(come):
    proponi("alessio", chiave="a")
    proponi("sonia", chiave="s")
    assert [p["tipo"] for p in (await routes_sogno.proposte_in_attesa(None))["proposte"]] == ["abitudine"]
    come["u"] = ADULTA
    visto = await routes_sogno.proposte_in_attesa(None)
    assert len(visto["proposte"]) == 1 and "profilo" not in visto["proposte"][0]


async def test_senza_identita_non_c_e_niente(come):
    proponi("alessio")
    come["u"] = None
    assert (await routes_sogno.proposte_in_attesa(None))["proposte"] == []


@pytest.mark.parametrize("rotta", ["scarta", "accetta"])
async def test_la_proposta_di_un_altro_non_esiste(come, rotta):
    p = proponi("alessio")
    come["u"] = ADULTA
    with pytest.raises(HTTPException) as e:
        await getattr(routes_sogno, rotta)(p["id"], None)
    assert e.value.status_code == 404
    assert proposte.trova(p["id"])["stato"] == "nuova", "un altro profilo non deve poterla decidere"


async def test_un_identificativo_inventato_e_non_trovato(come):
    with pytest.raises(HTTPException) as e:
        await routes_sogno.scarta("p_inventata", None)
    assert e.value.status_code == 404


async def test_scartare_la_toglie_e_non_torna(come):
    p = proponi("alessio")
    assert (await routes_sogno.scarta(p["id"], None))["success"] is True
    assert (await routes_sogno.proposte_in_attesa(None))["proposte"] == []
    assert proponi("alessio") is None


async def test_accettare_un_abitudine_crea_una_regola_spenta(come):
    p = proponi("alessio")
    esito = await routes_sogno.accetta(p["id"], None)
    regola = depositi.regole.per_id(esito["regola"])
    assert regola is not None and regola["attiva"] is False, "la regola nasce spenta: la accende una persona"
    assert regola["trigger"] == {"tipo": "orario", "ora": "07:30"}
    assert regola["azioni"] == [{"tipo": "dispositivo", "entity_id": "light.cucina", "servizio": "turn_on"}]
    assert regola["autore"] == "alessio"
    assert proposte.trova(p["id"])["stato"] == "accettata"


async def test_accettare_due_volte_non_crea_due_regole(come):
    p = proponi("alessio")
    await routes_sogno.accetta(p["id"], None)
    seconda = await routes_sogno.accetta(p["id"], None)
    assert seconda["regola"] is None
    assert len([r for r in depositi.regole.elenco() if r.get("autore") == "alessio"]) == 1


async def test_chi_non_puo_creare_routine_non_ne_crea(come):
    p = proponi("marco")
    come["u"] = BAMBINO
    with pytest.raises(PermessoNegato):
        await routes_sogno.accetta(p["id"], None)
    assert proposte.trova(p["id"])["stato"] == "nuova"
    assert not [r for r in depositi.regole.elenco() if r.get("autore") == "marco"]


async def test_un_abitudine_senza_regola_possibile_si_accetta_senza_inventarne_una(come):
    p = proponi("alessio", {**LUCE, "strumento": "comanda_clima"}, chiave="clima")
    esito = await routes_sogno.accetta(p["id"], None)
    assert esito["regola"] is None and proposte.trova(p["id"])["stato"] == "accettata"


def test_il_registro_dice_che_e_successo_non_cosa(come):
    registro_prima = len(registro.voci(limite=1000))
    p = proponi("alessio")
    from shinra.services import proposte_del_sogno as servizio

    servizio.scarta(ADMIN, p["id"])
    nuove = registro.voci(limite=registro_prima + 5)[:1]
    assert nuove[0]["azione"] == "sogno.proposta_scartata"
    assert "cucina" not in str(nuove[0]["dettagli"])


# ------------------------------------------------------------ la bozza di regola, nel dominio


@pytest.mark.parametrize(
    "cambia",
    [
        {"strumento": "comanda_media"},
        {"verbo": "dimmi_qualcosa"},
        {"bersaglio": "cucina"},
        {"bersaglio": "lock.ingresso"},
        {"bersaglio": "script.notte"},
        {"orario": ""},
    ],
)
def test_senza_una_regola_sicura_non_si_scrive_la_bozza(cambia):
    assert abitudini.bozza_di_regola({**LUCE, **cambia}) is None


def test_la_bozza_e_sempre_spenta():
    assert abitudini.bozza_di_regola(LUCE)["attiva"] is False
