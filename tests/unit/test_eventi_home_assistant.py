"""La casa che dice cosa succede.

Fino alla v0.2.0 ogni informazione da Home Assistant era una fotografia su
domanda: il sistema non sapeva mai **quando** qualcosa accadeva, e senza quel
«quando» una regola come «se la porta si apre dopo le 23, accendi l'ingresso»
non e' scrivibile.

Tutto quello che decide qualcosa sta in `Protocollo`, che non conosce il
socket: riceve dizionari e restituisce dizionari. Per questo questo file non
ha bisogno di un finto server, di attese, ne' di una rete — e infatti prova
il dialogo per intero, compresi i casi che con un server vero si vedrebbero
una volta l'anno.

Riferimento: issue #19.
"""

from __future__ import annotations

import pytest

from shinra.domain import eventi as dominio
from shinra.infra.homeassistant.eventi import (
    ATTESA_MASSIMA,
    ErroreAutenticazione,
    Protocollo,
    attesa_successiva,
    indirizzo_websocket,
)
from shinra.infra.homeassistant.stati import CacheStati, riassumi

TOKEN = "token-di-prova-lungo-abbastanza"


@pytest.fixture
def cache() -> CacheStati:
    return CacheStati()


@pytest.fixture
def raccolti(monkeypatch) -> list[dominio.Evento]:
    """Cattura cio' che finisce sul bus, senza toccare il ciclo asincrono."""
    visti: list[dominio.Evento] = []
    monkeypatch.setattr(dominio.bus, "pubblica_senza_attendere", visti.append)
    return visti


def _stato(entity_id: str, valore: str, nome: str = "") -> dict:
    return {
        "entity_id": entity_id,
        "state": valore,
        "attributes": {"friendly_name": nome} if nome else {},
    }


def _cambiamento(entity_id: str, da: str | None, a: str | None, nome: str = "") -> dict:
    return {
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {
                "entity_id": entity_id,
                "old_state": _stato(entity_id, da, nome) if da is not None else None,
                "new_state": _stato(entity_id, a, nome) if a is not None else None,
            },
        },
    }


# ----------------------------------------------------------- il dialogo


def test_al_saluto_si_risponde_con_il_token(cache):
    protocollo = Protocollo(TOKEN, cache=cache)

    risposte = protocollo.ricevi({"type": "auth_required", "ha_version": "2026.9"})

    assert risposte == [{"type": "auth", "access_token": TOKEN}]
    assert protocollo.autenticato is False


def test_dopo_l_autenticazione_ci_si_sottoscrive_agli_eventi(cache):
    protocollo = Protocollo(TOKEN, cache=cache)

    risposte = protocollo.ricevi({"type": "auth_ok", "ha_version": "2026.9"})

    assert protocollo.autenticato is True
    assert risposte == [
        {"id": Protocollo.ID_SOTTOSCRIZIONE, "type": "subscribe_events", "event_type": "state_changed"}
    ]


def test_un_token_rifiutato_solleva_e_non_si_riprova(cache):
    """Riprovare con lo stesso token e' inutile: serve un token nuovo.

    E' la sola condizione in cui l'anello di riconnessione si arrende. Se
    fosse trattata come una caduta qualsiasi, il servizio insisterebbe per
    sempre riempiendo il log senza avvicinarsi alla soluzione.
    """
    protocollo = Protocollo(TOKEN, cache=cache)

    with pytest.raises(ErroreAutenticazione):
        protocollo.ricevi({"type": "auth_invalid", "message": "Invalid access token"})


def test_la_sottoscrizione_riuscita_viene_registrata(cache):
    protocollo = Protocollo(TOKEN, cache=cache)
    protocollo.ricevi({"type": "auth_ok"})

    protocollo.ricevi({"id": Protocollo.ID_SOTTOSCRIZIONE, "type": "result", "success": True})

    assert protocollo.sottoscritto is True


def test_una_sottoscrizione_rifiutata_non_si_finge_riuscita(cache):
    protocollo = Protocollo(TOKEN, cache=cache)
    protocollo.ricevi({"type": "auth_ok"})

    protocollo.ricevi(
        {"id": Protocollo.ID_SOTTOSCRIZIONE, "type": "result", "success": False, "error": {"code": "x"}}
    )

    assert protocollo.sottoscritto is False


def test_un_messaggio_sconosciuto_non_rompe_niente(cache):
    protocollo = Protocollo(TOKEN, cache=cache)

    assert protocollo.ricevi({"type": "qualcosa_di_nuovo"}) == []
    assert protocollo.ricevi({}) == []


# ------------------------------------------------------ i cambi di stato


def test_un_cambio_di_stato_finisce_nella_cache_e_sul_bus(cache, raccolti):
    protocollo = Protocollo(TOKEN, cache=cache)

    protocollo.ricevi(_cambiamento("light.cucina", "off", "on", "Luce cucina"))

    assert cache.stato("light.cucina")["state"] == "on"
    assert len(raccolti) == 1
    dati = raccolti[0].dati
    assert raccolti[0].tipo == dominio.HA_STATO_CAMBIATO
    assert dati["entity_id"] == "light.cucina"
    assert dati["stato"] == "on"
    assert dati["stato_precedente"] == "off"
    assert dati["nome"] == "Luce cucina"


def test_un_dominio_che_non_interessa_aggiorna_la_cache_ma_non_il_bus(cache, raccolti):
    """`state_changed` scatta per ogni entita' della casa.

    Le batterie dei telecomandi e i contatori di aggiornamenti firmware
    cambiano di continuo: farli arrivare alla dashboard vorrebbe dire
    inondarla di notizie che nessuno ha chiesto. In cache restano, perche'
    li' servono a rispondere «com'e' messo quel sensore».
    """
    protocollo = Protocollo(TOKEN, cache=cache)

    protocollo.ricevi(_cambiamento("sensor.batteria_telecomando", "51", "50"))

    assert cache.stato("sensor.batteria_telecomando")["state"] == "50"
    assert raccolti == []


def test_un_attributo_che_cambia_senza_lo_stato_non_e_una_notizia(cache, raccolti):
    """La luce era accesa e ha solo variato luminosita'."""
    protocollo = Protocollo(TOKEN, cache=cache)

    protocollo.ricevi(_cambiamento("light.salotto", "on", "on"))

    assert cache.stato("light.salotto") is not None
    assert raccolti == []


def test_un_entita_rimossa_esce_dalla_cache(cache, raccolti):
    protocollo = Protocollo(TOKEN, cache=cache)
    protocollo.ricevi(_cambiamento("light.vecchia", "off", "on"))
    raccolti.clear()

    protocollo.ricevi(_cambiamento("light.vecchia", "on", None))

    assert cache.stato("light.vecchia") is None
    assert raccolti == []


def test_un_evento_di_altro_tipo_viene_ignorato(cache, raccolti):
    protocollo = Protocollo(TOKEN, cache=cache)

    protocollo.ricevi({"type": "event", "event": {"event_type": "call_service", "data": {"domain": "light"}}})

    assert cache.quanti() == 0
    assert raccolti == []


def test_un_evento_senza_entita_non_solleva(cache, raccolti):
    protocollo = Protocollo(TOKEN, cache=cache)

    protocollo.ricevi(
        {"type": "event", "event": {"event_type": "state_changed", "data": {"new_state": None}}}
    )

    assert cache.quanti() == 0


# ----------------------------------------------------------- la cache


def test_la_cache_svuotata_non_racconta_stati_vecchi(cache):
    """Uno stato di dieci minuti fa e' peggio di un «non lo so».

    Alla caduta della connessione l'assistente direbbe che la luce e' accesa
    mentre e' spenta, e nessuno saprebbe perche'.
    """
    cache.sostituisci([_stato("light.cucina", "on", "Luce cucina")])
    assert cache.popolata

    cache.svuota()

    assert not cache.popolata
    assert cache.riassunto() == ""


def test_il_riassunto_salta_cio_che_non_si_sa():
    righe = riassumi(
        [
            _stato("light.cucina", "on", "Luce cucina"),
            _stato("light.rotta", "unavailable", "Luce rotta"),
            _stato("sensor.umidita", "62", "Umidita'"),
        ]
    )

    assert "Luce cucina (light.cucina): on" in righe
    assert "Luce rotta" not in righe
    assert "umidita" not in righe.lower()


def test_il_riassunto_ha_un_tetto():
    molte = [_stato(f"light.numero{n}", "on", f"Luce {n}") for n in range(40)]

    assert riassumi(molte).count(";") == 14  # quindici voci, quattordici separatori


def test_senza_nome_amichevole_si_usa_l_identificativo():
    assert "light.senza_nome (light.senza_nome): on" in riassumi([_stato("light.senza_nome", "on")])


# ------------------------------------------------- indirizzo e riconnessione


@pytest.mark.parametrize(
    ("base", "atteso"),
    [
        ("http://casa.local:8123", "ws://casa.local:8123/api/websocket"),
        ("https://casa.example.com", "wss://casa.example.com/api/websocket"),
        ("http://192.168.1.10:8123/", "ws://192.168.1.10:8123/api/websocket"),
    ],
)
def test_l_indirizzo_websocket_si_ricava_da_quello_rest(base, atteso):
    assert indirizzo_websocket(base) == atteso


def test_l_attesa_raddoppia_fino_a_un_tetto():
    """Home Assistant che si riavvia torna in pochi secondi; Home Assistant
    spento resta spento per ore, e insistere ogni secondo per ore riempie il
    log senza avvicinare la soluzione."""
    attese = []
    attesa = 2.0
    for _ in range(8):
        attese.append(attesa)
        attesa = attesa_successiva(attesa)

    assert attese[:5] == [2.0, 4.0, 8.0, 16.0, 32.0]
    assert attesa == ATTESA_MASSIMA


# ------------------------------------------- se abbia senso ascoltare


@pytest.mark.parametrize(
    ("token", "utilizzabile"),
    [
        ("", False),
        ("   ", False),
        ("corto", False),
        ("INSERISCI_QUI_IL_TUO_TOKEN_LUNGO_ABBASTANZA", False),
        (TOKEN, True),
    ],
)
def test_un_segnaposto_non_e_un_token(token, utilizzabile):
    """Il valore di esempio supera qualunque controllo di presenza.

    Senza questa verifica il servizio proverebbe a riconnettersi per sempre a
    un Home Assistant che lo rifiuta a ogni tentativo — e il rifiuto per
    token invalido e' l'unico caso in cui l'anello si arrende, quindi
    resterebbe a insistere fino al riavvio.
    """
    from shinra.services.eventi_casa import _token_utilizzabile

    assert _token_utilizzabile(token) is utilizzabile


async def test_con_home_assistant_disattivato_non_si_ascolta(monkeypatch):
    from shinra.config.settings import settings
    from shinra.services import eventi_casa

    monkeypatch.setattr(settings.home_assistant, "enabled", False)

    assert await eventi_casa.avvia() is False
