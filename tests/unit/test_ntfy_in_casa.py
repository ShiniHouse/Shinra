"""ntfy in casa (#389): un canale in uscita che non passa mai da terzi, spento finche' la persona non lo accende.

Le regole difese qui: un indirizzo che non sia di casa non riceve niente (nemmeno una connessione); il canale e' acceso solo
per chi lo ha chiesto; l'argomento e' privato e non contiene il nome della persona; un guasto non diventa un'eccezione.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi import HTTPException

from shinra.api import routes_notifiche
from shinra.config.settings import settings
from shinra.domain import notifiche as dominio
from shinra.infra import ntfy
from shinra.services.notifiche import ServizioNotifiche
from shinra.services.user_manager import UserProfile

LOCALE = "http://192.168.1.20:8090"
AVVISO = dominio.Avviso(
    categoria=dominio.PROMEMORIA, titolo="Pasta", testo="Il timer e' scaduto", priorita="importante"
)


@pytest.fixture(autouse=True)
def impostazioni(monkeypatch):
    monkeypatch.setattr(settings.notifiche, "ntfy_url", LOCALE)
    monkeypatch.setattr(settings.security, "session_secret", "un-segreto-di-prova")


# ------------------------------------------------------------------ l'indirizzo


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8090",
        "http://127.0.0.1",
        "http://192.168.1.20:8090",
        "http://10.0.0.5",
        "http://172.16.3.4",
        "http://ntfy",
        "http://ntfy:80",
        "http://casa.local",
        "https://ntfy.lan",
        "http://[::1]:8090",
    ],
)
def test_gli_indirizzi_di_casa_sono_locali(url):
    assert dominio.indirizzo_locale(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://ntfy.sh",
        "https://ntfy.sh/mio-argomento",
        "http://8.8.8.8",
        "http://93.184.216.34:80",
        "https://ntfy.example.com",
        "http://casa.local.example.com",
        "ftp://192.168.1.20",
        "192.168.1.20",
        "http://",
        "",
    ],
)
def test_gli_indirizzi_pubblici_o_strani_non_sono_locali(url):
    assert not dominio.indirizzo_locale(url)


# ------------------------------------------------------------------ l'argomento


def test_l_argomento_e_stabile_e_privato():
    a = dominio.argomento_ntfy("segreto", "alessio")
    assert a == dominio.argomento_ntfy("segreto", "alessio")
    assert a != dominio.argomento_ntfy("segreto", "sonia"), "ognuno il suo"
    assert a != dominio.argomento_ntfy("altro-segreto", "alessio"), "senza il segreto non si indovina"
    assert "alessio" not in a


# ------------------------------------------------------------------ i canali


def prefs(**canali):
    return dominio.Preferenze("alessio", canali=dict(canali))


def test_ntfy_nasce_spento_gli_altri_canali_accesi():
    p = dominio.Preferenze("alessio")
    assert not p.vuole_canale(dominio.NTFY)
    assert p.vuole_canale(dominio.PUSH) and p.vuole_canale(dominio.WEB)
    assert dominio.NTFY not in dominio.canali_per(AVVISO, p)


def test_ntfy_si_accende_solo_se_la_persona_lo_vuole():
    assert dominio.NTFY in dominio.canali_per(AVVISO, prefs(ntfy=True))
    assert dominio.NTFY not in dominio.canali_per(AVVISO, prefs(ntfy=False))


def test_il_silenzioso_zittisce_ntfy_ma_non_la_sicurezza():
    zitto = dominio.Preferenze("alessio", canali={"ntfy": True}, silenzioso=True)
    assert dominio.NTFY not in dominio.canali_per(AVVISO, zitto)
    allarme = dominio.Avviso(categoria=dominio.SICUREZZA, titolo="Allarme", priorita=dominio.URGENTE)
    # Un allarme non si zittisce: arriva su ogni canale che la persona ha acceso, ntfy compreso.
    assert dominio.NTFY in dominio.canali_per(allarme, zitto)
    senza = dominio.Preferenze("alessio", silenzioso=True)
    assert dominio.NTFY not in dominio.canali_per(allarme, senza), "ma solo se lo ha acceso"


def test_senza_preferenze_ntfy_non_parte_nemmeno_per_un_urgente():
    urgente = dominio.Avviso(categoria=dominio.SICUREZZA, titolo="Allarme", priorita=dominio.URGENTE)
    assert dominio.NTFY not in dominio.canali_per(urgente, None)


# ------------------------------------------------------------------ l'invio


@respx.mock
async def test_pubblica_sul_server_di_casa_con_un_json():
    rotta = respx.post(LOCALE + "/").mock(return_value=httpx.Response(200, json={}))
    esito = await ntfy.pubblica(
        LOCALE, "shinra-abc", {"titolo": "Pasta", "testo": "Pronta", "priorita": "urgente"}
    )
    assert esito.riuscito and rotta.called
    corpo = rotta.calls[0].request.content.decode()
    assert '"topic":"shinra-abc"' in corpo.replace(" ", "") and '"priority":5' in corpo.replace(" ", "")


@respx.mock
async def test_un_indirizzo_pubblico_non_riceve_nemmeno_una_connessione():
    rotta = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200))
    esito = await ntfy.pubblica("https://ntfy.sh", "shinra-abc", {"titolo": "x"})
    assert not esito.riuscito and not rotta.called, "con un indirizzo non locale non deve uscire niente"


@respx.mock
@pytest.mark.parametrize("errore", [httpx.ConnectError("giu'"), httpx.ReadTimeout("lento")])
async def test_un_guasto_non_solleva(errore):
    respx.post(LOCALE + "/").mock(side_effect=errore)
    esito = await ntfy.pubblica(LOCALE, "shinra-abc", {"titolo": "x"})
    assert not esito.riuscito


@respx.mock
async def test_un_rifiuto_del_server_e_un_insuccesso_non_un_errore():
    respx.post(LOCALE + "/").mock(return_value=httpx.Response(403))
    assert not (await ntfy.pubblica(LOCALE, "shinra-abc", {"titolo": "x"})).riuscito


@respx.mock
async def test_il_log_non_dice_cosa_hai_scritto(monkeypatch):
    righe = []
    monkeypatch.setattr(ntfy.logger, "warning", lambda m, *a, **k: righe.append(m % a))
    respx.post(LOCALE + "/").mock(side_effect=httpx.ConnectError("giu'"))
    await ntfy.pubblica(LOCALE, "shinra-segreto", {"titolo": "Medicina", "testo": "alle sette"})
    assert righe and not any(p in r for r in righe for p in ("Medicina", "sette", "shinra-segreto"))


# ------------------------------------------------------------------ il servizio


@respx.mock
async def test_il_servizio_manda_solo_a_chi_ha_acceso_ntfy():
    rotta = respx.post(LOCALE + "/").mock(return_value=httpx.Response(200))
    servizio = ServizioNotifiche()
    servizio.imposta("alessio", "canale.ntfy", True)
    esito = await servizio.avvisa(AVVISO, utente="alessio")
    assert esito["per_canale"].get("ntfy") == 1 and rotta.call_count == 1

    rotta.reset()
    servizio.imposta("sonia", "canale.web", True)
    await servizio.avvisa(AVVISO, utente="sonia")
    assert rotta.call_count == 0, "sonia non lo ha acceso"


@respx.mock
async def test_senza_indirizzo_o_senza_segreto_non_parte_niente(monkeypatch):
    rotta = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200))
    servizio = ServizioNotifiche()
    servizio.imposta("alessio", "canale.ntfy", True)
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "")
    assert (await servizio.avvisa(AVVISO, utente="alessio"))["per_canale"].get("ntfy", 0) == 0
    monkeypatch.setattr(settings.notifiche, "ntfy_url", LOCALE)
    monkeypatch.setattr(settings.security, "session_secret", "")
    assert (await servizio.avvisa(AVVISO, utente="alessio"))["per_canale"].get("ntfy", 0) == 0
    assert not rotta.called


@respx.mock
async def test_un_indirizzo_pubblico_in_configurazione_non_manda_niente(monkeypatch):
    rotta = respx.post(url__regex=r".*").mock(return_value=httpx.Response(200))
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "https://ntfy.sh")
    servizio = ServizioNotifiche()
    servizio.imposta("alessio", "canale.ntfy", True)
    assert (await servizio.avvisa(AVVISO, utente="alessio"))["per_canale"].get("ntfy", 0) == 0
    assert not rotta.called


# ------------------------------------------------------------------ le rotte


ADMIN = UserProfile(id="alessio", name="Alessio", role="admin")


async def test_accenderlo_senza_server_di_casa_e_un_errore_che_spiega(monkeypatch):
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "")
    with pytest.raises(HTTPException) as e:
        await routes_notifiche.imposta_preferenza(
            routes_notifiche.Preferenza(chiave="canale.ntfy", valore=True), ADMIN
        )
    assert e.value.status_code == 400 and "ntfy_url" in e.value.detail


async def test_accenderlo_con_un_indirizzo_pubblico_e_rifiutato(monkeypatch):
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "https://ntfy.sh")
    with pytest.raises(HTTPException) as e:
        await routes_notifiche.imposta_preferenza(
            routes_notifiche.Preferenza(chiave="canale.ntfy", valore=True), ADMIN
        )
    assert e.value.status_code == 400


async def test_spegnerlo_si_puo_sempre(monkeypatch):
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "")
    r = await routes_notifiche.imposta_preferenza(
        routes_notifiche.Preferenza(chiave="canale.ntfy", valore=False), ADMIN
    )
    assert r["success"]


async def test_l_argomento_lo_vede_solo_chi_ha_acceso_ntfy():
    servizio = routes_notifiche.servizio_notifiche
    servizio.imposta("alessio", "canale.ntfy", False)
    spento = await routes_notifiche.ntfy(ADMIN)
    assert spento["configurato"] and not spento["acceso"] and spento["argomento"] == ""

    servizio.imposta("alessio", "canale.ntfy", True)
    acceso = await routes_notifiche.ntfy(ADMIN)
    assert (
        acceso["acceso"]
        and acceso["argomento"].startswith("shinra-")
        and "alessio" not in acceso["argomento"]
    )
    servizio.imposta("alessio", "canale.ntfy", False)


async def test_un_indirizzo_pubblico_si_segnala_senza_mostrarlo(monkeypatch):
    monkeypatch.setattr(settings.notifiche, "ntfy_url", "https://ntfy.sh")
    visto = await routes_notifiche.ntfy(ADMIN)
    assert not visto["configurato"] and visto["indirizzo_non_locale"] and visto["indirizzo"] == ""


def test_l_indirizzo_di_ntfy_si_puo_dare_dall_ambiente_come_fa_docker(monkeypatch):
    """Il `docker-compose.yml` passa `SHINRA_NTFY_URL`: deve arrivare nella configurazione (e non finire in `config.yaml`)."""
    from shinra.config import secrets as segreti
    from shinra.config.settings import _applica_ambiente

    monkeypatch.setenv("SHINRA_NTFY_URL", "http://ntfy:80")
    assert _applica_ambiente({})["notifiche"]["ntfy_url"] == "http://ntfy:80"
    assert ("notifiche", "ntfy_url") not in segreti.CAMPI_SEGRETI, "e' un indirizzo, non un segreto"
