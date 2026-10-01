"""Le azioni sensibili chiedono sempre conferma (issue #192).

Un principio permanente di Shinra: il modello non e' fidato. Questi test mettono alla
prova i tre criteri della scheda, e li provano **dalla porta d'ingresso**: l'agente vero,
con un modello finto che sceglie lo strumento sbagliato, e Home Assistant finto che
annota ogni chiamata. Cio' che conta non e' il messaggio che torna, ma che nessuna
chiamata a una serratura parta.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

import pytest

from shinra.domain import sensibilita
from shinra.domain.contesto import come_modello
from shinra.infra.db import depositi
from shinra.services import conferme, permessi, registro
from shinra.services.agent import ShinraAgent
from shinra.services.intenti import Richiesta, instrada
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import (
    UserProfile,
    user_manager,
)
from shinra.skills import registry
from shinra.skills.registry import TOOL_HANDLERS, execute_tool

PORTA = "lock.porta_ingresso"
STATI = [
    {"entity_id": PORTA, "state": "locked", "attributes": {"friendly_name": "Porta d'ingresso"}},
    {
        "entity_id": "alarm_control_panel.casa",
        "state": "armed_away",
        "attributes": {"friendly_name": "Allarme"},
    },
    {"entity_id": "cover.garage", "state": "closed", "attributes": {"friendly_name": "Garage"}},
    {"entity_id": "cover.salotto", "state": "closed", "attributes": {"friendly_name": "Tapparella salotto"}},
    {"entity_id": "light.cucina", "state": "off", "attributes": {"friendly_name": "Luce cucina"}},
]


@pytest.fixture
def casa(monkeypatch):
    """Il client vero di Home Assistant — con il suo controllo del modello e dei permessi — ma la POST e' finta."""
    chiamate: list[tuple[str, str, dict]] = []

    from shinra.infra.homeassistant.client import HomeAssistantClient

    class Risposta:
        status_code = 200
        text = ""

        def json(self):
            return {}

    class Connessione:
        async def post(self, url, headers=None, json=None):
            dominio, servizio = url.rsplit("/api/services/", 1)[1].split("/")
            chiamate.append((dominio, servizio, json or {}))
            return Risposta()

    class Finto(HomeAssistantClient):
        token = "token-di-prova"
        base_url = "http://casa.invalid"

        def _connessione(self, timeout):
            return Connessione()

        async def stati_correnti(self):
            return [dict(s) for s in STATI]

    cliente = Finto()
    monkeypatch.setattr("shinra.infra.homeassistant.client.client_home_assistant", lambda: cliente)
    monkeypatch.setattr("shinra.skills.ha_tools.client_home_assistant", lambda: cliente)
    depositi.alias.sostituisci_tutto(
        [
            {"id": "a1", "alias": "serratura ingresso", "entity_id": PORTA},
            {"id": "a2", "alias": "luce cucina", "entity_id": "light.cucina"},
        ]
    )
    depositi.modalita.sostituisci_tutto([])
    # Un amministratore vero, con i permessi veri: il controllo dei permessi di Home Assistant resta acceso.
    permessi.assicura_ruoli_predefiniti()
    user_manager.upsert_user(UserProfile(id="alessio", name="Alessio", role="admin"))
    conferme.azzera()
    yield chiamate
    conferme.azzera()


def _come(attore: str | None, canale: str = "web", ignota: bool = False):
    ctx = registro.apri_contesto(attore=attore, canale=canale)
    ctx.identita_ignota = ignota
    return ctx


def _profilo(nome: str) -> UserProfile:
    return UserProfile(id=nome.lower(), name=nome)


def _chiamate_alla_serratura(chiamate) -> list:
    return [c for c in chiamate if c[0] == "lock" or "lock." in str(c[2].get("entity_id", ""))]


async def _dillo(testo: str, attore: str = "alessio", canale: str = "web"):
    """Una frase di una persona, passando dagli intenti come fa l'agente."""
    _come(attore, canale)
    risposta = await instrada(Richiesta(testo=testo, profilo=_profilo(attore), memoria=ConversationMemory()))
    return risposta.testo if risposta else None


# ---------------------------------------------------- criterio 1: nessun percorso


SCELTE_DEL_MODELLO = [
    ("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"}),
    ("comanda_serratura", {"entity_id": "serratura ingresso", "azione": "sblocca"}),
    ("comanda_serratura", {"entity_id": PORTA, "azione": "apri"}),
    ("comanda_serratura", {"entity_id": PORTA}),
    ("control_device", {"entity_id": PORTA, "action": "turn_off"}),
    ("control_device", {"entity_id": PORTA, "action": "open"}),
    ("control_device", {"entity_id": "serratura ingresso", "action": "turn_on"}),
    ("comanda_allarme", {"azione": "disarma"}),
    ("comanda_allarme", {"azione": "disarma", "codice": "1234"}),
    ("comanda_tapparella", {"entity_id": "cover.garage", "azione": "apri"}),
    ("control_device", {"entity_id": "cover.garage", "action": "open"}),
    ("activate_scene_or_routine", {"entity_id": "script.apri_tutto"}),
]


@pytest.mark.parametrize(("tool", "argomenti"), SCELTE_DEL_MODELLO)
async def test_nessuna_scelta_del_modello_raggiunge_la_serratura_senza_conferma(casa, tool, argomenti):
    _come("alessio")
    with come_modello():
        esito = await execute_tool(tool, dict(argomenti))

    assert esito["success"] is False
    assert esito.get("conferma_richiesta") is True, esito
    assert casa == [], "nessuna chiamata deve essere partita verso Home Assistant"


async def test_l_agente_vero_non_apre_la_porta_quando_il_modello_lo_sceglie(casa, monkeypatch):
    """Il modello sceglie `comanda_serratura sblocca`: l'agente esegue lo strumento, e la porta resta chiusa."""
    agente = ShinraAgent()
    risposte = [
        {
            "success": True,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "comanda_serratura",
                            "arguments": {"entity_id": PORTA, "azione": "sblocca"},
                        }
                    }
                ],
            },
        },
        {"success": True, "message": {"role": "assistant", "content": "Ti chiedo conferma."}},
    ]

    async def chat(messages, tools=None, **_):
        return risposte.pop(0)

    monkeypatch.setattr(agente.ollama, "chat", chat)
    _come("alessio")
    esito = await agente.process_user_input(
        "apri la serratura dell'ingresso",
        user_profile=_profilo("Alessio"),
        session_memory=ConversationMemory(),
    )

    assert _chiamate_alla_serratura(casa) == []
    assert esito["actions"][0]["result"]["conferma_richiesta"] is True


async def test_un_passo_dentro_una_modalita_scelta_dal_modello_non_apre_la_porta(casa):
    """Anche cio' che il varco non vede (un passo scritto da una persona dentro una modalita') si ferma in fondo."""
    from shinra.infra.homeassistant.client import client_home_assistant

    _come("alessio")
    with come_modello():
        esito = await client_home_assistant().call_service("lock", "unlock", {"entity_id": PORTA})
    assert esito["success"] is False and "modello" in esito["error"]
    assert casa == []

    with come_modello():
        esito = await client_home_assistant().call_service(
            "homeassistant", "turn_on", {"entity_id": [PORTA, "light.cucina"]}
        )
    assert esito["success"] is False
    assert casa == []


async def test_le_azioni_sicure_partono_senza_domande(casa):
    _come("alessio")
    with come_modello():
        luce = await execute_tool("control_device", {"entity_id": "light.cucina", "action": "turn_on"})
        chiudi = await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "blocca"})
    assert luce.get("conferma_richiesta") is None
    assert chiudi.get("conferma_richiesta") is None
    assert [c[:2] for c in casa] == [("light", "turn_on"), ("lock", "lock")]


async def test_chiudere_la_porta_e_armare_l_allarme_non_chiedono_conferma(casa):
    _come("alessio")
    with come_modello():
        armato = await execute_tool("comanda_allarme", {"azione": "arma_fuori"})
    assert armato.get("conferma_richiesta") is None
    assert [c[:2] for c in casa] == [("alarm_control_panel", "alarm_arm_away")]


# ----------------------------------------------------------- il si' esegue, una volta


async def test_il_si_di_chi_ha_chiesto_esegue_quell_azione_una_volta(casa):
    _come("alessio")
    with come_modello():
        chiesta = await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})
    assert chiesta["conferma_richiesta"] is True and casa == []

    risposta = await _dillo("sì")
    assert risposta == "Porta d'ingresso aperta."
    assert casa == [("lock", "unlock", {"entity_id": PORTA})]

    # Una conferma si usa una volta: il secondo «si'» non apre di nuovo.
    ancora = await _dillo("sì")
    assert ancora is None or "niente da confermare" in ancora
    assert len(casa) == 1


async def test_un_no_non_esegue_niente(casa):
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    risposta = await _dillo("no")

    assert risposta == "Va bene, non faccio niente."
    assert casa == []
    assert "niente da confermare" in (await _dillo("sì") or "niente da confermare")


async def test_il_si_esegue_proprio_l_azione_chiesta_e_non_un_altra(casa):
    """La conferma ricorda gli argomenti: il modello non puo' cambiarli dopo il si'."""
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_allarme", {"azione": "disarma", "codice": "1234"})
        # Il modello ora chiede altro: la richiesta nuova sostituisce la precedente.
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    await _dillo("sì")

    assert [c[:2] for c in casa] == [("lock", "unlock")], "solo l'ultima azione chiesta"


async def test_una_frase_che_non_e_un_si_secco_non_conferma(casa):
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    await _dillo("sì, ma prima accendi la luce della cucina e dimmi il meteo")

    assert _chiamate_alla_serratura(casa) == []


# --------------------------------------------------- criterio 2: la conferma scade


async def test_una_conferma_scaduta_non_esegue_niente(casa, monkeypatch):
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    adesso = conferme.time.monotonic()
    monkeypatch.setattr(conferme.time, "monotonic", lambda: adesso + conferme.DURATA_S + 1)

    risposta = await _dillo("sì")

    assert casa == [], "la porta non deve essersi aperta"
    assert risposta is None or "niente da confermare" in risposta or "scaduta" in risposta


async def test_la_scadenza_si_scrive_nel_registro_anche_se_nessuno_chiede(casa, monkeypatch):
    monkeypatch.setattr(conferme, "DURATA_S", 0.05)
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})
    await asyncio.sleep(0.2)

    assert registro.voci(azione="conferma.scaduta")
    assert conferme.in_attesa() is None
    assert casa == []


# ----------------------------------------------- criterio 3: non vale per un altro


async def test_la_conferma_di_un_profilo_non_vale_per_un_altro(casa):
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    risposta_di_sam = await _dillo("sì", attore="sam")

    assert casa == [], "il si' di Sam non apre la porta chiesta da Alessio"
    assert risposta_di_sam is None or "niente da confermare" in risposta_di_sam
    # E la richiesta di Alessio e' ancora in piedi: la conferma di Sam non l'ha consumata.
    _come("alessio")
    assert conferme.in_attesa() is not None


async def test_la_conferma_su_un_canale_non_vale_su_un_altro(casa):
    _come("alessio", "web")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    await _dillo("sì", attore="alessio", canale="alexa")

    assert casa == []


# -------------------------------------------- canali senza identita' o senza interlocutore


async def test_da_una_voce_sconosciuta_l_azione_sensibile_non_parte_e_lo_dice(casa):
    _come(None, "alexa", ignota=True)
    with come_modello():
        esito = await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    assert esito["success"] is False and esito.get("rifiutata") is True
    assert "non so chi sta parlando" in esito["error"]
    assert casa == []
    assert conferme.in_attesa() is None
    assert registro.voci(azione="conferma.senza_identita")


async def test_senza_un_canale_a_cui_chiedere_non_parte(casa):
    """Lo scheduler, una chiamata senza interlocutore: nessuno puo' dire di si'."""
    _come("alessio", "")
    esito = await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    assert esito["success"] is False and esito.get("rifiutata") is True
    assert casa == []


async def test_con_l_autenticazione_spenta_la_conferma_funziona_per_chi_c_e(casa):
    """In casa, senza profili: nessun attore, ma qualcuno c'e' (e' un canale web)."""
    _come(None, "web")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})
    risposta = await instrada(Richiesta(testo="sì", profilo=None, memoria=ConversationMemory()))

    assert risposta is not None and casa == [("lock", "unlock", {"entity_id": PORTA})]


async def test_una_persona_che_chiede_a_parole_incontra_la_stessa_conferma(casa):
    """Non solo il modello: anche una frase che un intento capisce da sola passa dal varco."""
    risposta = await _dillo("spegni la serratura ingresso")

    assert risposta is not None and "Confermi" in risposta
    assert casa == []
    assert await _dillo("sì")
    assert len(casa) == 1


# ----------------------------------------------------------------- il registro


async def test_richiesta_conferma_rifiuto_e_scadenza_finiscono_nel_registro(casa):
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_allarme", {"azione": "disarma", "codice": "1234"})
    await _dillo("no")
    _come("alessio")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})
    await _dillo("sì")

    azioni = {v["azione"] for v in registro.voci(limite=200) if v["azione"].startswith("conferma.")}
    assert {"conferma.richiesta", "conferma.rifiutata", "conferma.accettata"} <= azioni

    # Il codice dell'allarme non finisce mai nel registro.
    assert "1234" not in str(registro.voci(limite=200))


async def test_vietata_agli_agenti_non_parte_nemmeno_confermata(casa, monkeypatch):
    monkeypatch.setitem(TOOL_HANDLERS, "cambia_pin", lambda **_: {"success": True})
    _come("alessio")
    with come_modello():
        esito = await execute_tool("cambia_pin", {"pin": "0000"})

    assert esito["success"] is False and esito.get("rifiutata") is True
    assert registro.voci(azione="conferma.vietata")
    assert conferme.in_attesa() is None


# ------------------------------------------------------------ i guardiani


def test_ogni_strumento_del_registro_e_classificato():
    """Uno strumento nuovo deve dire cos'e': altrimenti e' sensibile, e scomodo."""
    noti = sensibilita.TOOL_SICURI | sensibilita.TOOL_CONDIZIONATI
    sconosciuti = sorted(set(TOOL_HANDLERS) - noti)
    assert not sconosciuti, (
        f"Strumenti non classificati: {sconosciuti}. Aggiungili a TOOL_SICURI o a TOOL_CONDIZIONATI in "
        "domain/sensibilita.py, dopo aver deciso se un modello puo' sceglierli da solo."
    )


def test_nessuno_strumento_vietato_agli_agenti_e_registrato():
    presenti = sorted(set(TOOL_HANDLERS) & sensibilita.TOOL_VIETATI_AGLI_AGENTI)
    assert not presenti, f"Il modello non deve poter scegliere: {presenti}"
    schemi = {s["function"]["name"] for s in registry.TOOLS_SCHEMA}
    assert not schemi & sensibilita.TOOL_VIETATI_AGLI_AGENTI


def test_solo_le_conferme_possono_saltare_il_varco():
    """`_confermata=True` e' la chiave che apre il varco: la usa un posto solo."""
    radice = Path(__file__).resolve().parents[2] / "src" / "shinra"
    usi = []
    for percorso in radice.rglob("*.py"):
        albero = ast.parse(percorso.read_text(encoding="utf-8"))
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.keyword) and nodo.arg == "_confermata":
                usi.append(percorso.relative_to(radice).as_posix())
    assert usi == ["services/conferme.py"], usi


async def test_anche_chiamando_direttamente_il_si_di_un_altro_profilo_non_esegue(casa):
    """Il controllo non sta solo nell'intento: `rispondi` stesso riconosce chi risponde."""
    _come("alessio", "web")
    with come_modello():
        await execute_tool("comanda_serratura", {"entity_id": PORTA, "azione": "sblocca"})

    _come("sam", "web")
    assert (await conferme.rispondi(True))["esito"] == "nessuna"
    _come("alessio", "alexa")
    assert (await conferme.rispondi(True))["esito"] == "nessuna"
    _come(None, "web", ignota=True)
    assert (await conferme.rispondi(True))["esito"] == "nessuna"

    assert casa == []
