"""Il budget del contesto (#244): si conta per componente, si taglia nell'ordine dichiarato, niente si taglia senza traccia."""

from __future__ import annotations

from shinra.domain import budget


def messaggio(parole: int, ruolo: str = "user") -> dict:
    return {"role": ruolo, "content": "x" * (parole * 3)}  # 3 caratteri = 1 token (CARATTERI_PER_TOKEN)


def test_la_stima_arrotonda_per_eccesso_e_il_vuoto_pesa_zero() -> None:
    assert budget.stima_token("") == 0
    assert budget.stima_token("ab") == 1
    assert budget.stima_token("a" * 4) == 2


def test_la_misura_conta_ogni_componente() -> None:
    m = budget.misura(
        1024,
        150,
        sistema="s" * 300,
        strumenti="t" * 150,
        ricordi="r" * 30,
        storia=[messaggio(10), messaggio(20)],
        domanda="d" * 9,
    )
    assert m.componenti == {
        "sistema": 100,
        "strumenti": 50,
        "ricordi": 10,
        "storia": (10 + 4) + (20 + 4),
        "domanda": 3,
    }
    assert m.disponibile == 1024 - 150
    assert m.sfora == 0


def test_la_misura_dice_di_quanto_si_sfora() -> None:
    m = budget.misura(1024, 150, sistema="s" * 3 * 1000)
    assert m.sfora == 1000 - (1024 - 150)
    assert "SFORA" in m.come_riga()


def test_se_ci_sta_non_si_taglia_niente() -> None:
    storia = [messaggio(10), messaggio(10)]
    m = budget.misura(1024, 150, sistema="s" * 30, storia=storia, domanda="d")
    resta, ricordi, taglio = budget.riduci(m, storia, ["uno", "due"])
    assert resta == storia and ricordi == ["uno", "due"]
    assert not taglio.tagliato and not taglio.insufficiente


def test_si_taglia_prima_la_storia_dal_messaggio_piu_vecchio() -> None:
    storia = [messaggio(300), messaggio(300), messaggio(300)]
    m = budget.misura(1024, 150, sistema="s" * 3 * 100, storia=storia, domanda="d" * 3)
    assert m.sfora > 0
    resta, ricordi, taglio = budget.riduci(m, storia, ["ricordo"])
    assert resta == storia[1:] or resta == storia[2:], "doveva togliere i piu' vecchi"
    assert resta[-1] is storia[-1], "l'ultimo messaggio non si tocca per primo"
    assert ricordi == ["ricordo"], "i ricordi si toccano solo dopo la storia"
    assert taglio.storia_tolta == len(storia) - len(resta) and "storia" in taglio.motivi[0]


def test_finita_la_storia_si_tolgono_i_ricordi_dall_ultimo() -> None:
    ricordi = ["a" * 3 * 300, "b" * 3 * 300, "c" * 3 * 300]
    m = budget.misura(1024, 150, sistema="s" * 3 * 100, ricordi="\n".join(ricordi), domanda="d" * 3)
    _, ricordi_rimasti, taglio = budget.riduci(m, [], ricordi)
    assert ricordi_rimasti == ricordi[: len(ricordi_rimasti)], "i meno pertinenti sono gli ultimi"
    assert len(ricordi_rimasti) < len(ricordi)
    assert taglio.ricordi_tolti == len(ricordi) - len(ricordi_rimasti)


def test_sistema_strumenti_e_domanda_non_si_tagliano_mai_e_si_dice() -> None:
    storia = [messaggio(50)]
    m = budget.misura(
        1024, 150, sistema="s" * 3 * 2000, strumenti="t" * 3 * 100, domanda="d" * 3 * 100, storia=storia
    )
    resta, ricordi, taglio = budget.riduci(m, storia, ["ricordo"])
    assert resta == [] and ricordi == []
    assert taglio.insufficiente, "doveva dire che da soli non ci stanno"
    assert any("non ci stanno" in motivo for motivo in taglio.motivi)


def test_l_ordine_dichiarato_e_gli_intoccabili() -> None:
    assert budget.ORDINE_DI_TAGLIO == ("storia", "ricordi")
    assert set(budget.INTOCCABILI) == {"sistema", "strumenti", "domanda"}
    assert not set(budget.ORDINE_DI_TAGLIO) & set(budget.INTOCCABILI)


def test_l_agente_scrive_nel_log_quanto_pesa_il_prompt(monkeypatch, caplog) -> None:
    """Il prompt si misura a ogni richiesta che arriva al modello, e un prompt che non ci sta lo dice con un avviso."""
    import asyncio
    import logging

    from shinra.services.agent import ShinraAgent

    async def chat(self, messages, tools=None, temperature=None, **k):
        return {"success": True, "message": {"content": "Ciao.", "tool_calls": []}}

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    monkeypatch.setattr("shinra.services.agent.contesto_in_uso", lambda: 256)
    with caplog.at_level(logging.INFO, logger="Shinra"):
        asyncio.run(ShinraAgent().process_user_input("ciao come stai oggi"))
    righe = [r for r in caplog.records if "sistema=" in r.getMessage()]
    assert righe, "nessuna riga sul peso del prompt"
    assert "totale=" in righe[0].getMessage() and "domanda=" in righe[0].getMessage()
    assert (
        righe[0].levelno == logging.WARNING and "SFORA" in righe[0].getMessage()
    ), "con 256 di contesto doveva sforare"
