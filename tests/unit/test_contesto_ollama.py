"""Il taglio del prompt non e' piu' silenzioso.

Il banco di prova (#183) ha mostrato che con `num_ctx` 1024 Ollama legge 514
token dei 5.459 del prompt e tiene solo la coda: il modello sceglie fra gli
ultimi strumenti del catalogo, e nessun log lo diceva. Ollama non segnala il
taglio: si capisce dal numero di token letti, che arriva al tetto.

Riferimento: issue #244.
"""

from __future__ import annotations

import pytest

from shinra.config.settings import settings
from shinra.infra.llm import ollama as modulo


class _Risposta:
    status_code = 200
    text = ""

    def __init__(self, dati):
        self._dati = dati

    def json(self):
        return self._dati


def _finto_httpx(monkeypatch, dati, visti):
    class _Cliente:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json):
            visti.append(json)
            return _Risposta(dati)

    monkeypatch.setattr(modulo.httpx, "AsyncClient", _Cliente)


def _avvisi(monkeypatch) -> list[str]:
    """Gli avvisi scritti nel log. Non si usa `caplog`: altri test cambiano la propagazione dei log."""
    visti: list[str] = []
    monkeypatch.setattr(modulo.logger, "warning", lambda msg, *args, **k: visti.append(msg % args))
    return visti


async def _chiedi(monkeypatch, prompt_eval_count, num_ctx=0):
    visti: list[dict] = []
    dati = {"message": {"content": "ok"}}
    if prompt_eval_count is not None:
        dati["prompt_eval_count"] = prompt_eval_count
    _finto_httpx(monkeypatch, dati, visti)
    monkeypatch.setattr(settings.llm, "num_ctx", num_ctx)
    esito = await modulo.OllamaClient().chat([{"role": "user", "content": "ciao"}])
    return esito, visti[0]["options"]["num_ctx"]


@pytest.mark.asyncio
async def test_un_prompt_che_riempie_il_contesto_viene_segnalato(monkeypatch):
    avvisi = _avvisi(monkeypatch)
    esito, ctx = await _chiedi(monkeypatch, prompt_eval_count=1024)

    assert ctx == 1024
    assert esito["troncato"] is True
    assert len(avvisi) == 1 and "tagliato" in avvisi[0] and "1024" in avvisi[0]


@pytest.mark.asyncio
async def test_un_prompt_che_ci_sta_non_allarma(monkeypatch):
    avvisi = _avvisi(monkeypatch)
    esito, _ = await _chiedi(monkeypatch, prompt_eval_count=400)

    assert esito["troncato"] is False
    assert avvisi == []


@pytest.mark.asyncio
async def test_senza_il_conteggio_non_si_inventa_un_taglio(monkeypatch):
    esito, _ = await _chiedi(monkeypatch, prompt_eval_count=None)
    assert esito["troncato"] is False


@pytest.mark.asyncio
async def test_il_contesto_si_puo_configurare(monkeypatch):
    esito, ctx = await _chiedi(monkeypatch, prompt_eval_count=5459, num_ctx=8192)

    assert ctx == 8192
    assert esito["troncato"] is False, "a 8192 il prompt da 5.459 token ci sta"
