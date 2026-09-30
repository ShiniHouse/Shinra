"""La ricetta della guida allo sviluppo, eseguita (issue #38).

`docs/SVILUPPO.md` dice che per aggiungere uno strumento bastano un modulo e
tre punti in `registry.py`, e che il resto — registro delle azioni, traduzione
di un permesso negato, errori — arriva gratis da `execute_tool`. Una guida che
promette una cosa cosi' deve poterla dimostrare: qui si fa esattamente quello
che la guida descrive, con uno strumento inventato, e si guarda cosa succede.

Se un giorno `execute_tool` smettesse di tracciare o di tradurre i rifiuti, la
guida direbbe una cosa falsa e questo test lo dice prima di chi la legge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shinra.services import registro
from shinra.services.permessi import PermessoNegato
from shinra.skills import registry

GUIDA = Path(__file__).resolve().parent.parent.parent / "docs" / "SVILUPPO.md"


@pytest.fixture
def strumento_nuovo(monkeypatch):
    """Il modulo d'esempio della guida, registrato come dice la guida."""

    async def saluta(nome: str):
        if not nome.strip():
            return {"success": False, "error": "Dimmi chi devo salutare."}
        return {"success": True, "message": f"Ciao {nome}!"}

    schema = {
        "type": "function",
        "function": {
            "name": "saluta",
            "description": "Saluta una persona per nome.",
            "parameters": {
                "type": "object",
                "properties": {"nome": {"type": "string", "description": "Chi salutare."}},
                "required": ["nome"],
            },
        },
    }
    monkeypatch.setitem(registry.TOOL_HANDLERS, "saluta", saluta)
    monkeypatch.setattr(registry, "TOOLS_SCHEMA", [*registry.TOOLS_SCHEMA, schema])
    return saluta


def _voci() -> list[dict]:
    return registro.elenco(limite=20)


async def test_uno_strumento_registrato_come_dice_la_guida_funziona(strumento_nuovo):
    esito = await registry.execute_tool("saluta", {"nome": "Sonia"})

    assert esito == {"success": True, "message": "Ciao Sonia!"}


async def test_e_lascia_una_voce_nel_registro_senza_che_lo_scriva_chi_l_ha_fatto(strumento_nuovo):
    await registry.execute_tool("saluta", {"nome": "Sonia"})

    voce = next(v for v in _voci() if v["azione"] == "tool.saluta")
    assert voce["esito"] == registro.ESITO_OK
    assert voce["dettagli"]["parametri"] == {"nome": "Sonia"}


async def test_un_guasto_restituito_risulta_errore_nel_registro(strumento_nuovo):
    """La convenzione della guida: si restituisce `success: False`, non si solleva."""
    esito = await registry.execute_tool("saluta", {"nome": "  "})

    assert esito["success"] is False
    voce = next(v for v in _voci() if v["azione"] == "tool.saluta")
    assert voce["esito"] == registro.ESITO_ERRORE


async def test_un_permesso_negato_diventa_una_risposta_leggibile(monkeypatch, strumento_nuovo):
    async def riservato(**_):
        raise PermessoNegato("sicurezza.comanda", "Questo non puoi farlo.")

    monkeypatch.setitem(registry.TOOL_HANDLERS, "saluta", riservato)

    esito = await registry.execute_tool("saluta", {"nome": "x"})

    assert esito["success"] is False and esito["permesso_negato"] is True
    assert esito["spiegazione"] == "Questo non puoi farlo."
    voce = next(v for v in _voci() if v["azione"] == "tool.saluta")
    assert voce["esito"] == registro.ESITO_NEGATO


def test_lo_schema_d_esempio_ha_la_forma_che_la_guida_descrive(strumento_nuovo):
    nomi = {s["function"]["name"] for s in registry.TOOLS_SCHEMA}
    assert "saluta" in nomi
    assert json.dumps(registry.TOOLS_SCHEMA)  # serializzabile: e' quello che parte verso Ollama


# ---------------------------------------------------- la guida nomina cose vere


def test_i_nomi_che_la_guida_cita_esistono():
    """Una ricetta che nomina `registry.py`, `TOOL_HANDLERS` o un test che non
    ci sono piu' manda a cercare nel posto sbagliato."""
    testo = GUIDA.read_text(encoding="utf-8")

    assert "TOOL_HANDLERS" in testo and "TOOLS_SCHEMA" in testo
    assert hasattr(registry, "TOOL_HANDLERS") and hasattr(registry, "TOOLS_SCHEMA")

    radice = GUIDA.parent.parent
    for percorso in (
        "src/shinra/skills/registry.py",
        "src/shinra/infra/db/modelli.py",
        "src/shinra/infra/db/depositi.py",
        "web/static/js/principale.js",
        "web/static/js/stato.js",
        "scripts/genera_api.py",
        "tests/unit/test_domini_casa.py",
        "tests/unit/test_intenti.py",
        "tests/unit/test_lingua_per_utente.py",
        "tests/unit/test_api_regole.py",
    ):
        assert percorso in testo or Path(percorso).name in testo, f"la guida non nomina piu' {percorso}"
        assert (radice / percorso).is_file(), f"la guida nomina {percorso}, che non esiste"


def test_ogni_test_nominato_dalla_guida_esiste():
    """La tabella «cosa ti dicono i test» vale solo se i nomi sono veri."""
    import re

    radice = GUIDA.parent.parent
    sorgenti = "\n".join(p.read_text(encoding="utf-8") for p in (radice / "tests").rglob("*.py"))
    nominati = set(re.findall(r"`(test_[a-z0-9_]+)`", GUIDA.read_text(encoding="utf-8")))

    assert len(nominati) >= 8, f"test nominati dalla guida: {sorted(nominati)}"
    mancanti = sorted(n for n in nominati if f"def {n}" not in sorted_sorgenti(sorgenti, n))
    assert mancanti == [], f"la guida nomina test che non esistono: {mancanti}"


def sorted_sorgenti(sorgenti: str, _nome: str) -> str:
    return sorgenti
