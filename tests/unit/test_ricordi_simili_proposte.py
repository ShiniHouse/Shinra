"""Ricordi doppi o in contraddizione, come proposte (#260): mai una modifica da sola, mai il ricordo di un altro."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from shinra.api import routes_sogno
from shinra.infra.db import depositi
from shinra.infra.db.proposte import proposte
from shinra.services import permessi
from shinra.services import proposte_del_sogno as sogno
from shinra.services.user_manager import UserProfile

ADMIN = UserProfile(id="alessio", name="Alessio", role="admin")
ADULTA = UserProfile(id="sonia", name="Sonia", role="adult")
ADESSO = datetime(2026, 10, 20, 3, 0, tzinfo=timezone.utc)

UNO = "La sveglia di Alessio suona alle 7 nei giorni feriali"
DUE = "La sveglia di Alessio suona alle 8 nei giorni feriali"


@pytest.fixture(autouse=True)
def pulito():
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    depositi.fatti.sostituisci_tutto([])
    for chi in ("alessio", "sonia"):
        proposte.dimentica_profilo(chi)
    yield
    depositi.fatti.sostituisci_tutto([])
    for chi in ("alessio", "sonia"):
        proposte.dimentica_profilo(chi)


@pytest.fixture
def come(monkeypatch):
    stato = {"u": ADMIN}
    monkeypatch.setattr(routes_sogno, "utente_corrente", lambda request: stato["u"])
    return stato


def ricordo(id_, testo, chi="alessio", **extra):
    depositi.fatti.aggiungi(
        {"id": id_, "text": testo, "category": "generale", "enabled": True, "proprietario": chi, **extra}
    )


def coppia_di_alessio():
    ricordo("k1", UNO)
    ricordo("k2", DUE)


async def proposta_di_alessio(come):
    sogno.proponi_ricordi(ADESSO)
    (p,) = (await routes_sogno.proposte_in_attesa(None))["proposte"]
    return p


async def test_la_notte_propone_la_coppia_e_non_tocca_i_ricordi(come):
    coppia_di_alessio()
    assert sogno.proponi_ricordi(ADESSO) == {"viste": 1, "scritte": 1}
    assert {r["id"]: r["stato"] for r in depositi.fatti.elenco()} == {"k1": "attivo", "k2": "attivo"}
    assert all(r["text"] in (UNO, DUE) for r in depositi.fatti.elenco()), "nessun testo e' stato cambiato"


async def test_la_stessa_coppia_non_si_riproporne_la_notte_dopo(come):
    coppia_di_alessio()
    sogno.proponi_ricordi(ADESSO)
    assert sogno.proponi_ricordi(ADESSO)["scritte"] == 0


async def test_i_ricordi_della_casa_non_producono_proposte(come):
    ricordo("c1", UNO, chi="")
    ricordo("c2", DUE, chi="")
    assert sogno.proponi_ricordi(ADESSO)["viste"] == 0


async def test_la_proposta_mostra_i_due_testi_solo_a_chi_li_possiede(come):
    coppia_di_alessio()
    p = await proposta_di_alessio(come)
    assert {r["id"] for r in p["dati"]["ricordi"]} == {"k1", "k2"}
    assert {r["testo"] for r in p["dati"]["ricordi"]} == {UNO, DUE}
    come["u"] = ADULTA
    assert (await routes_sogno.proposte_in_attesa(None))["proposte"] == []


async def test_se_un_ricordo_sparisce_la_proposta_non_si_mostra_piu(come):
    coppia_di_alessio()
    await proposta_di_alessio(come)
    depositi.fatti.aggiorna("k2", {"stato": "archiviato"})
    assert (await routes_sogno.proposte_in_attesa(None))["proposte"] == []


async def test_accettare_senza_dire_quale_tenere_non_fa_niente(come):
    coppia_di_alessio()
    p = await proposta_di_alessio(come)
    with pytest.raises(HTTPException) as e:
        await routes_sogno.accetta(p["id"], None)
    assert e.value.status_code == 422
    assert {r["stato"] for r in depositi.fatti.elenco()} == {"attivo"}
    assert proposte.trova(p["id"])["stato"] == "nuova"


async def test_tenere_un_ricordo_che_non_e_della_coppia_non_vale(come):
    coppia_di_alessio()
    ricordo("k3", "Altro ricordo di Alessio senza relazione")
    p = await proposta_di_alessio(come)
    with pytest.raises(HTTPException) as e:
        await routes_sogno.accetta(p["id"], None, routes_sogno.Accettazione(tieni="k3"))
    assert e.value.status_code == 422
    assert depositi.fatti.per_id("k3")["stato"] == "attivo"


async def test_si_tiene_uno_e_l_altro_si_archivia_senza_cancellare(come):
    coppia_di_alessio()
    p = await proposta_di_alessio(come)
    esito = await routes_sogno.accetta(p["id"], None, routes_sogno.Accettazione(tieni="k1"))
    assert esito["archiviato"] == "k2"
    assert depositi.fatti.per_id("k1")["stato"] == "attivo"
    assert (
        depositi.fatti.per_id("k2")["stato"] == "archiviato"
    ), "archiviato, non cancellato: si puo' riattivare"
    assert depositi.fatti.per_id("k2")["text"] == DUE
    assert proposte.trova(p["id"])["stato"] == "accettata"


async def test_un_altro_profilo_non_puo_decidere_la_coppia(come):
    coppia_di_alessio()
    p = await proposta_di_alessio(come)
    come["u"] = ADULTA
    with pytest.raises(HTTPException) as e:
        await routes_sogno.accetta(p["id"], None, routes_sogno.Accettazione(tieni="k1"))
    assert e.value.status_code == 404
    assert {r["stato"] for r in depositi.fatti.elenco()} == {"attivo"}


async def test_scartare_lascia_i_ricordi_com_erano_e_non_torna(come):
    coppia_di_alessio()
    p = await proposta_di_alessio(come)
    await routes_sogno.scarta(p["id"], None)
    assert {r["stato"] for r in depositi.fatti.elenco()} == {"attivo"}
    assert sogno.proponi_ricordi(ADESSO)["scritte"] == 0, "chi ha detto no non lo risente"


async def test_il_log_non_dice_cosa_ricordi(monkeypatch):
    righe = []
    monkeypatch.setattr(sogno.logger, "info", lambda m, *a, **k: righe.append(m % a))
    coppia_di_alessio()
    sogno.proponi_ricordi(ADESSO)
    assert righe and not any("sveglia" in r or "alessio" in r for r in righe)


async def test_una_proposta_che_punta_a_ricordi_altrui_non_li_mostra(come):
    """Difesa in profondita': anche se una proposta avesse gli identificativi di ricordi di un altro, non ne esce il testo."""
    ricordo("s1", "Sonia prepara una sorpresa per il compleanno di Alessio", chi="sonia")
    ricordo("s2", "Sonia prepara una sorpresa per il compleanno di Marco", chi="sonia")
    proposte.proponi(
        "alessio",
        "ricordo_doppio",
        "forzata",
        {"ids": ["s1", "s2"]},
        ADESSO.replace(tzinfo=None),
        ADESSO.replace(tzinfo=None, year=2027),
    )
    assert (await routes_sogno.proposte_in_attesa(None))["proposte"] == []
