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
from shinra.services import agenti, plugin, registro
from shinra.services.intenti.lingue import schemi
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
