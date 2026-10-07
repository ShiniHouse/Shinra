"""Gli agenti di dominio e il router (ADR 0008, issue #190).

Il router non usa il modello, quindi si misura qui, senza Ollama: sul corpus del
banco di prova (`banco/corpus.yaml`) si guarda se, per ogni frase che ha uno
strumento atteso, l'agente di quel dominio e' fra quelli scelti. E' la soglia
dell'ADR: un router che sbaglia dominio in piu' del 10% delle frasi cancella il
vantaggio degli agenti.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from shinra.services import agenti
from shinra.services.intenti.lingue import lingue_disponibili, schemi
from shinra.skills.registry import TOOL_HANDLERS, TOOLS_SCHEMA

CORPUS = Path(__file__).resolve().parent.parent.parent / "banco" / "corpus.yaml"


def _dominio_di() -> dict[str, str]:
    return {strumento: a.nome for a in agenti.AGENTI.values() for strumento in a.strumenti}


def _voci() -> list[dict]:
    dati = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
    return dati if isinstance(dati, list) else next(v for v in dati.values() if isinstance(v, list))


def test_ogni_strumento_sta_in_un_solo_agente():
    """Se uno strumento stesse in due agenti, il confine fra i domini non direbbe niente."""
    conteggio: dict[str, int] = {}
    for a in agenti.AGENTI.values():
        for s in a.strumenti:
            conteggio[s] = conteggio.get(s, 0) + 1

    assert {s for s, n in conteggio.items() if n > 1} == set()


def test_gli_agenti_coprono_tutto_il_catalogo_e_niente_di_piu():
    catalogo = {s["function"]["name"] for s in TOOLS_SCHEMA}

    assert set(_dominio_di()) == catalogo
    # Qualche gestore non ha schema (lo chiama solo un intento, mai il modello): non ha un agente.
    assert catalogo <= set(TOOL_HANDLERS)


@pytest.mark.parametrize("lingua", lingue_disponibili())
def test_ogni_lingua_dice_le_parole_di_ogni_agente(lingua):
    dichiarati = set(schemi(lingua).domini_agente)

    assert dichiarati == set(agenti.AGENTI), f"{lingua}: i domini non coincidono con gli agenti"
    assert all(schemi(lingua).domini_agente[n] for n in dichiarati), f"{lingua}: un dominio senza parole"


def test_un_agente_non_puo_chiamare_uno_strumento_fuori_dal_suo_dominio():
    """Il criterio della scheda: il confine sta nell'esecuzione, non nel prompt."""
    assert agenti.consente(["clima_e_tapparelle"], "comanda_clima") is True
    assert agenti.consente(["clima_e_tapparelle"], "comanda_serratura") is False
    assert agenti.consente(["energia"], "control_device") is False
    assert agenti.consente(["casa", "energia"], "fascia_corrente") is True, "con due agenti valgono i due"


def test_senza_agenti_non_parte_niente():
    """Il router non ha riconosciuto un dominio: il modello non ha ricevuto strumenti, e se ne nomina uno lo inventa."""
    assert agenti.consente([], "comanda_serratura") is False
    assert agenti.consente([], "get_home_status") is False


def test_il_modello_vede_solo_gli_schemi_degli_agenti_scelti():
    visti = {s["function"]["name"] for s in agenti.schemi_di(["energia"])}

    assert visti == {"fascia_corrente", "consumo_energia", "costo_dispositivo"}


@pytest.mark.parametrize(
    "frase, atteso",
    [
        ("quanto ho consumato oggi", "energia"),
        ("chiudi la tapparella del salotto", "clima_e_tapparelle"),
        ("chiudi la porta di ingresso a chiave", "dispositivi"),
        ("ci sono finestre aperte", "sicurezza"),
        ("che tempo fa a Bologna domani", "informazioni"),
        ("aggiungi il latte alla lista della spesa", "agenda"),
        ("accendi la luce della cucina", "casa"),
    ],
)
def test_il_router_riconosce_il_dominio(frase, atteso):
    assert atteso in agenti.scegli(frase, schemi("it"))


def test_senza_parole_riconosciute_il_router_non_sceglie():
    assert agenti.scegli("raccontami una barzelletta", schemi("it")) == []


def test_non_si_scelgono_piu_di_due_agenti():
    scelti = agenti.scegli("accendi la luce, chiudi la tapparella, dimmi il meteo e il consumo", schemi("it"))

    assert len(scelti) <= agenti.MASSIMO_AGENTI


def test_il_router_sceglie_il_dominio_giusto_in_almeno_il_90_per_cento_delle_frasi_del_banco():
    """La soglia dell'ADR 0008: il router deterministico, misurato sulle frasi del banco di prova."""
    dominio = _dominio_di()
    lingua = schemi("it")
    con_strumento = [v for v in _voci() if v.get("attesi")]
    sbagliate = []
    for voce in con_strumento:
        servono = {dominio[a["tool"]] for a in voce["attesi"]}
        if not servono <= set(agenti.scegli(voce["frase"], lingua)):
            sbagliate.append(voce["frase"])

    giuste = len(con_strumento) - len(sbagliate)
    assert con_strumento, "il corpus non ha frasi con uno strumento atteso"
    assert giuste / len(con_strumento) >= 0.9, f"{giuste}/{len(con_strumento)}; sbagliate: {sbagliate}"


# ------------------------------------------------------------ l'agente vero, con un modello finto


class _Modello:
    """Un modello finto: risponde a comando con le chiamate date, poi con una frase."""

    def __init__(self, chiamate, risposta="Fatto."):
        self.chiamate = chiamate
        self.risposta = risposta
        self.strumenti_visti: list = []

    async def chat(self, messages, tools=None, **_):
        self.strumenti_visti.append(tools)
        if len(self.strumenti_visti) == 1 and self.chiamate:
            return {
                "success": True,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": n, "arguments": a}} for n, a in self.chiamate],
                },
            }
        return {"success": True, "message": {"role": "assistant", "content": self.risposta}}


async def _chiedi(monkeypatch, frase, chiamate, risposta="Fatto.", esito=None):
    from shinra.services import agent as modulo
    from shinra.services.memory import ConversationMemory
    from shinra.services.user_manager import UserProfile

    eseguiti: list[str] = []

    async def execute_tool(nome, argomenti):
        eseguiti.append(nome)
        return esito if esito is not None else {"success": True}

    modello = _Modello(chiamate, risposta)
    a = modulo.ShinraAgent()
    monkeypatch.setattr(a.ollama, "chat", modello.chat)
    monkeypatch.setattr(modulo, "execute_tool", execute_tool)
    esito = await a.process_user_input(
        frase, user_profile=UserProfile(id="a", name="Alessio"), session_memory=ConversationMemory()
    )
    return esito, modello, eseguiti


async def test_il_modello_vede_solo_gli_strumenti_dell_agente_scelto(monkeypatch):
    esito, modello, _ = await _chiedi(monkeypatch, "alza la tapparella del salotto", [])

    visti = {s["function"]["name"] for s in modello.strumenti_visti[0]}
    assert visti == agenti.AGENTI["clima_e_tapparelle"].strumenti
    assert esito["agenti"] == ["clima_e_tapparelle"]


async def test_uno_strumento_fuori_dominio_non_parte_anche_se_il_modello_lo_chiede(monkeypatch):
    """Il modello nomina una serratura mentre lavora l'agente delle tapparelle."""
    esito, _, eseguiti = await _chiedi(
        monkeypatch,
        "alza la tapparella del salotto",
        [("comanda_serratura", {"entity_id": "lock.ingresso", "azione": "sblocca"})],
    )

    assert eseguiti == [], "la serratura non deve essere stata eseguita"
    rifiutata = esito["actions"][0]
    assert rifiutata["tool"] == "comanda_serratura" and rifiutata["result"]["success"] is False
    assert esito["success"] is True, "la risposta arriva lo stesso"


async def test_uno_strumento_del_proprio_dominio_parte(monkeypatch):
    _, _, eseguiti = await _chiedi(
        monkeypatch,
        "alza la tapparella del salotto",
        [("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "alza"})],
    )

    assert eseguiti == ["comanda_tapparella"]


async def test_se_il_router_non_riconosce_niente_il_modello_non_riceve_strumenti(monkeypatch):
    """Il ripiego non e' il catalogo intero (~5.460 token, non ci sta nel contesto): e' rispondere a parole."""
    esito, modello, _ = await _chiedi(monkeypatch, "apri", [])

    assert not modello.strumenti_visti[0], "nessuno strumento al modello"
    assert esito["agenti"] == []


async def test_senza_dominio_uno_strumento_nominato_lo_stesso_non_parte(monkeypatch):
    """«apri» senza dire cosa: se il modello chiama una tapparella a caso, non si esegue."""
    _, _, eseguiti = await _chiedi(
        monkeypatch, "apri", [("comanda_tapparella", {"entity_id": "", "azione": "apri"})]
    )

    assert eseguiti == []


# --------------------------------------- cosa si dice a chi ha chiesto, dopo uno strumento fallito (#195)


async def test_se_lo_strumento_fallisce_si_dice_cio_che_ha_detto_lo_strumento_non_il_modello(monkeypatch):
    """Provando in casa: `add_reminder` diceva «non ho capito quando» e il modello rispondeva `success: true`."""
    errore = "Non ho capito quando ricordarti di spegnere le luci. Dimmi un orario."
    esito, _, _ = await _chiedi(
        monkeypatch,
        "alza la tapparella del salotto",
        [("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "alza"})],
        risposta='{"success": true, "message": "Fatto, tapparella alzata."}',
        esito={"success": False, "error": errore},
    )

    assert esito["response"] == errore
    assert "Fatto" not in esito["response"]


async def test_il_json_grezzo_del_modello_non_arriva_a_chi_parla(monkeypatch):
    esito, _, _ = await _chiedi(
        monkeypatch,
        "alza la tapparella del salotto",
        [("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "alza"})],
        risposta='{"success": true, "message": "Tapparella alzata."}',
    )

    assert esito["response"] == "Tapparella alzata."


async def test_un_json_senza_parole_diventa_una_frase_e_non_un_oggetto(monkeypatch):
    esito, _, _ = await _chiedi(monkeypatch, "alza la tapparella del salotto", [], risposta='{"ok": 1}')

    assert not esito["response"].startswith("{")


async def test_una_risposta_normale_resta_com_e(monkeypatch):
    esito, _, _ = await _chiedi(
        monkeypatch,
        "alza la tapparella del salotto",
        [("comanda_tapparella", {"entity_id": "cover.salotto", "azione": "alza"})],
        risposta="Fatto, la tapparella e' alzata.",
    )

    assert esito["response"] == "Fatto, la tapparella e' alzata."
