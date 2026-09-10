"""Le rotte con cui si dice di chi e' una voce.

Associare una voce a un profilo significa dare a chi parla i permessi di
quella persona: e' gestione degli utenti, e porta lo stesso permesso. Chi non
puo' creare un profilo amministratore non deve poter decidere quale voce lo
comanda.

Riferimento: issue #48.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.services import permessi


@pytest.fixture(autouse=True)
def voci_di_prova():
    permessi.assicura_ruoli_predefiniti()
    depositi.voci_sentite.segna_passaggio("amzn1.person.UNO")
    depositi.voci_sentite.segna_passaggio("amzn1.person.DUE")
    yield


def test_l_elenco_dice_quali_voci_sono_attribuite(cliente_autenticato):
    risposta = cliente_autenticato.get("/api/voci")

    assert risposta.status_code == 200
    per_id = {r["person_id"]: r for r in risposta.json()}
    assert set(per_id) == {"amzn1.person.UNO", "amzn1.person.DUE"}
    assert per_id["amzn1.person.UNO"]["user_id"] is None


def test_associare_una_voce_la_attribuisce(cliente_autenticato):
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]

    risposta = cliente_autenticato.post(
        "/api/voci/associa", json={"person_id": "amzn1.person.UNO", "user_id": chi.id}
    )

    assert risposta.status_code == 200
    assert depositi.voci_sentite.per_id("amzn1.person.UNO")["user_id"] == chi.id


def test_associare_a_un_profilo_inesistente_e_un_errore_del_cliente(cliente_autenticato):
    """Un errore di battitura non deve produrre un'associazione che sembra
    valida — e nemmeno un 500 che sembra un guasto."""
    risposta = cliente_autenticato.post(
        "/api/voci/associa", json={"person_id": "amzn1.person.UNO", "user_id": "non-esiste"}
    )

    assert risposta.status_code == 400
    assert depositi.voci_sentite.per_id("amzn1.person.UNO")["user_id"] is None


def test_associare_una_voce_mai_sentita_non_ne_inventa_una(cliente_autenticato):
    """Le righe nascono sentendo, non scrivendo: inventarne una vorrebbe dire
    poter attribuire permessi a un identificativo che nessuno ha verificato."""
    from shinra.services.user_manager import user_manager

    risposta = cliente_autenticato.post(
        "/api/voci/associa",
        json={"person_id": "amzn1.person.MAI", "user_id": user_manager.get_users()[0].id},
    )

    assert risposta.status_code == 404
    assert depositi.voci_sentite.per_id("amzn1.person.MAI") is None


def test_dissociare_riporta_la_voce_a_sconosciuta(cliente_autenticato):
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]
    cliente_autenticato.post("/api/voci/associa", json={"person_id": "amzn1.person.UNO", "user_id": chi.id})

    risposta = cliente_autenticato.post(
        "/api/voci/associa", json={"person_id": "amzn1.person.UNO", "user_id": None}
    )

    assert risposta.status_code == 200
    assert depositi.voci_sentite.per_id("amzn1.person.UNO")["user_id"] is None


def test_dimenticare_toglie_la_riga(cliente_autenticato):
    risposta = cliente_autenticato.delete("/api/voci/amzn1.person.DUE")

    assert risposta.status_code == 200
    assert depositi.voci_sentite.per_id("amzn1.person.DUE") is None


def test_dimenticare_una_voce_che_non_c_e_lo_dice(cliente_autenticato):
    assert cliente_autenticato.delete("/api/voci/amzn1.person.MAI").status_code == 404


def test_chi_non_gestisce_gli_utenti_non_associa_le_voci(cliente_autenticato):
    """Il controllo che rende la rotta qualcosa di piu' di un modulo: senza,
    un ragazzo potrebbe attribuire la propria voce al profilo del padre."""
    from shinra.services.user_manager import UserProfile, user_manager

    chi = user_manager.get_users()[0]
    # Un secondo amministratore, altrimenti declassare il primo e' vietato —
    # ed e' giusto che lo sia: una casa senza amministratori non si riapre.
    user_manager.upsert_user(UserProfile(id="altro-admin", name="Altro", role="admin"))
    user_manager.upsert_user(UserProfile(id=chi.id, name=chi.name, role="teen"))

    risposta = cliente_autenticato.post(
        "/api/voci/associa", json={"person_id": "amzn1.person.UNO", "user_id": chi.id}
    )

    assert risposta.status_code == 403
    assert depositi.voci_sentite.per_id("amzn1.person.UNO")["user_id"] is None


def test_senza_sessione_l_elenco_non_si_legge():
    """Dice quante persone parlano in questa casa: non e' per chiunque passi."""
    from fastapi.testclient import TestClient

    from shinra.api.app import app

    with TestClient(app) as client:
        assert client.get("/api/voci").status_code == 401
