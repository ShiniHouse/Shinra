"""Il grafo del Cervello dice la verita' sulla casa (issue #185).

La scheda «Il Cervello» mostra nodi e collegamenti. Questi test guardano il
lato server, e difendono quattro promesse:

- **ogni oggetto compare una volta sola**, e nessun cavo punta nel vuoto;
- **un collegamento e' vero**: dice una cosa che il sistema sa;
- **il contenuto della conoscenza non esce mai**;
- **lo stato dei sistemi viene dal programma**: una regola spenta e Home
  Assistant irraggiungibile risultano `fermo` e `non_raggiungibile`, col loro
  motivo, e tornano `attivo` quando si riaccendono.
"""

from __future__ import annotations

import json
import time

import pytest

from shinra.domain import cervello as dominio
from shinra.infra.db import depositi
from shinra.services import cervello as servizio
from shinra.services import eventi_casa, permessi
from shinra.services.user_manager import UserProfile

SEGRETO = "il codice del cancello e' 4711"


@pytest.fixture(autouse=True)
def _senza_cache_di_ollama():
    servizio.dimentica_il_modello()
    yield
    servizio.dimentica_il_modello()


@pytest.fixture
def casa(monkeypatch):
    """Una casa di esempio: due stanze, tre dispositivi, una routine, due regole, un fatto."""
    depositi.alias.sostituisci_tutto(
        [
            {
                "id": "a1",
                "alias": "luce cucina",
                "entity_id": "light.cucina",
                "room": "Cucina",
                "domain": "light",
            },
            {
                "id": "a2",
                "alias": "luce salotto",
                "entity_id": "light.salotto",
                "room": "Salotto",
                "domain": "light",
            },
            {
                "id": "a3",
                "alias": "clima camera",
                "entity_id": "climate.camera",
                "room": "",
                "domain": "climate",
            },
        ]
    )
    depositi.modalita.sostituisci_tutto(
        [
            {
                "id": "m1",
                "name": "Cinema",
                "trigger_phrases": ["modalità cinema"],
                "enabled": True,
                "actions": [],
                "nodes": [
                    {"id": "n1", "type": "trigger", "data": {}},
                    {
                        "id": "n2",
                        "type": "ha_device",
                        "data": {"entity_id": "light.salotto", "action": "turn_off"},
                    },
                ],
                "edges": [{"from": "n1", "to": "n2"}],
            }
        ]
    )
    depositi.regole.sostituisci_tutto(
        [
            {
                "id": "r1",
                "nome": "Luce cucina al tramonto",
                "attiva": True,
                "trigger": {"tipo": "tramonto"},
                "condizioni": [],
                "azioni": [{"tipo": "dispositivo", "entity_id": "light.cucina", "azione": "turn_on"}],
                "origine": "",
            },
            {
                "id": "r2",
                "nome": "Cinema alle nove",
                "attiva": True,
                "trigger": {"tipo": "orario", "ora": "21:00"},
                "condizioni": [],
                "azioni": [{"tipo": "dispositivo", "entity_id": "light.salotto", "azione": "turn_off"}],
                "origine": "grafo:m1",
            },
        ]
    )
    depositi.fatti.sostituisci_tutto([{"id": "k1", "text": SEGRETO, "category": "casa", "enabled": True}])
    depositi.fonti.sostituisci_tutto(
        [{"id": "f1", "name": "ANSA", "category": "generale", "url": "http://x", "enabled": True}]
    )

    from shinra.config.settings import settings

    monkeypatch.setattr(settings.home_assistant, "enabled", True)
    monkeypatch.setattr(eventi_casa, "in_ascolto", lambda: True)

    class OllamaFinto:
        base_url = "http://ollama.finto"
        model = "qwen2.5:3b"

        async def get_available_models(self):
            return ["qwen2.5:3b"]

    monkeypatch.setattr(servizio, "OllamaClient", OllamaFinto)


def _per_id(grafo):
    return {n["id"]: n for n in grafo["nodi"]}


# ------------------------------------------------ ogni oggetto, una volta sola


async def test_ogni_oggetto_della_casa_compare_come_nodo_una_volta_sola(casa):
    grafo = await servizio.genera(None)
    id_nodi = [n["id"] for n in grafo["nodi"]]

    assert len(id_nodi) == len(set(id_nodi)), "un nodo compare due volte"
    for atteso in (
        "stanza:cucina",
        "stanza:salotto",
        "dispositivo:light.cucina",
        "dispositivo:light.salotto",
        "dispositivo:climate.camera",
        "alias:a1",
        "alias:a2",
        "alias:a3",
        "routine:m1",
        "regola:r1",
        "regola:r2",
        "fatto:k1",
        "argomento:casa",
    ):
        assert atteso in id_nodi, f"{atteso} non compare nel grafo"


async def test_gli_strumenti_del_catalogo_compaiono_col_loro_dominio(casa):
    grafo = await servizio.genera(None)
    per_id = _per_id(grafo)

    assert "strumento:get_weather" in per_id and per_id["strumento:get_weather"]["dominio"] == "informazioni"
    assert "dominio:informazioni" in per_id
    cavi = {(c["da"], c["a"]) for c in grafo["collegamenti"]}
    assert ("strumento:get_weather", "dominio:informazioni") in cavi


# ------------------------------------------------------ i cavi dicono il vero


async def test_nessun_collegamento_punta_a_un_nodo_che_non_esiste(casa):
    grafo = await servizio.genera(None)
    nodi = {n["id"] for n in grafo["nodi"]}

    fuori = [c for c in grafo["collegamenti"] if c["da"] not in nodi or c["a"] not in nodi]
    assert fuori == []


async def test_i_collegamenti_sono_quelli_che_il_sistema_sa(casa):
    grafo = await servizio.genera(None)
    cavi = {(c["da"], c["a"], c["tipo"]) for c in grafo["collegamenti"]}

    assert ("alias:a1", "dispositivo:light.cucina", "chiama") in cavi
    assert ("dispositivo:light.cucina", "stanza:cucina", "sta_in") in cavi
    assert ("regola:r1", "dispositivo:light.cucina", "comanda") in cavi
    assert ("routine:m1", "dispositivo:light.salotto", "comanda") in cavi
    # la regola nata dall'editor sa da quale routine viene
    assert ("regola:r2", "routine:m1", "nasce_da") in cavi
    assert ("fatto:k1", "argomento:casa", "riguarda") in cavi
    # e un dispositivo senza stanza non ne ha una inventata
    assert not [c for c in cavi if c[0] == "dispositivo:climate.camera" and c[2] == "sta_in"]


def test_un_cavo_verso_il_vuoto_si_scarta_e_non_si_conta():
    grafo = dominio.costruisci(
        alias=[{"id": "a1", "alias": "luce", "entity_id": "light.x", "room": ""}],
        routine=[{"id": "m1", "name": "Solo", "nodes": [], "actions": []}],
        regole=[{"id": "r1", "nome": "Orfana", "attiva": True, "origine": "grafo:cancellata"}],
    )

    assert [c for c in grafo["collegamenti"] if c["a"] == "routine:cancellata"] == []
    assert grafo["contatori"]["collegamenti"] == len(grafo["collegamenti"])


def test_un_dispositivo_comandato_senza_alias_compare_col_suo_codice():
    grafo = dominio.costruisci(
        regole=[
            {"id": "r1", "nome": "Senza alias", "attiva": True, "azioni": [{"entity_id": "switch.pompa"}]}
        ]
    )
    nodi = {n["id"]: n for n in grafo["nodi"]}

    assert nodi["dispositivo:switch.pompa"]["nome"] == "switch.pompa"


# ---------------------------------------------------- la conoscenza non esce


async def test_il_contenuto_dei_fatti_non_compare_da_nessuna_parte(casa):
    grafo = await servizio.genera(None)

    assert SEGRETO not in json.dumps(grafo, ensure_ascii=False)
    fatto = _per_id(grafo)["fatto:k1"]
    assert fatto["nome"] == "casa", "il nodo di un fatto porta il testo invece dell'argomento"


async def test_chi_non_puo_leggere_la_conoscenza_non_la_vede(casa):
    depositi.ruoli.salva(
        {
            "id": "solo_luci",
            "nome": "Solo luci",
            "descrizione": "",
            "permessi": [permessi.COMANDA_DISPOSITIVI],
            "predefinito": False,
        }
    )
    limitato = UserProfile(id="ospite", name="Ospite", role="solo_luci")

    grafo = await servizio.genera(limitato)
    tipi = {n["tipo"] for n in grafo["nodi"]}

    assert "fatto" not in tipi and "argomento" not in tipi
    assert {"alias", "routine", "regola"} <= tipi, "gli altri nodi devono restare: li vede gia' altrove"


def test_senza_autenticazione_l_endpoint_risponde_401():
    from fastapi.testclient import TestClient

    from shinra.api.app import app

    with TestClient(app) as client:
        assert client.get("/api/cervello").status_code == 401


def test_l_endpoint_risponde_con_la_forma_promessa(cliente_autenticato, casa):
    risposta = cliente_autenticato.get("/api/cervello")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert set(corpo) == {"nodi", "collegamenti", "clusters", "sistemi", "contatori", "troncato"}
    assert {"nodi", "collegamenti", "sistemi", "sistemi_attivi", "agenti_pronti"} <= set(corpo["contatori"])


# ---------------------------------------------------- lo stato dei sistemi


def _sistema(grafo, id_):
    return next(s for s in grafo["sistemi"] if s["id"] == id_)


async def test_una_regola_disattivata_rende_il_sistema_fermo_col_suo_motivo(casa):
    depositi.regole.aggiorna("r1", {"attiva": False})

    grafo = await servizio.genera(None)
    regole = _sistema(grafo, "regole")

    assert regole["stato"] == dominio.FERMO
    assert "Luce cucina al tramonto" in regole["motivo"]
    assert _per_id(grafo)["regola:r1"]["stato"] == dominio.FERMO

    depositi.regole.aggiorna("r1", {"attiva": True})
    assert _sistema(await servizio.genera(None), "regole")["stato"] == dominio.ATTIVO


async def test_home_assistant_irraggiungibile_e_non_raggiungibile(casa, monkeypatch):
    monkeypatch.setattr(eventi_casa, "in_ascolto", lambda: False)

    ha = _sistema(await servizio.genera(None), "home_assistant")

    assert ha["stato"] == dominio.NON_RAGGIUNGIBILE and ha["motivo"]

    monkeypatch.setattr(eventi_casa, "in_ascolto", lambda: True)
    assert _sistema(await servizio.genera(None), "home_assistant")["stato"] == dominio.ATTIVO


async def test_home_assistant_spento_nelle_impostazioni_e_fermo(casa, monkeypatch):
    from shinra.config.settings import settings

    monkeypatch.setattr(settings.home_assistant, "enabled", False)

    ha = _sistema(await servizio.genera(None), "home_assistant")

    assert ha["stato"] == dominio.FERMO and "disattivato" in ha["motivo"]


async def test_un_modello_che_non_c_e_dice_quale_scaricare(casa, monkeypatch):
    class SenzaModello:
        base_url = "http://ollama.finto"
        model = "qwen2.5:3b"

        async def get_available_models(self):
            return ["llama3.2:1b"]

    monkeypatch.setattr(servizio, "OllamaClient", SenzaModello)

    modello = _sistema(await servizio.genera(None), "modello")

    assert modello["stato"] == dominio.FERMO and "ollama pull qwen2.5:3b" in modello["motivo"]


async def test_ollama_spento_non_fa_aspettare_la_scheda(casa, monkeypatch):
    import asyncio

    class Lento:
        base_url = "http://ollama.finto"
        model = "qwen2.5:3b"

        async def get_available_models(self):
            await asyncio.sleep(30)
            return ["qwen2.5:3b"]

    monkeypatch.setattr(servizio, "OllamaClient", Lento)
    monkeypatch.setattr(servizio, "ATTESA_OLLAMA", 0.2)

    inizio = time.monotonic()
    modello = _sistema(await servizio.genera(None), "modello")

    assert time.monotonic() - inizio < 2, "la scheda ha aspettato Ollama invece di dire che non risponde"
    assert modello["stato"] == dominio.NON_RAGGIUNGIBILE


def test_uno_stato_sconosciuto_non_passa_per_attivo():
    grafo = dominio.costruisci(sistemi=[{"id": "x", "nome": "X", "stato": "benissimo"}])

    assert grafo["sistemi"][0]["stato"] == dominio.NON_RAGGIUNGIBILE
    assert grafo["contatori"]["sistemi_attivi"] == 0


def test_i_contatori_vengono_dagli_stessi_dati_del_grafo():
    grafo = dominio.costruisci(
        alias=[{"id": "a1", "alias": "luce", "entity_id": "light.x", "room": "Sala"}],
        sistemi=[
            {"id": "a", "nome": "A", "stato": dominio.ATTIVO},
            {"id": "b", "nome": "B", "stato": dominio.FERMO, "motivo": "spento"},
        ],
        agenti=[{"nome": "luci", "pronto": True}, {"nome": "clima", "pronto": False}],
    )
    c = grafo["contatori"]

    assert c["collegamenti"] == len(grafo["collegamenti"]) and c["nodi"] == len(grafo["nodi"])
    assert c["sistemi"] == 2 and c["sistemi_attivi"] == 1 and c["agenti_pronti"] == 1


# ---------------------------------------------------------------- il tetto


def test_oltre_il_tetto_si_tengono_i_nodi_importanti_e_gli_altri_si_contano():
    fatti = [{"id": f"k{i}", "text": "x", "category": "casa"} for i in range(50)]
    alias = [
        {"id": f"a{i}", "alias": f"luce {i}", "entity_id": f"light.l{i}", "room": "Sala"} for i in range(10)
    ]

    grafo = dominio.costruisci(alias=alias, fatti=fatti, massimo_nodi=30)

    assert len(grafo["nodi"]) == 30 and grafo["troncato"] is True
    nodi = {n["id"] for n in grafo["nodi"]}
    assert "stanza:sala" in nodi, "la stanza e' il primo a restare"
    conoscenza = next(c for c in grafo["clusters"] if c["id"] == "conoscenza")
    assert conoscenza["nascosti"] > 0 and conoscenza["nodi"] + conoscenza["nascosti"] == 51
    # i cavi che puntavano a un nodo nascosto non restano
    assert all(c["da"] in nodi and c["a"] in nodi for c in grafo["collegamenti"])


async def test_una_casa_grande_si_descrive_in_meno_di_un_secondo(casa):
    depositi.alias.sostituisci_tutto(
        [
            {
                "id": f"a{i}",
                "alias": f"luce {i}",
                "entity_id": f"light.l{i}",
                "room": f"Stanza {i % 12}",
                "domain": "light",
            }
            for i in range(500)
        ]
    )
    depositi.fatti.sostituisci_tutto(
        [{"id": f"k{i}", "text": f"fatto {i}", "category": f"c{i % 9}"} for i in range(300)]
    )

    inizio = time.monotonic()
    grafo = await servizio.genera(None)
    durata = time.monotonic() - inizio

    assert durata < 1.0, f"il grafo di una casa grande ha impiegato {durata:.2f}s"
    assert len(grafo["nodi"]) <= dominio.MASSIMO_NODI
    assert grafo["troncato"] is True
