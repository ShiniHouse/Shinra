"""Le rotte delle passkey.

Tre sono pubbliche, e devono esserlo: sono l'accesso, e chi non e' ancora
entrato non ha una sessione da esibire. Le altre lavorano sul profilo della
sessione, come i dispositivi fidati e per lo stesso motivo — una passkey e'
personale, e un permesso statico direbbe la cosa sbagliata.

Riferimento: issue #48.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from shinra.api.app import app
from shinra.infra.db import depositi

# `TestClient` parla `http://testserver`, che non e' HTTPS ne' `localhost`:
# per il dominio e' un contesto non sicuro, ed e' il caso giusto per provare
# che il rifiuto sia chiaro. Con questa intestazione si passa dall'altra
# parte, dove le passkey si potrebbero usare.
DA_LOCALHOST = {"host": "localhost"}


@pytest.fixture(autouse=True)
def senza_sfide():
    from shinra.services.passkey import servizio_passkey

    servizio_passkey.dimentica_sfide()
    yield
    servizio_passkey.dimentica_sfide()


def _mia(utente: str, identificativo: str, nome: str = "iPhone") -> None:
    depositi.passkey.salva(
        {
            "id": identificativo,
            "user_id": utente,
            "nome": nome,
            "chiave_pubblica": "finta",
            "contatore": 0,
            "rp_id": "localhost",
            "tipo_dispositivo": "multi_device",
        }
    )


# ------------------------------------------------------------- lo stato


def test_lo_stato_si_legge_senza_essere_entrati():
    """La schermata d'accesso deve sapere se mostrare il pulsante **prima**
    che qualcuno sia entrato."""
    with TestClient(app) as client:
        risposta = client.get("/api/auth/passkey/stato")

    assert risposta.status_code == 200
    assert "disponibile" in risposta.json()


def test_dove_non_si_puo_lo_stato_dice_perche():
    """Un pulsante che fallisce con un errore del browser e' peggio di un
    pulsante assente: chi lo preme conclude che il server e' rotto."""
    with TestClient(app) as client:
        stato = client.get("/api/auth/passkey/stato", headers={"host": "192.168.1.50:8000"}).json()

    assert stato["disponibile"] is False
    assert stato["spiegazione"]


def test_da_localhost_le_passkey_si_possono_usare():
    with TestClient(app) as client:
        stato = client.get("/api/auth/passkey/stato", headers=DA_LOCALHOST).json()

    assert stato["disponibile"] is True
    assert stato["spiegazione"] == ""


# ------------------------------------------------------------ l'accesso


def test_la_sfida_di_accesso_si_chiede_senza_sessione():
    with TestClient(app) as client:
        risposta = client.post("/api/auth/passkey/accesso/inizio", headers=DA_LOCALHOST)

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["sfida_id"]
    assert corpo["opzioni"]["challenge"]


def test_la_sfida_di_accesso_non_elenca_le_credenziali_di_casa():
    """Direbbe a chiunque apra la pagina chi vive qui e quanti dispositivi
    ha."""
    _mia("alessio", "cred-1")

    with TestClient(app) as client:
        corpo = client.post("/api/auth/passkey/accesso/inizio", headers=DA_LOCALHOST).json()

    assert not corpo["opzioni"].get("allowCredentials")


def test_dove_non_si_puo_chiedere_la_sfida_e_un_conflitto_non_un_guasto():
    with TestClient(app) as client:
        risposta = client.post("/api/auth/passkey/accesso/inizio", headers={"host": "192.168.1.50:8000"})

    assert risposta.status_code == 409
    assert "nome di dominio" in risposta.json()["detail"]


def test_una_credenziale_sconosciuta_non_apre_la_sessione():
    with TestClient(app) as client:
        avvio = client.post("/api/auth/passkey/accesso/inizio", headers=DA_LOCALHOST).json()
        risposta = client.post(
            "/api/auth/passkey/accesso/fine",
            headers=DA_LOCALHOST,
            json={"sfida_id": avvio["sfida_id"], "credenziale": {"id": "mai-vista"}},
        )

    assert risposta.status_code == 401
    assert "shinra_sessione" not in risposta.cookies


# ------------------------------------------------- registrazione e gestione


def test_registrare_una_passkey_richiede_una_sessione():
    with TestClient(app) as client:
        risposta = client.post("/api/auth/passkey/registrazione/inizio", headers=DA_LOCALHOST)

    assert risposta.status_code == 401


def test_l_elenco_richiede_una_sessione():
    with TestClient(app) as client:
        assert client.get("/api/auth/passkey").status_code == 401


def test_l_elenco_mostra_le_proprie_senza_la_chiave_pubblica(cliente_autenticato):
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]
    _mia(chi.id, "cred-mia")
    _mia("qualcun-altro", "cred-altrui")

    elenco = cliente_autenticato.get("/api/auth/passkey").json()

    assert [p["id"] for p in elenco] == ["cred-mia"]
    assert "chiave_pubblica" not in elenco[0]


def test_si_revoca_la_propria(cliente_autenticato):
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]
    _mia(chi.id, "cred-mia")

    risposta = cliente_autenticato.delete("/api/auth/passkey/cred-mia")

    assert risposta.status_code == 200
    assert depositi.passkey.per_id("cred-mia") is None


def test_non_si_revoca_quella_di_un_altro(cliente_autenticato):
    """Stessa risposta di «non esiste»: distinguerle direbbe a chi prova che
    quella credenziale esiste e di chi non e'."""
    _mia("qualcun-altro", "cred-altrui")

    risposta = cliente_autenticato.delete("/api/auth/passkey/cred-altrui")

    assert risposta.status_code == 404
    assert depositi.passkey.per_id("cred-altrui") is not None


def test_una_passkey_con_le_barre_nell_identificativo_si_revoca(cliente_autenticato):
    """Gli identificativi sono base64url e non contengono barre, ma il
    percorso e' dichiarato `:path` proprio per non dipendere da questo: un
    identificativo che non si riesce a revocare e' una credenziale che resta
    valida per sempre."""
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]
    _mia(chi.id, "abc/def+ghi")

    risposta = cliente_autenticato.delete("/api/auth/passkey/abc/def+ghi")

    assert risposta.status_code == 200
    assert depositi.passkey.per_id("abc/def+ghi") is None


def test_l_inizio_della_registrazione_esclude_quelle_gia_registrate(cliente_autenticato):
    """Senza, lo stesso telefono registra due passkey per la stessa persona e
    l'elenco si riempie di righe indistinguibili."""
    from shinra.services.user_manager import user_manager

    chi = user_manager.get_users()[0]
    _mia(chi.id, "Y3JlZC1taWE")

    corpo = cliente_autenticato.post("/api/auth/passkey/registrazione/inizio", headers=DA_LOCALHOST).json()

    assert [c["id"] for c in corpo["opzioni"]["excludeCredentials"]] == ["Y3JlZC1taWE"]
