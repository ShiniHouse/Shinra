"""#193: un manifesto che dice cosa fa un plugin, e permessi che si rispettano.

Le garanzie sono tre e si provano qui: un plugin non dichiarato non si carica e
non fa piu' di quello che dichiara; uno che si rompe non ferma il resto; e il
registro delle azioni dice quale plugin ha fatto cosa.
"""

import json
import textwrap

import pytest

from shinra import percorsi
from shinra.domain import sensibilita
from shinra.infra.lingue import schemi
from shinra.services import agenti, plugin, registro
from shinra.services.plugin import (
    Contesto,
    ManifestoNonValido,
    PermessoPluginNegato,
    carica_plugin,
    leggi_manifesto,
)
from shinra.skills.registry import TOOL_HANDLERS, execute_tool


@pytest.fixture(autouse=True)
def senza_plugin():
    """Nessun plugin resta caricato da un test all'altro."""
    plugin.disattiva()
    yield
    plugin.disattiva()


def _manifesto(**campi) -> dict:
    base = {
        "nome": "demo",
        "versione": "1.0.0",
        "descrizione": "Un plugin di prova",
        "strumenti": ["demo_saluta"],
        "parole": ["salutami"],
        "permessi": {},
    }
    base.update(campi)
    return base


def _scrivi(cartella, manifesto: dict, codice: str | None = None):
    """Un plugin in una cartella temporanea, con il modulo che si vuole."""
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "plugin.json").write_text(json.dumps(manifesto), encoding="utf-8")
    if codice is None:
        codice = """
        SCHEMI = [{"type": "function", "function": {"name": "demo_saluta", "description": "Saluta", "parameters": {"type": "object", "properties": {}}}}]

        def saluta(contesto):
            return {"success": True, "messaggio": "Ciao"}

        GESTORI = {"demo_saluta": saluta}
        """
    (cartella / "plugin.py").write_text(textwrap.dedent(codice), encoding="utf-8")
    return cartella


# ------------------------------------------------------------- il manifesto


def test_un_manifesto_valido_si_legge() -> None:
    m = leggi_manifesto(_manifesto(permessi={"domini_ha": ["light"], "rete": ["api.meteo.it"]}))
    assert m.nome == "demo"
    assert m.permessi.domini_ha == {"light"}
    assert m.permessi.rete == {"api.meteo.it"}
    assert "light" in m.permessi.descrivi()


def test_senza_permessi_lo_dice_in_chiaro() -> None:
    assert "nessun permesso" in leggi_manifesto(_manifesto()).permessi.descrivi()


@pytest.mark.parametrize(
    "difetto, frase",
    [
        ({"nome": "Demo Plugin"}, "il nome deve essere"),
        ({"versione": ""}, "manca «versione»"),
        ({"strumenti": []}, "«strumenti» deve essere"),
        ({"strumenti": ["saluta"]}, "deve chiamarsi «demo_"),
        ({"strumenti": ["demo_a", "demo_a"]}, "stesso nome"),
        ({"inventato": 1}, "campi sconosciuti"),
        ({"permessi": {"root": True}}, "permessi sconosciuti"),
        ({"permessi": {"rete": ["http://x.it/api"]}}, "host semplici"),
        ({"origine": "terzi"}, "solo i plugin del proprietario"),
    ],
)
def test_un_manifesto_sbagliato_dice_cosa_non_va(difetto, frase) -> None:
    with pytest.raises(ManifestoNonValido) as errore:
        leggi_manifesto(_manifesto(**difetto))
    assert any(frase in p for p in errore.value.problemi), errore.value.problemi


@pytest.mark.parametrize("dominio", ["lock", "alarm_control_panel", "script"])
def test_un_plugin_non_puo_nemmeno_chiedere_le_cose_delicate(dominio) -> None:
    with pytest.raises(ManifestoNonValido) as errore:
        leggi_manifesto(_manifesto(permessi={"domini_ha": ["light", dominio]}))
    assert any(dominio in p and "delicate" in p for p in errore.value.problemi)


def test_il_manifesto_dice_tutti_i_problemi_insieme() -> None:
    with pytest.raises(ManifestoNonValido) as errore:
        leggi_manifesto(_manifesto(versione="", descrizione="", strumenti=[]))
    assert len(errore.value.problemi) >= 3


# ------------------------------------------------------------ il caricamento


@pytest.mark.parametrize(
    "frase",
    [
        "Tira il dado",  # detto a voce in casa, il 2026-10-13: con le frasi intere nel manifesto non combaciava
        "tira un dado per favore",
        "lancia il dado a 20 facce",
        "tira i dadi",
        "fammi tirare un dado",
        "TIRA IL DADO",
    ],
)
def test_il_dado_si_riconosce_comunque_lo_si_dica(frase) -> None:
    plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])
    assert agenti.scegli(frase, schemi("it")) == ["plugin_esempio_dado"], frase


@pytest.mark.parametrize("frase", ["accendi la luce del salotto", "che tempo fa domani", "che ore sono"])
def test_il_dado_non_ruba_le_richieste_degli_altri(frase) -> None:
    plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])
    assert "plugin_esempio_dado" not in agenti.scegli(frase, schemi("it")), frase


def test_il_plugin_di_esempio_si_carica_e_un_agente_lo_sceglie() -> None:
    caricati, errori = plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])

    assert caricati == ["esempio_dado"] and errori == {}
    assert "esempio_dado_tira" in TOOL_HANDLERS
    assert agenti.scegli("tira un dado per favore", schemi("it")) == ["plugin_esempio_dado"]
    assert agenti.consente(["plugin_esempio_dado"], "esempio_dado_tira")
    assert not agenti.consente(
        ["plugin_esempio_dado"], "control_device"
    ), "il plugin ha preso strumenti non suoi"


@pytest.mark.asyncio
async def test_il_plugin_di_esempio_si_esegue_e_il_registro_dice_quale() -> None:
    plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])

    esito = await execute_tool("esempio_dado_tira", {"facce": 6})

    assert esito["success"] is True and "E' uscito" in esito["messaggio"]
    voce = registro.voci(azione="tool.esempio_dado_tira")[0]
    assert voce["dettagli"]["plugin"] == "esempio_dado"


def test_un_plugin_non_abilitato_non_si_importa(tmp_path) -> None:
    cartella = _scrivi(tmp_path / "demo", _manifesto(), "raise RuntimeError('importato')\n")
    assert cartella.exists()

    caricati, errori = plugin.attiva(tmp_path, [])

    assert caricati == [] and errori == {}, "ha importato un plugin che nessuno ha abilitato"


def test_un_plugin_rotto_non_ferma_gli_altri(tmp_path) -> None:
    _scrivi(tmp_path / "demo", _manifesto())
    _scrivi(
        tmp_path / "rotto", _manifesto(nome="rotto", strumenti=["rotto_x"]), "raise RuntimeError('boom')\n"
    )

    caricati, errori = plugin.attiva(tmp_path, ["rotto", "demo"])

    assert caricati == ["demo"]
    assert "boom" in errori["rotto"][0]
    assert "demo_saluta" in TOOL_HANDLERS


def test_gli_strumenti_del_modulo_devono_essere_quelli_del_manifesto(tmp_path) -> None:
    codice = """
    SCHEMI = [{"type": "function", "function": {"name": "demo_altro", "description": "x", "parameters": {}}}]
    GESTORI = {"demo_altro": lambda c: {}}
    """
    _scrivi(tmp_path / "demo", _manifesto(), codice)
    with pytest.raises(ManifestoNonValido) as errore:
        carica_plugin(tmp_path / "demo")
    assert "non sono quelli del manifesto" in errore.value.problemi[0]


def test_il_nome_deve_essere_quello_della_cartella(tmp_path) -> None:
    _scrivi(tmp_path / "altra", _manifesto())
    with pytest.raises(ManifestoNonValido, match="non e' quello della cartella"):
        carica_plugin(tmp_path / "altra")


def test_uno_strumento_che_esiste_gia_non_si_sovrascrive(tmp_path) -> None:
    manifesto = _manifesto(strumenti=["demo_saluta"])
    TOOL_HANDLERS["demo_saluta"] = lambda: {"success": True, "messaggio": "originale"}
    try:
        _scrivi(tmp_path / "demo", manifesto)
        caricati, errori = plugin.attiva(tmp_path, ["demo"])
        assert caricati == [] and "gia' esistenti" in errori["demo"][0]
        assert TOOL_HANDLERS["demo_saluta"]()["messaggio"] == "originale"
    finally:
        TOOL_HANDLERS.pop("demo_saluta", None)


def test_disattivare_toglie_tutto(tmp_path) -> None:
    _scrivi(tmp_path / "demo", _manifesto())
    plugin.attiva(tmp_path, ["demo"])
    assert "plugin_demo" in agenti.AGENTI

    plugin.disattiva()

    assert "demo_saluta" not in TOOL_HANDLERS
    assert "plugin_demo" not in agenti.AGENTI
    assert "demo_saluta" not in sensibilita.TOOL_SICURI_DINAMICI


# ------------------------------------------------------ gli errori a lavoro


@pytest.mark.asyncio
async def test_un_plugin_che_si_rompe_lavorando_da_un_errore_leggibile(tmp_path) -> None:
    codice = """
    SCHEMI = [{"type": "function", "function": {"name": "demo_saluta", "description": "x", "parameters": {"type": "object", "properties": {}}}}]

    def saluta(contesto):
        raise ValueError("il servizio meteo non risponde")

    GESTORI = {"demo_saluta": saluta}
    """
    _scrivi(tmp_path / "demo", _manifesto(), codice)
    plugin.attiva(tmp_path, ["demo"])

    esito = await execute_tool("demo_saluta", {})

    assert esito["success"] is False
    assert "il servizio meteo non risponde" in esito["error"]
    assert registro.voci(azione="tool.demo_saluta")[0]["esito"] == registro.ESITO_ERRORE
    # E il resto del servizio e' al suo posto.
    assert "get_weather" in TOOL_HANDLERS


# --------------------------------------------------------------- i permessi


def _contesto(**permessi) -> Contesto:
    return Contesto(leggi_manifesto(_manifesto(permessi=permessi)))


@pytest.mark.asyncio
async def test_un_plugin_non_comanda_un_dominio_che_non_ha_dichiarato() -> None:
    contesto = _contesto(domini_ha=["light"])
    with pytest.raises(PermessoPluginNegato, match="cover"):
        await contesto.comanda("cover.salotto", "close_cover")


@pytest.mark.asyncio
async def test_senza_permessi_non_comanda_niente() -> None:
    with pytest.raises(PermessoPluginNegato):
        await _contesto().comanda("light.cucina", "turn_on")


@pytest.mark.asyncio
async def test_un_dominio_dichiarato_si_comanda_dal_motore(monkeypatch) -> None:
    visti = []

    async def comanda(azione):
        visti.append(azione)
        return {"riuscita": True, "entity_id": azione["entity_id"]}

    monkeypatch.setattr("shinra.skills.ha_tools.comanda_dal_motore", comanda)

    esito = await _contesto(domini_ha=["light"]).comanda("light.cucina", "turn_on", {"brightness_pct": 40})

    assert esito["riuscita"] is True
    assert visti == [{"entity_id": "light.cucina", "servizio": "turn_on", "dati": {"brightness_pct": 40}}]


@pytest.mark.asyncio
async def test_un_garage_non_si_comanda_nemmeno_dichiarando_cover() -> None:
    contesto = _contesto(domini_ha=["cover"])
    with pytest.raises(PermessoPluginNegato, match="delicata"):
        await contesto.comanda("cover.garage", "open_cover")


@pytest.mark.asyncio
async def test_la_rete_solo_verso_gli_host_dichiarati() -> None:
    contesto = _contesto(rete=["api.esempio.it"])
    with pytest.raises(PermessoPluginNegato, match=r"altrove\.example"):
        await contesto.leggi("https://altrove.example/dati")


def test_la_conoscenza_solo_se_dichiarata() -> None:
    with pytest.raises(PermessoPluginNegato, match="conoscenza"):
        _contesto().conoscenza()


# ------------------------------------------------- cosa chiede conferma


def test_un_plugin_senza_permessi_sulla_casa_e_sicuro(tmp_path) -> None:
    _scrivi(tmp_path / "demo", _manifesto())
    plugin.attiva(tmp_path, ["demo"])
    assert sensibilita.classifica("demo_saluta") == sensibilita.SICURA


def test_un_plugin_che_comanda_dispositivi_chiede_conferma(tmp_path) -> None:
    _scrivi(tmp_path / "demo", _manifesto(permessi={"domini_ha": ["light"]}))
    plugin.attiva(tmp_path, ["demo"])
    assert sensibilita.classifica("demo_saluta") == sensibilita.SENSIBILE


def test_uno_strumento_di_plugin_scaricato_torna_sensibile(tmp_path) -> None:
    _scrivi(tmp_path / "demo", _manifesto())
    plugin.attiva(tmp_path, ["demo"])
    plugin.disattiva()
    assert sensibilita.classifica("demo_saluta") == sensibilita.SENSIBILE


# ------------------------------------- dal messaggio alla riga di registro, per il percorso vero dell'agente
#
# Il router da solo (`agenti.scegli`) e' la parte facile. In casa, il 2026-10-13, «Tira un dado» non e' arrivato a
# nessun agente: l'agente da' gli strumenti al modello solo se la frase contiene una «parola d'azione» del catalogo, e
# «tira un dado» non ne ha. Il plugin era caricato, il router lo sceglieva, e il modello inventava il numero. I test
# sopra non lo vedevano perche' non passavano dall'agente.


@pytest.fixture
def agente_con_dado(monkeypatch):
    """L'agente vero con il modello finto: registra cosa gli arriva e chiama lo strumento che gli si dice."""
    from shinra.services.agent import ShinraAgent

    plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])
    arrivi: list = []
    risposte = [
        {
            "success": True,
            "message": {
                "content": "",
                "tool_calls": [{"function": {"name": "esempio_dado_tira", "arguments": {"facce": 6}}}],
            },
        },
        {"success": True, "message": {"content": "Ecco il tuo dado.", "tool_calls": []}},
    ]

    async def chat(self, messages, tools=None, **k):
        arrivi.append({"tools": [t["function"]["name"] for t in tools] if tools else None})
        return risposte[min(len(arrivi) - 1, len(risposte) - 1)]

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    yield ShinraAgent(), arrivi


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frase", ["Tira un dado", "Tira il dado", "lancia il dado a 20 facce", "tira i dadi"]
)
async def test_il_modello_riceve_lo_strumento_del_dado_e_il_registro_lo_dice(agente_con_dado, frase) -> None:
    agente, arrivi = agente_con_dado

    esito = await agente.process_user_input(frase)

    assert arrivi[0]["tools"] == ["esempio_dado_tira"], "lo strumento non e' arrivato al modello"
    assert [a["tool"] for a in esito["actions"]] == ["esempio_dado_tira"]
    assert "E' uscito" in esito["actions"][0]["result"]["messaggio"], "il numero non l'ha tirato il plugin"
    voce = registro.voci(azione="tool.esempio_dado_tira")[0]
    assert voce["dettagli"]["plugin"] == "esempio_dado", "il registro non dice quale plugin ha tirato"


@pytest.mark.asyncio
async def test_una_chiacchiera_non_da_strumenti_al_modello(agente_con_dado) -> None:
    agente, arrivi = agente_con_dado
    await agente.process_user_input("ciao come stai oggi")
    assert arrivi[0]["tools"] is None


# ------------------------- il modello non chiama lo strumento: si riprova una volta, senza la storia
#
# Provato il 2026-10-13 sul modello vero (qwen2.5:3b, Ollama del server): con la storia pulita il dado si chiama 3 volte su 3;
# con una sola risposta inventata fra i messaggi precedenti, 0 su 3, e il modello imita quella risposta.


@pytest.fixture
def agente_che_inventa(monkeypatch):
    """Il modello finto: con la storia risponde a parole (inventando); con la sola richiesta chiama lo strumento."""
    from shinra.services.agent import ShinraAgent

    plugin.attiva(percorsi.PLUGIN, ["esempio_dado"])
    arrivi: list = []
    impostazioni = {"riprova_chiama": True}

    async def chat(self, messages, tools=None, temperature=None, **k):
        arrivi.append(
            {
                "n": len(messages),
                "tools": [t["function"]["name"] for t in tools] if tools else None,
                "t": temperature,
                "utente": messages[-1]["content"],
            }
        )
        if tools and len(messages) > 2:
            return {"success": True, "message": {"content": "Il dado giallo e' venuto 5.", "tool_calls": []}}
        if tools:
            chiama = (
                [{"function": {"name": "esempio_dado_tira", "arguments": {"facce": 6}}}]
                if impostazioni["riprova_chiama"]
                else []
            )
            return {
                "success": True,
                "message": {"content": "" if chiama else "Non so.", "tool_calls": chiama},
            }
        return {"success": True, "message": {"content": "Ecco il tuo dado.", "tool_calls": []}}

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    yield ShinraAgent(), arrivi, impostazioni


def _storia_avvelenata():
    """Una conversazione in cui il modello ha gia' inventato un numero senza tirare il dado."""
    from shinra.services.memory import ConversationMemory

    memoria = ConversationMemory()
    memoria.add_user_message("Tira un dado")
    memoria.add_assistant_message("Il dado giallo e' venuto 3.")
    return memoria


@pytest.mark.asyncio
async def test_se_il_modello_non_chiama_lo_strumento_si_riprova_senza_storia(agente_che_inventa) -> None:
    agente, arrivi, _ = agente_che_inventa

    esito = await agente.process_user_input("Tira un dado", session_memory=_storia_avvelenata())

    primo, riprova = arrivi[0], arrivi[1]
    assert primo["tools"] == ["esempio_dado_tira"] and primo["n"] > 2
    assert riprova["n"] == 2, "la riprova doveva avere solo il sistema e la richiesta"
    assert riprova["tools"] == ["esempio_dado_tira"] and riprova["t"] == 0.1
    assert riprova["utente"] == "Tira un dado", "la riprova ha portato dietro il contesto"
    assert [a["tool"] for a in esito["actions"]] == ["esempio_dado_tira"]
    assert "E' uscito" in esito["actions"][0]["result"]["messaggio"], "il numero non l'ha tirato il plugin"
    assert (
        esito["response"] == "Ecco il tuo dado."
    ), "la risposta inventata non doveva arrivare a chi ha chiesto"
    assert registro.voci(azione="tool.esempio_dado_tira")[0]["dettagli"]["plugin"] == "esempio_dado"


@pytest.mark.asyncio
async def test_se_anche_la_riprova_non_chiama_si_tiene_la_prima_risposta(agente_che_inventa) -> None:
    agente, arrivi, impostazioni = agente_che_inventa
    impostazioni["riprova_chiama"] = False

    esito = await agente.process_user_input("Tira un dado", session_memory=_storia_avvelenata())

    assert len(arrivi) == 2, "ha riprovato piu' di una volta"
    assert esito["actions"] == []
    assert esito["response"] == "Il dado giallo e' venuto 5."


@pytest.mark.asyncio
async def test_se_il_modello_chiama_lo_strumento_non_si_riprova(agente_con_dado) -> None:
    agente, arrivi = agente_con_dado
    await agente.process_user_input("Tira un dado")
    assert (
        len(arrivi) == 2
    ), "la prima chiamata porta lo strumento, la seconda legge il risultato: nessuna riprova"


@pytest.mark.asyncio
async def test_senza_un_plugin_non_si_riprova(monkeypatch) -> None:
    from shinra.services.agent import ShinraAgent

    arrivi: list = []

    async def chat(self, messages, tools=None, **k):
        arrivi.append(len(messages))
        return {"success": True, "message": {"content": "Quale?", "tool_calls": []}}

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    await ShinraAgent().process_user_input("regola il termostato")
    assert 2 not in arrivi, "ha riprovato senza storia per una richiesta che non e' di un plugin"
