"""L'orchestratore (#432, ADR 0013): spento di serie, un pezzo che fallisce non ferma gli altri, la storia resta una."""

from __future__ import annotations

import pytest

from shinra.config.settings import settings
from shinra.services import orchestratore, registro
from shinra.services.intenti import Risposta


def _non_riuscito(elenco: str) -> str:
    return f"NON: {elenco}"


# ------------------------------------------------------------------ il revisore


def test_il_revisore_si_fida_solo_di_success_false():
    assert orchestratore.rivedi({"success": True, "actions": [{"result": {"success": True}}]})
    assert orchestratore.rivedi({"actions": [{"result": "ok"}, {"result": None}]})
    assert not orchestratore.rivedi({"success": False})
    assert not orchestratore.rivedi({"actions": [{"result": {"success": False}}]})


# ------------------------------------------------------------------ il giro


async def test_un_pezzo_che_fallisce_non_ferma_gli_altri_e_si_dice():
    visti: list[str] = []

    async def pezzo(testo: str):
        visti.append(testo)
        if testo == "b":
            return {"response": "no", "actions": [{"result": {"success": False}}]}
        return {"response": f"fatto {testo}", "actions": [{"tool": "t", "result": {"success": True}}]}

    esito = await orchestratore.orchestra(["a", "b", "c"], pezzo, _non_riuscito, "Fatto.")
    assert visti == ["a", "b", "c"]
    assert esito["success"] is False
    assert (esito["pezzi"], esito["falliti"]) == (3, 1)
    assert "fatto a" in esito["response"] and "fatto c" in esito["response"]
    assert esito["response"].endswith("NON: b")
    assert "no" not in esito["response"].replace("NON", "")


async def test_un_pezzo_che_lancia_un_errore_conta_come_fallito():
    async def pezzo(testo: str):
        if testo == "a":
            raise RuntimeError("boom")
        return {"response": "ok", "actions": []}

    esito = await orchestratore.orchestra(["a", "b"], pezzo, _non_riuscito, "Fatto.")
    assert esito["falliti"] == 1 and esito["response"] == "ok NON: a"


async def test_se_nessuno_dice_niente_e_tutto_riesce_si_dice_fatto():
    async def pezzo(testo: str):
        return {"response": "", "actions": []}

    esito = await orchestratore.orchestra(["a", "b"], pezzo, _non_riuscito, "Fatto.")
    assert esito["response"] == "Fatto." and esito["success"] is True


async def test_oltre_il_tetto_delle_azioni_non_si_esegue_e_si_dice():
    eseguiti: list[str] = []

    async def pezzo(testo: str):
        eseguiti.append(testo)
        return {"response": "ok", "actions": [{"result": {"success": True}}] * orchestratore.MASSIMO_AZIONI}

    esito = await orchestratore.orchestra(["a", "b"], pezzo, _non_riuscito, "Fatto.")
    assert eseguiti == ["a"]
    assert esito["falliti"] == 1 and esito["response"].endswith("NON: b")


async def test_il_registro_porta_i_conti_e_non_il_testo(monkeypatch):
    voci: list[dict] = []
    monkeypatch.setattr(registro, "registra", lambda azione, **kw: voci.append({"azione": azione, **kw}))

    async def pezzo(testo: str):
        return {"response": "ok", "actions": []}

    await orchestratore.orchestra(["spegni la luce segreta", "b"], pezzo, _non_riuscito, "Fatto.")
    assert voci == [
        {
            "azione": "orchestratore.scomposta",
            "esito": registro.ESITO_OK,
            "dettagli": {"pezzi": 2, "falliti": 0},
        }
    ]


# ------------------------------------------------------------------ nell'agente


async def _agente(monkeypatch, acceso: bool, frase: str):
    from shinra.services import agent as modulo
    from shinra.services.memory import ConversationMemory
    from shinra.services.user_manager import UserProfile

    visti: list[str] = []

    async def instrada(richiesta):
        visti.append(richiesta.testo)
        return Risposta(testo=f"ok: {richiesta.testo}")

    monkeypatch.setattr(modulo, "instrada", instrada)
    monkeypatch.setattr(settings.agenti, "orchestratore", acceso)
    memoria = ConversationMemory()
    esito = await modulo.ShinraAgent().process_user_input(
        frase, user_profile=UserProfile(id="a", name="Alessio", lingua="it"), session_memory=memoria
    )
    return esito, visti, memoria


FRASE = "Spegni la luce del salotto e accendi la tv"


async def test_spenta_la_frase_resta_intera(monkeypatch):
    esito, visti, _ = await _agente(monkeypatch, False, FRASE)
    assert visti == [FRASE]
    assert "pezzi" not in esito


async def test_accesa_ogni_pezzo_fa_il_suo_giro_e_la_storia_resta_una(monkeypatch):
    esito, visti, memoria = await _agente(monkeypatch, True, FRASE)
    assert len(visti) == 2 and all(" e " not in v for v in visti)
    assert esito["pezzi"] == 2 and esito["success"] is True
    assert all(v in esito["response"] for v in visti)
    contenuti = [m["content"] for m in memoria.history]
    assert contenuti == [FRASE, esito["response"]]


async def test_accesa_con_una_sola_azione_non_si_spezza(monkeypatch):
    esito, visti, _ = await _agente(monkeypatch, True, "Spegni la luce del salotto")
    assert visti == ["Spegni la luce del salotto"] and "pezzi" not in esito


@pytest.mark.parametrize("acceso", [False])
def test_di_serie_e_spenta(acceso):
    from shinra.config.settings import AgentiConfig

    assert AgentiConfig().orchestratore is acceso
