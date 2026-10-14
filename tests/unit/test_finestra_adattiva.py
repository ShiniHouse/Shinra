"""La storia grezza e' cio' che resta del budget (#257, #244): nessuna richiesta supera il contesto, nell'ordine dichiarato.

Prove deterministiche: il prompt ridotto ci sta davvero (misurato con lo stesso conteggio che lo ha ridotto); si taglia prima la
storia dal messaggio piu' vecchio, poi i ricordi meno pertinenti, mai il sistema, gli strumenti e la domanda; con un contesto
piu' largo la finestra cresce senza toccare il codice; una richiesta con molti strumenti si restringe da sola; e se tagliare
non basterebbe a farlo stare, non si butta la storia (si lascia com'e' e lo si dice).
"""

from __future__ import annotations

import pytest

from shinra.domain import budget
from shinra.services import prompt_nel_budget as p

RISPOSTA = 150


def parole(n: int, c: str = "x") -> str:
    return c * (n * 3)  # 3 caratteri = 1 token nella stima (CARATTERI_PER_TOKEN)


def messaggi(
    storia: int = 20, peso_messaggio: int = 40, sistema: int = 200, domanda: int = 30, ricordi: str = ""
):
    m = [{"role": "system", "content": parole(sistema, "s")}]
    for i in range(storia):
        m.append(
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"{i:02d}" + parole(peso_messaggio, "h"),
            }
        )
    m.append({"role": "user", "content": (ricordi + "\n\n" if ricordi else "") + parole(domanda, "d")})
    return m


def tutto(adattato: p.Adattato, schemi=None):
    """Il peso dei messaggi cosi' come li riceverebbe il modello, con lo stesso conteggio."""
    import json

    m = adattato.messaggi
    return budget.misura(
        4096,
        RISPOSTA,
        sistema=m[0]["content"],
        strumenti=json.dumps(schemi, ensure_ascii=False) if schemi else "",
        ricordi="",
        storia=m[1:-1],
        domanda=m[-1]["content"],
    ).totale


def test_se_ci_sta_non_si_taglia_niente():
    m = messaggi(storia=4)
    a = p.adatta(m, [], "", num_ctx=4096, risposta=RISPOSTA)
    assert a.messaggi == m and not a.taglio.tagliato and not a.taglio.insufficiente


def test_il_prompt_ridotto_ci_sta_davvero_e_si_taglia_dal_piu_vecchio():
    m = messaggi(storia=20)
    a = p.adatta(m, [], "", num_ctx=1024, risposta=RISPOSTA)
    assert a.taglio.storia_tolta > 0 and not a.taglio.insufficiente
    assert not a.misura.sfora, "il prompt ridotto non ci sta ancora"
    assert tutto(a) <= 1024 - RISPOSTA
    rimasti = [x["content"][:2] for x in a.messaggi[1:-1]]
    assert rimasti == [
        f"{i:02d}" for i in range(20 - len(rimasti), 20)
    ], "si e' tagliato dal messaggio sbagliato"


def test_non_si_tocca_mai_il_sistema_ne_la_domanda():
    m = messaggi(storia=20)
    a = p.adatta(m, [], "", num_ctx=1024, risposta=RISPOSTA)
    assert a.messaggi[0] == m[0] and a.messaggi[-1] == m[-1]


@pytest.mark.parametrize("quanti", [17, 18, 19, 20, 21, 22, 23, 24])
def test_la_storia_ridotta_comincia_da_chi_parla(quanti):
    """Con un numero pari o dispari di messaggi da togliere, la storia che resta non parte da una risposta a vuoto."""
    a = p.adatta(messaggi(storia=quanti), [], "", num_ctx=1024, risposta=RISPOSTA)
    assert a.taglio.storia_tolta > 0
    assert a.messaggi[1]["role"] == "user", "la storia tagliata inizia a meta' di uno scambio"


def test_con_un_contesto_piu_largo_la_finestra_cresce_senza_toccare_il_codice():
    m = messaggi(storia=20, peso_messaggio=120)
    strette = p.adatta(m, [], "", num_ctx=1024, risposta=RISPOSTA)
    larghe = p.adatta(m, [], "", num_ctx=2048, risposta=RISPOSTA)
    larghissime = p.adatta(m, [], "", num_ctx=8192, risposta=RISPOSTA)
    assert len(strette.messaggi) < len(larghe.messaggi) < len(larghissime.messaggi) == len(m)


def test_una_richiesta_con_molti_strumenti_ha_meno_storia_di_una_chiacchierata():
    m = messaggi(storia=20)
    pochi = [{"function": {"name": "uno", "description": "x" * 30}}]
    molti = [{"function": {"name": f"s{i}", "description": "x" * 200}} for i in range(8)]
    senza = p.adatta(m, [], "", num_ctx=1536, risposta=RISPOSTA)
    con_pochi = p.adatta(m, pochi, "", num_ctx=1536, risposta=RISPOSTA)
    con_molti = p.adatta(m, molti, "", num_ctx=1536, risposta=RISPOSTA)
    assert len(senza.messaggi) >= len(con_pochi.messaggi) > len(con_molti.messaggi)
    assert not con_molti.misura.sfora and tutto(con_molti, molti) <= 4096 - RISPOSTA


def test_finita_la_storia_si_tolgono_i_ricordi_dall_ultimo_e_nel_messaggio_della_domanda():
    ricordi = "\n".join(f"- ricordo {i} " + parole(120, "r") for i in range(6))
    m = messaggi(storia=4, ricordi=ricordi)
    a = p.adatta(m, [], ricordi, num_ctx=1024, risposta=RISPOSTA)
    assert a.taglio.storia_tolta == 4, "i ricordi non si toccano finche' c'e' storia da tagliare"
    assert 0 < a.taglio.ricordi_tolti < 6 and not a.taglio.insufficiente
    ultimo = a.messaggi[-1]["content"]
    assert "- ricordo 0 " in ultimo, "i piu' pertinenti (i primi) devono restare"
    assert "- ricordo 5 " not in ultimo, "l'ultimo ricordo doveva uscire dal messaggio"
    assert a.conoscenza.count("\n") + 1 == 6 - a.taglio.ricordi_tolti


@pytest.fixture
def righe_di_log(monkeypatch):
    """Cio' che il modulo scrive nel log, senza dipendere da come e' configurato il logging nel resto dei test."""
    scritte: list[str] = []

    class Registro:
        def __getattr__(self, livello):
            return lambda messaggio, *a, **k: scritte.append(str(messaggio) % a if a else str(messaggio))

    monkeypatch.setattr(p, "logger", Registro())
    return scritte


def test_se_tagliare_non_basta_si_lascia_com_e_e_lo_si_dice(righe_di_log):
    """Un prompt che non ci sta nemmeno senza storia: buttare la storia farebbe perdere il filo senza farlo stare."""
    m = messaggi(storia=6, sistema=2000)
    a = p.adatta(m, [], "", num_ctx=1024, risposta=RISPOSTA)
    assert a.messaggi == m, "ha buttato la storia anche se non serviva a farlo stare"
    assert a.taglio.insufficiente
    assert any("nemmeno senza storia" in r for r in righe_di_log), "il caso non lascia traccia"


def test_ogni_taglio_lascia_una_riga_nel_log(righe_di_log):
    p.adatta(messaggi(storia=20), [], "", num_ctx=1024, risposta=RISPOSTA)
    assert any("non ci stava nel contesto" in r and "storia: tolti" in r for r in righe_di_log), righe_di_log


@pytest.mark.parametrize("storia", [0, 1, 2])
def test_senza_storia_o_quasi_non_si_rompe_niente(storia):
    m = messaggi(storia=storia)
    a = p.adatta(m, [], "", num_ctx=4096, risposta=RISPOSTA)
    assert a.messaggi == m


def test_un_solo_messaggio_non_si_rompe():
    m = [{"role": "user", "content": "ciao"}]
    assert p.adatta(m, [], "", num_ctx=1024, risposta=RISPOSTA).messaggi == m


# ------------------------------------------------------------------ nell'agente


async def test_l_agente_manda_al_modello_un_prompt_che_ci_sta(monkeypatch):
    """Con un contesto stretto, dopo una conversazione lunga, il modello riceve meno storia: e la risposta arriva."""
    from shinra.services.agent import ShinraAgent
    from shinra.services.memory import ConversationMemory
    from shinra.services.user_manager import UserProfile

    visti: list[int] = []

    async def chat(self, messages, tools=None, temperature=None, **k):
        visti.append(len(messages))
        return {"success": True, "message": {"content": "Ecco.", "tool_calls": []}}

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    memoria = ConversationMemory(max_history=10)
    for i in range(10):
        memoria.add_user_message(f"richiesta numero {i} " + "parola " * 40)
        memoria.add_assistant_message(f"[azione eseguita: control_device(x={i})]")

    monkeypatch.setattr("shinra.services.agent.contesto_in_uso", lambda: 32768)
    larghe = visti.copy()
    await ShinraAgent().process_user_input(
        "racconta cosa sai di me", user_profile=UserProfile(id="u1", name="U"), session_memory=memoria
    )
    larghe = visti[-1]

    monkeypatch.setattr("shinra.services.agent.contesto_in_uso", lambda: 1400)
    memoria2 = ConversationMemory(max_history=10)
    for i in range(10):
        memoria2.add_user_message(f"richiesta numero {i} " + "parola " * 40)
        memoria2.add_assistant_message(f"[azione eseguita: control_device(x={i})]")
    await ShinraAgent().process_user_input(
        "racconta cosa sai di me", user_profile=UserProfile(id="u1", name="U"), session_memory=memoria2
    )
    strette = visti[-1]

    assert strette < larghe, f"con un contesto stretto la storia doveva ridursi ({strette} contro {larghe})"
