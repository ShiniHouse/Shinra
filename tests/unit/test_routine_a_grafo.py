"""L'esecuzione di una routine disegnata a nodi.

`test_grafo.py` prova le decisioni; qui si prova che l'esecutore le rispetti.
Sono due cose diverse e si rompono separatamente: un dominio corretto chiamato
male esegue il ramo sbagliato con la stessa naturalezza di un dominio
sbagliato.

Nessuno di questi test tocca la rete: il client di Home Assistant e' sostituito,
e cio' che si verifica e' **quale servizio chiediamo**.

Riferimento: issue #28.
"""

from __future__ import annotations

import pytest

from shinra.domain import grafo as dominio
from shinra.domain.eventi import RICHIESTA_AVVISO, Evento, bus
from shinra.infra.db import depositi
from shinra.skills import ha_tools

# Una casa con una persona a casa e una luce accesa: basta a far scattare le
# due condizioni che questi test usano.
STATI = [
    {"entity_id": "person.alessio", "state": "home", "attributes": {"friendly_name": "Alessio"}},
    {"entity_id": "light.salotto", "state": "on", "attributes": {"friendly_name": "Salotto"}},
]


@pytest.fixture
def casa(monkeypatch):
    chiamate: list[tuple[str, str, dict]] = []

    class FintoClient:
        async def call_service(self, dominio_ha, servizio, dati=None):
            chiamate.append((dominio_ha, servizio, dati or {}))
            return {"success": True}

        async def get_states(self):
            return STATI

        async def stati_correnti(self):
            return STATI

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: FintoClient())
    return chiamate


def _salva(nodi, archi, nome: str = "prova") -> None:
    depositi.modalita.sostituisci_tutto(
        [
            {
                "id": "m1",
                "name": nome,
                "enabled": True,
                "trigger_phrases": [nome],
                "nodes": nodi,
                "edges": archi,
            }
        ]
    )


def test_il_disegno_dell_editor_sopravvive_al_salvataggio():
    """Il difetto piu' grosso trovato lavorando a questa scheda, e quello che
    rendeva vana tutto il resto.

    Le colonne `nodes` ed `edges` non esistevano nella tabella delle routine.
    L'editor le mandava, il deposito copiava solo i campi che conosceva, e il
    disegno spariva — senza errori, senza avvisi. Di conseguenza l'esecutore
    non ha **mai** visto un grafo in produzione: le sue novanta righe di
    visita in ampiezza erano codice irraggiungibile.
    """
    from shinra.infra.data_store import data_store

    nodi = [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO, entity_id="light.x")]
    archi = [_a("t", "luce")]

    data_store.salva_modalita(
        {"id": "disegnata", "name": "Disegnata", "enabled": True, "nodes": nodi, "edges": archi}
    )
    riletta = next(m for m in data_store.get_modes() if m["id"] == "disegnata")

    assert riletta["nodes"] == nodi, "il disegno e' stato scartato dal salvataggio"
    assert riletta["edges"] == archi


def _n(identificativo: str, tipo: str, **dati) -> dict:
    return {"id": identificativo, "type": tipo, "data": dati}


def _a(partenza: str, arrivo: str, ramo: str | None = None) -> dict:
    arco = {"from": partenza, "to": arrivo}
    if ramo:
        arco["ramo"] = ramo
    return arco


# ------------------------------------------------------- il ramo percorso


async def test_una_routine_con_condizione_percorre_il_ramo_giusto(casa):
    """Il criterio della scheda: «una routine con una condizione percorre il
    ramo corretto in esecuzione reale».

    In casa c'e' Alessio, quindi la condizione «casa abitata» e' vera e deve
    accendersi la luce del ramo vero — non quella del ramo falso, e non
    entrambe.
    """
    _salva(
        [
            _n("t", dominio.TRIGGER),
            _n("se", dominio.CONDIZIONE, condizione={"tipo": "presenza", "abitata": True}),
            _n("si", dominio.DISPOSITIVO, entity_id="light.bentornato", action="turn_on"),
            _n("no", dominio.DISPOSITIVO, entity_id="light.nessuno", action="turn_on"),
        ],
        [_a("t", "se"), _a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)],
    )

    esito = await ha_tools.activate_mode("prova")

    entita = [dati.get("entity_id") for _, _, dati in casa]
    assert entita == ["light.bentornato"], "il ramo falso non doveva essere eseguito"
    assert esito["decisioni"] == [{"node_id": "se", "ramo": dominio.VERO, "motivo": ""}]


async def test_il_ramo_falso_si_percorre_quando_la_condizione_non_regge(casa):
    """La luce del salotto e' accesa: la condizione «e' spenta» e' falsa."""
    _salva(
        [
            _n("t", dominio.TRIGGER),
            _n(
                "se",
                dominio.CONDIZIONE,
                condizione={"tipo": "stato_entita", "entity_id": "light.salotto", "stato": "off"},
            ),
            _n("si", dominio.DISPOSITIVO, entity_id="light.si", action="turn_on"),
            _n("no", dominio.DISPOSITIVO, entity_id="light.no", action="turn_on"),
        ],
        [_a("t", "se"), _a("se", "si", dominio.VERO), _a("se", "no", dominio.FALSO)],
    )

    esito = await ha_tools.activate_mode("prova")

    assert [d.get("entity_id") for _, _, d in casa] == ["light.no"]
    assert esito["decisioni"][0]["ramo"] == dominio.FALSO
    assert "on" in esito["decisioni"][0]["motivo"]


async def test_una_routine_lineare_continua_a_funzionare(casa):
    """Le routine gia' salvate sono tutte cosi': romperle sarebbe un prezzo
    che nessuno ha chiesto di pagare."""
    _salva(
        [
            _n("t", dominio.TRIGGER),
            _n("uno", dominio.DISPOSITIVO, entity_id="light.uno", action="turn_on"),
            _n("due", dominio.DISPOSITIVO, entity_id="light.due", action="turn_off"),
        ],
        [_a("t", "uno"), _a("uno", "due")],
    )

    await ha_tools.activate_mode("prova")

    assert [(s, d.get("entity_id")) for _, s, d in casa] == [
        ("turn_on", "light.uno"),
        ("turn_off", "light.due"),
    ]


async def test_senza_condizioni_non_si_interroga_la_casa(monkeypatch):
    """Una routine lineare non deve pagare un giro a Home Assistant per
    leggere stati che nessuno guardera'."""
    letture = []

    class FintoClient:
        async def call_service(self, dominio_ha, servizio, dati=None):
            return {"success": True}

        async def stati_correnti(self):
            letture.append(1)
            return STATI

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: FintoClient())
    _salva(
        [_n("t", dominio.TRIGGER), _n("uno", dominio.DISPOSITIVO, entity_id="light.uno")],
        [_a("t", "uno")],
    )

    await ha_tools.activate_mode("prova")

    assert letture == [], "nessuna condizione da valutare, nessuna lettura da fare"


async def test_una_casa_irraggiungibile_non_e_un_errore_di_grafo(monkeypatch):
    """Se Home Assistant non risponde, le condizioni si valutano senza stati:
    la routine fa quello che puo' invece di non fare niente."""

    class ClienteRotto:
        async def call_service(self, dominio_ha, servizio, dati=None):
            return {"success": True}

        async def stati_correnti(self):
            raise ConnectionError("casa irraggiungibile")

    monkeypatch.setattr(ha_tools, "client_home_assistant", lambda: ClienteRotto())
    _salva(
        [
            _n("t", dominio.TRIGGER),
            _n("se", dominio.CONDIZIONE, condizione={"tipo": "presenza", "abitata": True}),
            _n("no", dominio.DISPOSITIVO, entity_id="light.no"),
        ],
        [_a("t", "se"), _a("se", "no", dominio.FALSO)],
    )

    esito = await ha_tools.activate_mode("prova")

    assert esito["success"] is True
    assert esito["decisioni"][0]["ramo"] == dominio.FALSO


# ---------------------------------------------------------- la notifica


async def test_il_nodo_notifica_chiede_un_avviso_sul_bus(casa):
    """Una capacita' non puo' chiamare il servizio delle notifiche — sta sotto
    di esso — quindi pubblica, e chi sa mandarle raccoglie."""
    visti: list[Evento] = []
    annulla = bus.sottoscrivi(RICHIESTA_AVVISO, lambda e: visti.append(e))
    try:
        _salva(
            [
                _n("t", dominio.TRIGGER),
                _n("avvisa", dominio.NOTIFICA, titolo="Cena", testo="la pasta e' pronta"),
            ],
            [_a("t", "avvisa")],
        )

        esito = await ha_tools.activate_mode("prova")
    finally:
        annulla()

    assert len(visti) == 1
    assert visti[0].dati["titolo"] == "Cena"
    assert visti[0].dati["testo"] == "la pasta e' pronta"
    assert [a["type"] for a in esito["azioni_eseguite"]] == ["notifica"]


async def test_una_notifica_senza_testo_non_parte(casa):
    """Un nodo appena trascinato e non ancora compilato non deve mandare una
    notifica vuota al telefono di tutti."""
    visti: list[Evento] = []
    annulla = bus.sottoscrivi(RICHIESTA_AVVISO, lambda e: visti.append(e))
    try:
        _salva(
            [_n("t", dominio.TRIGGER), _n("avvisa", dominio.NOTIFICA, titolo="Vuota")],
            [_a("t", "avvisa")],
        )
        esito = await ha_tools.activate_mode("prova")
    finally:
        annulla()

    assert visti == []
    assert esito["azioni_eseguite"][0]["status"] is False


async def test_la_notifica_e_distinta_dall_annuncio(casa):
    """Un annuncio lo sente chi e' nella stanza, una notifica raggiunge il
    telefono di chi non c'e'. Prima si poteva scrivere solo la prima."""
    visti: list[Evento] = []
    annulla = bus.sottoscrivi(RICHIESTA_AVVISO, lambda e: visti.append(e))
    try:
        _salva(
            [
                _n("t", dominio.TRIGGER),
                _n("voce", dominio.ANNUNCIO, message="detto a voce"),
                _n("push", dominio.NOTIFICA, testo="mandato al telefono"),
            ],
            [_a("t", "voce"), _a("voce", "push")],
        )
        esito = await ha_tools.activate_mode("prova")
    finally:
        annulla()

    assert "detto a voce" in esito["messaggio"]
    assert len(visti) == 1
    assert visti[0].dati["testo"] == "mandato al telefono"


# ------------------------------------------------ il salvataggio validato


def test_un_grafo_con_un_ciclo_non_si_salva(cliente_autenticato):
    """Il criterio della scheda: «un grafo non valido non puo' essere salvato,
    e l'errore dice cosa non va»."""
    risposta = cliente_autenticato.post(
        "/api/modes",
        json={
            "id": "m9",
            "name": "avvitata",
            "nodes": [_n("a", dominio.DISPOSITIVO), _n("b", dominio.DISPOSITIVO)],
            "edges": [_a("a", "b"), _a("b", "a")],
        },
    )

    assert risposta.status_code == 400
    dettaglio = risposta.json()["detail"]
    assert any(p["tipo"] == dominio.CICLO for p in dettaglio["problemi"])
    assert "a" in dettaglio["messaggio"] and "b" in dettaglio["messaggio"]


def test_un_grafo_valido_si_salva(cliente_autenticato):
    risposta = cliente_autenticato.post(
        "/api/modes",
        json={
            "id": "m8",
            "name": "buona",
            "nodes": [_n("t", dominio.TRIGGER), _n("luce", dominio.DISPOSITIVO)],
            "edges": [_a("t", "luce")],
        },
    )

    assert risposta.status_code == 200
    assert risposta.json()["success"] is True


def test_una_routine_senza_grafo_si_salva_lo_stesso(cliente_autenticato):
    """Le routine con l'elenco lineare di azioni sono la forma vecchia, e
    sono ancora in giro: rifiutarle vorrebbe dire non poterle piu' modificare."""
    risposta = cliente_autenticato.post(
        "/api/modes",
        json={"id": "m7", "name": "vecchia", "actions": [{"type": "tts", "message": "ciao"}]},
    )

    assert risposta.status_code == 200


def test_si_puo_chiedere_cosa_non_va_senza_salvare(cliente_autenticato):
    """L'editor la chiama mentre si disegna: saperlo mentre lo si sta facendo
    e' un'altra cosa dal saperlo quando il disegno e' finito."""
    prima = len(depositi.modalita.elenco())

    risposta = cliente_autenticato.post(
        "/api/modes/valida",
        json={
            "nodes": [_n("se", dominio.CONDIZIONE), _n("si", dominio.ANNUNCIO)],
            "edges": [_a("se", "si", dominio.VERO)],
        },
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["valido"] is False
    assert corpo["problemi"][0]["nodi"] == ["se"]
    assert len(depositi.modalita.elenco()) == prima, "validare non deve salvare"
