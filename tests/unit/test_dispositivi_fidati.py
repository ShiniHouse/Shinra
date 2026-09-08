"""Il telefono che non chiede il PIN, e quello che si puo' togliere di mezzo.

Un PIN per persona rende i permessi reali, ma su un telefono diventa un
fastidio quotidiano — e una protezione fastidiosa viene disattivata. A quel
punto la casa e' aperta come prima, con in piu' l'illusione di essere
protetta. Riferimento: issue #20, ADR 0004.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from shinra.api import dispositivi, sicurezza
from shinra.api.app import app
from shinra.infra.db import depositi
from shinra.services import permessi
from shinra.services.user_manager import user_manager

PIN = "482913"


@pytest.fixture
def casa_chiusa():
    """Autenticazione attiva, due profili con PIN, tutto azzerato."""
    from shinra.config.settings import settings

    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    permessi.assicura_ruoli_predefiniti()
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "thomas", "name": "Thomas", "role": "teen"},
        ]
    )
    user_manager.imposta_pin("alessio", PIN)
    user_manager.imposta_pin("thomas", "112233")
    sicurezza.azzera_stato()
    yield
    settings.security.auth_enabled = era_attiva
    sicurezza.azzera_stato()


def _entra(client: TestClient, utente: str = "alessio", pin: str = PIN, ricorda: bool = False):
    return client.post(
        "/api/auth/login",
        json={
            "pin": pin,
            "user_id": utente,
            "ricorda_dispositivo": ricorda,
            "nome_dispositivo": "iPhone di prova",
        },
    )


# ------------------------------------------------------- il PIN non si ripete


def test_dopo_ricorda_il_pin_non_viene_piu_chiesto(casa_chiusa):
    """Il criterio di accettazione principale."""
    with TestClient(app) as client:
        assert _entra(client, ricorda=True).status_code == 200
        assert client.cookies.get(dispositivi.NOME_COOKIE)

        # Si esce: la sessione non c'e' piu', ma il dispositivo resta noto.
        client.post("/api/auth/logout")
        sicurezza.azzera_stato()

        assert client.get("/api/modes").status_code == 200


def test_senza_ricorda_il_pin_viene_richiesto(casa_chiusa):
    with TestClient(app) as client:
        assert _entra(client, ricorda=False).status_code == 200
        assert client.cookies.get(dispositivi.NOME_COOKIE) is None

        client.post("/api/auth/logout")
        sicurezza.azzera_stato()

        assert client.get("/api/modes").status_code == 401


def test_revocare_un_dispositivo_lo_rimanda_al_pin(casa_chiusa):
    with TestClient(app) as client:
        _entra(client, ricorda=True)
        elenco = client.get("/api/dispositivi").json()
        assert len(elenco) == 1

        assert client.delete(f"/api/dispositivi/{elenco[0]['id']}").json()["success"] is True

        client.post("/api/auth/logout")
        sicurezza.azzera_stato()
        assert client.get("/api/modes").status_code == 401


def test_revoca_tutti_risparmia_il_dispositivo_da_cui_si_chiede(casa_chiusa):
    """Chi ha perso il telefono lo fa dal computer di casa: restare chiusi
    fuori nello stesso momento non aiuterebbe nessuno."""
    with TestClient(app) as client:
        _entra(client, ricorda=True)
        dispositivi.ricorda("alessio", nome="Telefono perso", firma=sicurezza.firma_credenziale)
        assert len(dispositivi.elenco()) == 2

        esito = client.post("/api/dispositivi/revoca-tutti").json()

        assert esito["revocati"] == 1
        rimasti = dispositivi.elenco()
        assert len(rimasti) == 1 and rimasti[0]["nome"] == "iPhone di prova"


# ------------------------------------------------------------- la credenziale


def test_la_credenziale_non_e_leggibile_da_javascript(casa_chiusa):
    with TestClient(app) as client:
        risposta = _entra(client, ricorda=True)

    intestazioni = [v for k, v in risposta.headers.items() if k.lower() == "set-cookie"]
    del_dispositivo = [c for c in intestazioni if dispositivi.NOME_COOKIE in c]
    assert del_dispositivo, "il cookie del dispositivo deve essere impostato"
    assert "httponly" in del_dispositivo[0].lower()
    assert "samesite=lax" in del_dispositivo[0].lower()


def test_nel_database_c_e_solo_l_impronta(casa_chiusa):
    credenziale = dispositivi.ricorda("alessio", nome="Tablet", firma=sicurezza.firma_credenziale)

    from sqlalchemy import select

    from shinra.infra.db.modelli import DispositivoFidato
    from shinra.infra.db.motore import sessione

    with sessione() as s:
        righe = s.scalars(select(DispositivoFidato)).all()
        salvate = [r.impronta for r in righe]

    assert credenziale not in salvate
    assert all(len(i) == 64 for i in salvate)  # sha256 esadecimale


def test_una_credenziale_inventata_non_apre_niente(casa_chiusa):
    assert dispositivi.riconosci("credenziale-inventata") is None
    assert dispositivi.riconosci(None) is None


def test_un_dispositivo_lasciato_nel_cassetto_scade():
    credenziale = dispositivi.ricorda("alessio", nome="Vecchio", firma=sicurezza.firma_credenziale)

    from sqlalchemy import select

    from shinra.infra.db.modelli import DispositivoFidato
    from shinra.infra.db.motore import sessione

    with sessione() as s:
        riga = s.scalars(select(DispositivoFidato)).first()
        riga.ultimo_uso = datetime.now(timezone.utc) - timedelta(days=31)

    assert dispositivi.riconosci(credenziale) is None
    assert dispositivi.elenco() == []  # e viene tolto di mezzo


def test_ogni_uso_rinnova_la_scadenza():
    """Un telefono usato tutti i giorni non chiede mai il PIN; uno lasciato in
    un cassetto per un mese lo richiede."""
    credenziale = dispositivi.ricorda("alessio", nome="Quotidiano", firma=sicurezza.firma_credenziale)

    from sqlalchemy import select

    from shinra.infra.db.modelli import DispositivoFidato
    from shinra.infra.db.motore import sessione

    with sessione() as s:
        s.scalars(select(DispositivoFidato)).first().ultimo_uso = datetime.now(timezone.utc) - timedelta(
            days=29
        )

    assert dispositivi.riconosci(credenziale) == "alessio"

    with sessione() as s:
        riga = s.scalars(select(DispositivoFidato)).first()
        assert (datetime.now(timezone.utc).replace(tzinfo=None) - riga.ultimo_uso).days == 0


# --------------------------------------------------- identifica, non promuove


def test_un_dispositivo_fidato_non_regala_permessi(casa_chiusa):
    """Il telefono di Thomas resta il telefono di un ragazzo: puo' accendere
    le luci, non aprire la porta e non toccare le impostazioni."""
    with TestClient(app) as client:
        _entra(client, utente="thomas", pin="112233", ricorda=True)
        client.post("/api/auth/logout")
        sicurezza.azzera_stato()

        # Entra dal dispositivo, senza PIN...
        assert client.get("/api/modes").status_code == 200
        # ...ma resta un ragazzo.
        assert client.get("/api/settings").status_code == 403
        assert client.post("/api/users", json={"id": "x", "name": "X"}).status_code == 403


# ------------------------------------------------------------ le revoche


def test_cambiare_il_pin_revoca_gli_altri_dispositivi(casa_chiusa):
    """Se il PIN e' stato cambiato perche' qualcuno lo aveva scoperto, un
    telefono ancora fidato renderebbe il cambio inutile."""
    with TestClient(app) as client:
        _entra(client, ricorda=True)
        dispositivi.ricorda("alessio", nome="Altro telefono", firma=sicurezza.firma_credenziale)

        esito = client.post("/api/users/alessio/pin", json={"pin": "999888"}).json()

        assert esito["dispositivi_revocati"] == 1
        rimasti = [d["nome"] for d in dispositivi.elenco()]
        assert rimasti == ["iPhone di prova"]


def test_cancellare_un_profilo_revoca_i_suoi_dispositivi(casa_chiusa):
    dispositivi.ricorda("thomas", nome="Telefono di Thomas", firma=sicurezza.firma_credenziale)

    with TestClient(app) as client:
        _entra(client)
        client.delete("/api/users/thomas")

    assert dispositivi.elenco() == []


def test_un_familiare_non_revoca_i_dispositivi_di_un_altro(casa_chiusa):
    dispositivi.ricorda("alessio", nome="Di Alessio", firma=sicurezza.firma_credenziale)

    with TestClient(app) as client:
        _entra(client, utente="thomas", pin="112233")
        altrui = dispositivi.elenco("alessio")[0]["id"]

        assert client.delete(f"/api/dispositivi/{altrui}").status_code == 403


def test_ognuno_vede_i_propri_dispositivi(casa_chiusa):
    dispositivi.ricorda("alessio", nome="Di Alessio", firma=sicurezza.firma_credenziale)
    dispositivi.ricorda("thomas", nome="Di Thomas", firma=sicurezza.firma_credenziale)

    with TestClient(app) as client:
        _entra(client, utente="thomas", pin="112233")
        suoi = client.get("/api/dispositivi").json()

    assert [d["nome"] for d in suoi] == ["Di Thomas"]
