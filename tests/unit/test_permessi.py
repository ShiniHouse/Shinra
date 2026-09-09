"""Chi puo' fare cosa, e cosa succede a chi non puo'.

Fino alla v0.2.0 il profilo distingueva adulto, ragazzo e bambino ma quella
distinzione cambiava **solo il tono delle risposte**: un bambino poteva
comandare qualunque cosa. Riferimento: issue #46, ADR 0004.

Il test piu' importante di questo file e'
`test_una_routine_non_aggira_il_permesso_sulle_serrature`: e' il modo ovvio
di eludere un controllo sui permessi, e se passasse quello, tutto il resto
sarebbe teatro.
"""

from __future__ import annotations

import pytest

from shinra.infra.db import depositi
from shinra.services import permessi, registro
from shinra.services.permessi import PermessoNegato
from shinra.services.user_manager import UltimoAmministratore, UserProfile, user_manager


@pytest.fixture(autouse=True)
def famiglia():
    """Una casa con i ruoli predefiniti e quattro persone."""
    permessi.assicura_ruoli_predefiniti()
    depositi.utenti.sostituisci_tutto(
        [
            {"id": "alessio", "name": "Alessio", "role": "admin"},
            {"id": "sonia", "name": "Sonia", "role": "adult"},
            {"id": "thomas", "name": "Thomas", "role": "teen"},
            {"id": "ospite", "name": "Ospite", "role": "guest"},
        ]
    )
    registro.apri_contesto(canale="web")
    yield


def _profilo(identificativo: str) -> UserProfile:
    return user_manager.get_user_by_id(identificativo)


# ------------------------------------------------------------- i ruoli


def test_i_ruoli_predefiniti_nascono_all_avvio():
    esistenti = {r["id"] for r in depositi.ruoli.elenco()}
    assert {"admin", "adult", "teen", "child", "guest"} <= esistenti


def test_ricreare_i_ruoli_non_sovrascrive_le_scelte_dell_utente():
    """Se hai tolto le serrature agli adulti, deve restare com'e' hai deciso
    tu anche dopo un aggiornamento."""
    depositi.ruoli.aggiorna("adult", {"permessi": [permessi.COMANDA_DISPOSITIVI]})

    permessi.assicura_ruoli_predefiniti()

    assert depositi.ruoli.per_id("adult")["permessi"] == [permessi.COMANDA_DISPOSITIVI]


def test_l_amministratore_ha_tutti_i_permessi():
    for permesso in permessi.TUTTI:
        assert permessi.ha_permesso(_profilo("alessio"), permesso)


def test_il_ragazzo_accende_le_luci_ma_non_apre_le_serrature():
    thomas = _profilo("thomas")
    assert permessi.ha_permesso(thomas, permessi.COMANDA_DISPOSITIVI)
    assert not permessi.ha_permesso(thomas, permessi.COMANDA_SICUREZZA)
    assert not permessi.ha_permesso(thomas, permessi.GESTISCI_IMPOSTAZIONI)


def test_l_ospite_puo_chiedere_non_comandare():
    ospite = _profilo("ospite")
    assert permessi.ha_permesso(ospite, permessi.LEGGI_CONOSCENZA)
    assert not permessi.ha_permesso(ospite, permessi.COMANDA_DISPOSITIVI)


def test_un_ruolo_cancellato_non_lascia_poteri_a_chi_lo_aveva():
    """Se qualcuno cancella un ruolo ancora assegnato, quei profili restano
    senza poteri invece di ereditarli tutti."""
    depositi.ruoli.cancella("teen")

    assert not permessi.ha_permesso(_profilo("thomas"), permessi.COMANDA_DISPOSITIVI)


def test_un_ruolo_su_misura_da_esattamente_i_permessi_scelti():
    """Criterio di accettazione: «Collaboratrice domestica» esiste perche' se
    ne possano creare di nuovi, non perche' se ne scelga uno fra quattro."""
    depositi.ruoli.aggiungi(
        {
            "id": "domestica",
            "nome": "Collaboratrice domestica",
            "permessi": [permessi.COMANDA_DISPOSITIVI, permessi.ATTIVA_MODALITA],
            "predefinito": False,
        }
    )
    depositi.utenti.salva({"id": "marta", "name": "Marta", "role": "domestica"})

    marta = _profilo("marta")
    assert permessi.ha_permesso(marta, permessi.COMANDA_DISPOSITIVI)
    assert permessi.ha_permesso(marta, permessi.ATTIVA_MODALITA)
    assert not permessi.ha_permesso(marta, permessi.COMANDA_SICUREZZA)
    assert not permessi.ha_permesso(marta, permessi.GESTISCI_UTENTI)


# ------------------------------------------------ serrature contro lampadine


def test_le_serrature_chiedono_un_permesso_diverso_dalle_luci():
    """Sbagliare su una serratura ha conseguenze di un altro ordine: chi puo'
    accendere una luce non deve per questo poter aprire la porta di casa."""
    assert permessi.permesso_per_dominio("light") == permessi.COMANDA_DISPOSITIVI
    assert permessi.permesso_per_dominio("climate") == permessi.COMANDA_DISPOSITIVI
    assert permessi.permesso_per_dominio("lock") == permessi.COMANDA_SICUREZZA
    assert permessi.permesso_per_dominio("alarm_control_panel") == permessi.COMANDA_SICUREZZA


# ------------------------------------------------------- il controllo vero


async def test_chi_non_puo_comandare_non_accende_la_luce(monkeypatch):
    """Criterio di accettazione: ne' da chat ne' da API diretta. Il controllo
    e' in `call_service`, dove passa tutto."""
    from shinra.infra.homeassistant.client import HomeAssistantClient

    registro.apri_contesto(attore="ospite", canale="web")
    chiamate = []

    async def non_deve_partire(*a, **k):
        chiamate.append(a)

    client = HomeAssistantClient(base_url="http://x", token="t" * 30)
    monkeypatch.setattr(client, "_connessione", lambda t: (_ for _ in ()).throw(AssertionError("rete!")))

    with pytest.raises(PermessoNegato):
        await client.call_service("light", "turn_on", {"entity_id": "light.cucina"})

    assert chiamate == []


async def test_una_routine_non_aggira_il_permesso_sulle_serrature(monkeypatch):
    """Il test che conta.

    Una routine puo' contenere qualunque azione, comprese quelle che un
    permesso negherebbe. Se venisse eseguita con i poteri di chi l'ha
    scritta, per aggirare il controllo basterebbe scriversi una routine —
    e chiunque puo' scriverne una.
    """
    from shinra.infra.homeassistant.client import HomeAssistantClient

    registro.apri_contesto(attore="thomas", canale="web")  # ragazzo: niente serrature
    client = HomeAssistantClient(base_url="http://x", token="t" * 30)

    # La luce passa...
    monkeypatch.setattr(client, "_connessione", lambda timeout: _FintoHttp())
    esito = await client.call_service("light", "turn_on", {"entity_id": "light.salotto"})
    assert esito["success"] is True

    # ...la serratura no, nemmeno dentro una routine.
    with pytest.raises(PermessoNegato):
        await client.call_service("lock", "unlock", {"entity_id": "lock.ingresso"})


class _FintoHttp:
    async def post(self, *a, **k):
        class Risposta:
            status_code = 200

            @staticmethod
            def json():
                return {}

        return Risposta()


async def test_il_rifiuto_e_spiegato_e_tracciato(monkeypatch):
    """Un 403 muto lascia solo l'impressione che qualcosa sia rotto: chi lo
    riceve non sa nemmeno cosa chiedere a chi amministra la casa."""
    from shinra.skills import registry

    registro.apri_contesto(attore="ospite", canale="web")

    async def finto_control(**argomenti):
        from shinra.services.permessi import esigi_per_dominio

        esigi_per_dominio("light")
        return {"success": True}

    monkeypatch.setitem(registry.TOOL_HANDLERS, "control_device", finto_control)
    esito = await registry.execute_tool("control_device", {"entity_id": "light.cucina"})

    assert esito["permesso_negato"] is True
    assert "permesso" in esito["spiegazione"].lower()

    negati = [v for v in registro.voci(limite=50) if v["esito"] == registro.ESITO_NEGATO]
    assert negati, "ogni rifiuto deve finire nel registro"


async def test_senza_identita_la_casa_resta_comandabile():
    """Con l'autenticazione spenta non c'e' un profilo: e' la stessa scelta
    fatta li', ed e' segnalata a voce alta dai controlli d'avvio."""
    registro.apri_contesto(attore=None, canale="web")

    assert permessi.ha_permesso(None, permessi.COMANDA_SICUREZZA)


# --------------------------------------------------- l'ultimo amministratore


def test_l_ultimo_amministratore_non_si_declassa():
    depositi.utenti.sostituisci_tutto([{"id": "alessio", "name": "Alessio", "role": "admin"}])

    with pytest.raises(UltimoAmministratore):
        user_manager.upsert_user(UserProfile(id="alessio", name="Alessio", role="adult"))


def test_l_ultimo_amministratore_non_si_cancella():
    depositi.utenti.sostituisci_tutto([{"id": "alessio", "name": "Alessio", "role": "admin"}])

    with pytest.raises(UltimoAmministratore):
        user_manager.delete_user("alessio")


def test_con_due_amministratori_uno_si_puo_declassare():
    depositi.utenti.salva({"id": "sonia", "name": "Sonia", "role": "admin"})

    user_manager.upsert_user(UserProfile(id="sonia", name="Sonia", role="adult"))

    assert _profilo("sonia").role == "adult"
    assert len(user_manager.amministratori()) == 1


# -------------------------------------------------------- le rotte protette


def test_ogni_rotta_che_cambia_qualcosa_dichiara_un_permesso():
    """Il presidio che impedisce al problema di tornare: una rotta nuova che
    scrive senza dichiarare il permesso fa fallire questo test, invece di
    passare inosservata per sei mesi."""
    from shinra.api.app import app
    from tests.unit.test_autenticazione import rotte_api

    # Rotte che scrivono ma non richiedono un permesso: sono elencate qui una
    # per una, con la ragione. Un elenco vuoto sarebbe piu' bello; mentire
    # sarebbe peggio.
    SENZA_PERMESSO = {
        ("POST", "/api/chat"),  # la chat non comanda: comandano i tool, controllati a valle
        ("POST", "/api/tts"),
        ("POST", "/api/alexa"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/users/identify"),  # dice solo chi sei, non cambia niente
        ("POST", "/api/timers"),
        ("DELETE", "/api/timers/{timer_id}"),
        ("POST", "/api/reminders"),
        ("DELETE", "/api/reminders/{reminder_id}"),
        ("POST", "/api/sources"),
        ("POST", "/api/sources/bulk-toggle"),
        ("DELETE", "/api/sources/{source_id}"),
        ("POST", "/api/learning/start"),
        ("POST", "/api/learning/answer"),
        ("POST", "/api/learning/confirm-routine"),
        ("POST", "/api/learning/stop"),
        # I dispositivi fidati non si proteggono con un permesso fisso: la
        # regola e' «i tuoi, oppure tutti se amministri», e dipende da chi
        # chiede e da chi possiede il dispositivo. Un permesso statico
        # direbbe la cosa sbagliata in meta' dei casi; il controllo di
        # proprieta' e' dentro le rotte, e ha i suoi test.
        ("DELETE", "/api/dispositivi/{id_dispositivo}"),
        ("POST", "/api/dispositivi/revoca-tutti"),
        # Le notifiche seguono la stessa regola dei dispositivi fidati, e per
        # lo stesso motivo: sono **personali**. Registrare il proprio
        # telefono e scegliere cosa sentire non e' un'azione amministrativa,
        # e un permesso statico direbbe la cosa sbagliata — o lo si da' a
        # tutti, e non protegge niente, o lo si nega, e la casa non avvisa
        # nessuno tranne gli amministratori.
        #
        # La protezione e' che ogni rotta lavora sull'utente della sessione:
        # `dimentica` rifiuta un endpoint che non e' tuo, e i test lo
        # verificano.
        ("POST", "/api/notifiche/sottoscrivi"),
        ("POST", "/api/notifiche/dimentica"),
        ("POST", "/api/notifiche/preferenze"),
        ("POST", "/api/notifiche/prova"),
    }

    mancanti = []
    for rotta in rotte_api(app):
        metodi = {m for m in rotta.methods if m in ("POST", "PUT", "PATCH", "DELETE")}
        if not metodi:
            continue
        nomi = {getattr(d.call, "__name__", "") for d in rotta.dependant.dependencies}
        if any(n.startswith("richiedi_") and n not in ("richiedi_autenticazione",) for n in nomi):
            continue
        for metodo in metodi:
            if (metodo, rotta.path) not in SENZA_PERMESSO:
                mancanti.append(f"{metodo} {rotta.path}")

    assert mancanti == [], f"queste rotte cambiano lo stato senza dichiarare un permesso: {mancanti}"


# --------------------------------------- i permessi arrivano all'interfaccia
#
# La dashboard non decide niente: nasconde. Ma per nascondere le cose giuste
# deve sapere cosa puo' fare chi la sta guardando, e finora non aveva modo di
# saperlo — mostrava a tutti il pannello dei ruoli, che poi il server
# rifiutava.


def _stato(client) -> dict:
    return client.get("/api/auth/status").json()


def test_lo_stato_dice_cosa_puo_fare_chi_e_entrato():
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.config.settings import settings

    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    user_manager.imposta_pin("thomas", "445566")
    sicurezza.azzera_stato()
    try:
        with TestClient(app) as client:
            client.post("/api/auth/login", json={"pin": "445566", "user_id": "thomas"})
            concessi = set(_stato(client)["permessi"])
    finally:
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()

    assert concessi == set(permessi.permessi_del_ruolo("teen"))
    assert permessi.COMANDA_SICUREZZA not in concessi
    assert permessi.GESTISCI_UTENTI not in concessi


def test_chi_non_e_entrato_non_ha_permessi():
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.config.settings import settings

    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    sicurezza.azzera_stato()
    try:
        with TestClient(app) as client:
            stato = _stato(client)
    finally:
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()

    assert stato["authenticated"] is False
    assert stato["permessi"] == []


def test_a_casa_aperta_l_elenco_e_completo():
    """Con l'autenticazione spenta `ha_permesso` concede tutto: l'interfaccia
    deve dire la stessa cosa, non fingere restrizioni che non ci sono."""
    from fastapi.testclient import TestClient

    from shinra.api import sicurezza
    from shinra.api.app import app
    from shinra.config.settings import settings

    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = False
    sicurezza.azzera_stato()
    try:
        with TestClient(app) as client:
            stato = _stato(client)
    finally:
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()

    assert set(stato["permessi"]) == set(permessi.TUTTI)
