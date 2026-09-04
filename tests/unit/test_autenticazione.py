"""La casa non risponde a chi non si e' identificato.

Prima della issue #3, `is_authenticated()` era invocata in **un endpoint su
trentanove**: chiunque fosse sulla rete di casa comandava l'impianto e leggeva
l'anagrafica della famiglia con una `curl`.

Il test piu' importante di questo file non e' quello sui 401: e'
`test_ogni_rotta_dichiara_la_propria_protezione`, che fallisce quando qualcuno
aggiunge un endpoint senza decidere se sia pubblico. E' l'unico modo perche' il
problema non si ripresenti fra sei mesi.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from config.settings import settings
from core.user_manager import user_manager
from server import sicurezza
from server.app import app

PIN_DI_PROVA = "482913"
DIPENDENZE_PROTETTE = {"richiedi_autenticazione", "richiedi_amministratore"}


def rotte_api(applicazione) -> list[APIRoute]:
    """Tutte le rotte, scendendo dentro i router inclusi.

    FastAPI conserva i router inclusi come oggetti annidati invece di
    appiattirli: fermarsi al primo livello ne vedrebbe sette su quaranta, e il
    test sembrerebbe passare mentre non guarda quasi nulla.
    """
    trovate: list[APIRoute] = []
    visti: set[int] = set()

    def scendi(contenitore) -> None:
        if id(contenitore) in visti:
            return
        visti.add(id(contenitore))

        for r in getattr(contenitore, "routes", []) or []:
            if isinstance(r, APIRoute):
                trovate.append(r)
                continue
            # FastAPI conserva un router incluso come _IncludedRouter, che
            # non espone `routes` ma tiene l'originale in `original_router`.
            interno = getattr(r, "original_router", None)
            if interno is not None:
                scendi(interno)
            elif hasattr(r, "routes"):
                scendi(r)

        annidato = getattr(contenitore, "router", None)
        if annidato is not None and annidato is not contenitore:
            scendi(annidato)

    scendi(applicazione)
    return trovate


def e_protetta(rotta: APIRoute) -> bool:
    nomi = {getattr(d.call, "__name__", "") for d in rotta.dependant.dependencies}
    for d in rotta.dependant.dependencies:
        nomi |= {getattr(s.call, "__name__", "") for s in d.dependencies}
    return bool(nomi & DIPENDENZE_PROTETTE)


@pytest.fixture()
def casa_chiusa():
    """Autenticazione attiva, un amministratore con PIN, sessioni azzerate."""
    era_attiva = settings.security.auth_enabled
    utenti = user_manager.get_users()
    amministratore = utenti[0]
    pin_originale = amministratore.pin

    settings.security.auth_enabled = True
    user_manager.imposta_pin(amministratore.id, PIN_DI_PROVA)
    sicurezza.azzera_stato()

    yield amministratore

    settings.security.auth_enabled = era_attiva
    utenti = user_manager.get_users()
    for i, u in enumerate(utenti):
        if u.id == amministratore.id:
            utenti[i].pin = pin_originale
    user_manager.save_users(utenti)
    sicurezza.azzera_stato()


# ---------------------------------------------------------------- inventario


def test_ogni_rotta_dichiara_la_propria_protezione() -> None:
    """Nessuna rotta puo' essere ne' protetta ne' dichiarata pubblica.

    Questo test fallisce quando si aggiunge un endpoint dimenticandosi della
    sicurezza. Per farlo passare bisogna scegliere: proteggerlo, oppure
    aggiungerlo a `sicurezza.ROTTE_PUBBLICHE` scrivendo perche'.
    """
    scoperte = [
        f"{sorted(r.methods)} {r.path}"
        for r in rotte_api(app)
        if not e_protetta(r) and r.path not in sicurezza.ROTTE_PUBBLICHE
    ]
    assert not scoperte, (
        "Rotte senza protezione e non dichiarate pubbliche:\n  "
        + "\n  ".join(sorted(set(scoperte)))
        + "\n\nProteggila con Depends(richiedi_autenticazione), oppure aggiungila a "
        "server/sicurezza.py ROTTE_PUBBLICHE spiegando perche'."
    )


def test_l_inventario_vede_davvero_tutte_le_rotte() -> None:
    """Guardia sulla guardia.

    Se un aggiornamento di FastAPI cambiasse il modo di annidare i router,
    `rotte_api` potrebbe restituire una manciata di rotte e il test qui sopra
    passerebbe senza guardare nulla.
    """
    trovate = rotte_api(app)
    percorsi = {r.path for r in trovate}
    assert (
        len(percorsi) > 25
    ), f"Trovate solo {len(percorsi)} rotte: l'inventario non sta scendendo nei router"
    for attesa in ("/api/modes", "/api/users", "/api/knowledge", "/api/auth/login", "/health"):
        assert attesa in percorsi, f"{attesa} non compare nell'inventario"


# ------------------------------------------------------------ senza sessione


@pytest.mark.parametrize(
    ("metodo", "rotta"),
    [
        ("GET", "/api/modes"),
        ("GET", "/api/users"),
        ("GET", "/api/knowledge"),
        ("GET", "/api/aliases"),
        ("GET", "/api/timers"),
        ("GET", "/api/settings"),
        ("GET", "/api/status"),
        ("POST", "/api/modes/Cinema/activate"),
    ],
)
def test_senza_sessione_risponde_401(casa_chiusa, metodo: str, rotta: str) -> None:
    with TestClient(app) as c:
        assert c.request(metodo, rotta).status_code == 401


def test_la_chat_non_comanda_la_casa_senza_sessione(casa_chiusa) -> None:
    """Il caso che conta: la chat accetta linguaggio naturale, quindi puo'
    accendere luci, attivare modalita' e leggere lo stato della casa."""
    with TestClient(app) as c:
        assert c.post("/api/chat", json={"message": "accendi la luce"}).status_code == 401


@pytest.mark.parametrize("rotta", ["/health", "/api/auth/status", "/api/auth/profili"])
def test_le_rotte_pubbliche_restano_raggiungibili(casa_chiusa, rotta: str) -> None:
    with TestClient(app) as c:
        assert c.get(rotta).status_code == 200


def test_health_non_rivela_nulla(casa_chiusa) -> None:
    """E' pubblica: non deve contenere modelli, indirizzi o stato dei servizi."""
    with TestClient(app) as c:
        corpo = c.get("/health").json()
    assert corpo == {"status": "ok"}


def test_l_elenco_profili_non_espone_i_pin(casa_chiusa) -> None:
    with TestClient(app) as c:
        profili = c.get("/api/auth/profili").json()
    assert profili
    for p in profili:
        assert "pin" not in p
        assert set(p) <= {"id", "name", "avatar_type", "role", "ha_pin"}


# --------------------------------------------------------------------- accesso


def test_accesso_con_pin_corretto(casa_chiusa) -> None:
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": casa_chiusa.id})
        assert r.status_code == 200
        assert r.json()["utente"]["name"] == casa_chiusa.name
        assert "pin" not in r.json()["utente"]
        assert c.get("/api/modes").status_code == 200


def test_accesso_con_pin_errato(casa_chiusa) -> None:
    with TestClient(app) as c:
        r = c.post("/api/auth/login", json={"pin": "000000", "user_id": casa_chiusa.id})
        assert r.status_code == 401
        assert c.get("/api/modes").status_code == 401


def test_il_pin_di_un_familiare_non_apre_la_sessione_di_un_altro(casa_chiusa) -> None:
    """Il punto dell'identita' per persona: il PIN vale per chi lo possiede."""
    utenti = user_manager.get_users()
    utenti.append(type(casa_chiusa)(id="figlio_prova", name="Figlio", role="teen", age_group="teen"))
    user_manager.save_users(utenti)
    user_manager.imposta_pin("figlio_prova", "111111")
    try:
        with TestClient(app) as c:
            # il PIN del figlio non apre la sessione dell'amministratore
            r = c.post("/api/auth/login", json={"pin": "111111", "user_id": casa_chiusa.id})
            assert r.status_code == 401
            # ma apre la propria
            r = c.post("/api/auth/login", json={"pin": "111111", "user_id": "figlio_prova"})
            assert r.status_code == 200
            assert r.json()["utente"]["id"] == "figlio_prova"
    finally:
        user_manager.delete_user("figlio_prova")


def test_uscire_chiude_la_sessione(casa_chiusa) -> None:
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": casa_chiusa.id})
        assert c.get("/api/modes").status_code == 200
        c.post("/api/auth/logout")
        assert c.get("/api/modes").status_code == 401


def test_troppi_tentativi_bloccano(casa_chiusa) -> None:
    with TestClient(app) as c:
        for _ in range(sicurezza.TENTATIVI_MAX):
            c.post("/api/auth/login", json={"pin": "000000", "user_id": casa_chiusa.id})
        r = c.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": casa_chiusa.id})
        assert r.status_code == 429, "il PIN corretto non deve sbloccare un client gia' limitato"


# ------------------------------------------------------------------------ PIN


def test_il_pin_non_e_mai_salvato_in_chiaro() -> None:
    cifrato = sicurezza.cifra_pin("1234")
    assert "1234" not in cifrato
    assert cifrato.startswith("pbkdf2_sha256$")
    assert sicurezza.verifica_pin("1234", cifrato)
    assert not sicurezza.verifica_pin("1235", cifrato)


def test_due_pin_uguali_hanno_hash_diversi() -> None:
    """Sale casuale: due familiari con lo stesso PIN non sono riconoscibili
    confrontando il file, e una tabella precalcolata non serve a nulla."""
    assert sicurezza.cifra_pin("1234") != sicurezza.cifra_pin("1234")


@pytest.mark.parametrize("valore", [None, "", "non-un-hash", "pbkdf2_sha256$rotto"])
def test_un_hash_malformato_non_autorizza(valore) -> None:
    assert not sicurezza.verifica_pin("1234", valore)


def test_cambiare_pin_chiude_le_sessioni_aperte(casa_chiusa) -> None:
    """Se il PIN e' stato cambiato perche' qualcuno lo aveva scoperto,
    lasciare aperte le sessioni vecchie renderebbe il cambio inutile."""
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": casa_chiusa.id})
        assert c.get("/api/modes").status_code == 200
        r = c.post(f"/api/users/{casa_chiusa.id}/pin", json={"pin": "999888"})
        assert r.status_code == 200
        assert r.json()["sessioni_chiuse"] >= 1
        assert c.get("/api/modes").status_code == 401


def test_modificare_un_profilo_non_ne_cancella_il_pin(casa_chiusa) -> None:
    """L'interfaccia non rimanda il PIN quando salva un profilo: senza la
    protezione in upsert_user, rinominare un utente lo chiuderebbe fuori."""
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": casa_chiusa.id})
        profilo = casa_chiusa.model_dump()
        profilo["pin"] = None
        profilo["notes"] = "modificato dal test"
        assert c.post("/api/users", json=profilo).status_code == 200
    assert user_manager.get_user_by_id(casa_chiusa.id).pin, "il PIN e' stato cancellato"


# ------------------------------------------- PIN in chiaro da versioni vecchie


def test_un_pin_in_chiaro_non_chiude_fuori_la_famiglia() -> None:
    """Il difetto che ha davvero chiuso fuori il proprietario.

    `_prepara_accesso` si fermava se un profilo aveva un `pin` qualsiasi. Con
    un valore in chiaro rimasto da una versione precedente, l'autenticazione
    risultava attiva, nessun PIN nuovo veniva generato, e quel valore non
    poteva essere riconosciuto perche' il confronto si aspetta un hash:
    nessuno riusciva piu' a entrare, e non c'era modo di accorgersene.
    """
    from server.app import _prepara_accesso

    era_attiva = settings.security.auth_enabled
    originali = user_manager.get_users()
    salvati = [u.model_copy(deep=True) for u in originali]
    settings.security.auth_enabled = True

    try:
        utenti = user_manager.get_users()
        utenti[0].pin = "1234"  # in chiaro, come lo lasciava una versione vecchia
        user_manager.save_users(utenti)

        # Un PIN non cifrato non deve valere come "qualcuno puo' accedere".
        assert not sicurezza.autenticazione_attiva()

        _prepara_accesso()

        dopo = user_manager.get_users()[0]
        assert sicurezza.e_cifrato(dopo.pin), "il PIN in chiaro non e' stato cifrato"
        assert sicurezza.verifica_pin("1234", dopo.pin), "il PIN di prima non funziona piu'"
        assert sicurezza.autenticazione_attiva()
    finally:
        user_manager.save_users(salvati)
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()


def test_senza_alcun_pin_ne_viene_generato_uno() -> None:
    """Nessuno deve restare chiuso fuori: se non c'e' modo di entrare, se ne crea uno."""
    from server.app import _prepara_accesso

    era_attiva = settings.security.auth_enabled
    salvati = [u.model_copy(deep=True) for u in user_manager.get_users()]
    settings.security.auth_enabled = True

    try:
        utenti = user_manager.get_users()
        for u in utenti:
            u.pin = None
        user_manager.save_users(utenti)
        assert not sicurezza.autenticazione_attiva()

        _prepara_accesso()

        assert any(sicurezza.e_cifrato(u.pin) for u in user_manager.get_users())
        assert sicurezza.autenticazione_attiva()
    finally:
        user_manager.save_users(salvati)
        settings.security.auth_enabled = era_attiva
        sicurezza.azzera_stato()
