"""Il prompt di sistema non cambia fra una richiesta e l'altra, cosi' Ollama riusa quello che ha gia' letto.

Il banco di prova (#183) ha misurato che la stessa richiesta ripetuta costa 3-10 secondi invece di 130: il
prefisso del prompt e' in cache. Ma la cache vale solo fino al primo byte diverso, e il prompt cominciava con
«Oggi e' mercoledi 30 settembre, ore 21:40»: in produzione cambiava ogni minuto, e il banco (che costruiva il
prompt una volta sola) non se ne accorgeva. Qui si prova che le cose che cambiano non stanno piu' nel prompt.

Riferimento: ADR 0008, issue #190.
"""

from __future__ import annotations

from datetime import datetime

from shinra.config.prompt_templates import get_contesto_della_richiesta, get_system_prompt
from shinra.infra.lingue import schemi
from shinra.services import agent as modulo_agente
from shinra.services.agent import ShinraAgent
from shinra.services.memory import ConversationMemory
from shinra.services.user_manager import UserProfile


def test_il_prompt_di_sistema_non_dipende_dall_ora(monkeypatch):
    """Due momenti diversi, stesso prompt: il prefisso resta quello."""
    import shinra.config.prompt_templates as modulo

    class _Ora:
        valore = datetime(2026, 9, 30, 21, 40)

        @classmethod
        def now(cls):
            return cls.valore

    monkeypatch.setattr(modulo.datetime, "datetime", _Ora)
    primo = get_system_prompt(lingua=schemi("it"), default_city="Bologna")
    _Ora.valore = datetime(2026, 10, 1, 7, 5)
    secondo = get_system_prompt(lingua=schemi("it"), default_city="Bologna")

    assert primo == secondo
    assert "2026" not in primo and "Oggi" not in primo


def test_il_contesto_della_richiesta_porta_l_ora_la_conoscenza_e_i_dispositivi():
    testo = get_contesto_della_richiesta(
        lingua=schemi("it"),
        home_context_summary="luce cucina: accesa",
        custom_knowledge="la chiave di scorta e' sotto il vaso",
        adesso=datetime(2026, 9, 30, 21, 40),
    )

    assert "mercoledì 30 settembre 2026, ore 21:40" in testo
    assert "luce cucina: accesa" in testo and "sotto il vaso" in testo


def test_il_contesto_in_inglese_e_in_inglese():
    testo = get_contesto_della_richiesta(lingua=schemi("en"), adesso=datetime(2026, 9, 30, 21, 40))

    assert testo.startswith("Today is Wednesday")


async def test_l_agente_manda_lo_stesso_prompt_e_mette_il_contesto_davanti_alla_frase(monkeypatch):
    visti: list = []

    async def chat(messages, tools=None, **_):
        visti.append([dict(m) for m in messages])
        return {"success": True, "message": {"role": "assistant", "content": "Fatto."}}

    async def riepilogo():
        return "luce cucina: accesa"

    agente = ShinraAgent()
    monkeypatch.setattr(agente.ollama, "chat", chat)
    monkeypatch.setattr(agente.ha, "get_relevant_entities_summary", riepilogo)
    monkeypatch.setattr(modulo_agente.settings.home_assistant, "enabled", True)
    memoria = ConversationMemory()
    profilo = UserProfile(id="a", name="Alessio")

    await agente.process_user_input("dimmi una cosa strana", user_profile=profilo, session_memory=memoria)
    await agente.process_user_input("e un'altra cosa strana", user_profile=profilo, session_memory=memoria)

    assert visti[0][0] == visti[1][0], "il prompt di sistema deve essere identico fra due richieste"
    assert "luce cucina: accesa" not in visti[0][0]["content"]
    ultimo = visti[0][-1]["content"]
    assert ultimo.endswith("dimmi una cosa strana") and "luce cucina: accesa" in ultimo and "Oggi è" in ultimo
    # La storia non si porta dietro il contesto di ieri: in memoria resta la frase pulita.
    primo_utente = next(m["content"] for m in memoria.get_messages() if m["role"] == "user")
    assert primo_utente == "dimmi una cosa strana"
