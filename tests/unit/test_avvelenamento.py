"""La guardia contro l'avvelenamento della memoria (#264): un testo con istruzioni non ha la forma di un ricordo."""

from __future__ import annotations

import pytest
import yaml

from shinra import percorsi
from shinra.domain import avvelenamento
from shinra.infra.lingue import lingue_disponibili, schemi

OSTILI = yaml.safe_load((percorsi.RADICE / "banco" / "memoria" / "ostili.yaml").read_text(encoding="utf-8"))[
    "tentativi"
]
RICORDI = yaml.safe_load((percorsi.RADICE / "banco" / "memoria" / "corpus.yaml").read_text(encoding="utf-8"))[
    "ricordi"
]


def verdetto(testo: str, lingua: str):
    return avvelenamento.valuta(testo, schemi(lingua).sospetto)


def test_ci_sono_almeno_venti_tentativi_e_in_piu_lingue():
    assert len(OSTILI) >= 20
    assert {t["lingua"] for t in OSTILI} >= {"it", "en"}


@pytest.mark.parametrize("tentativo", OSTILI, ids=lambda t: t["testo"][:45].replace("\n", " "))
def test_nessun_tentativo_ostile_ha_la_forma_di_un_ricordo(tentativo):
    esito = verdetto(tentativo["testo"], tentativo["lingua"])
    assert not esito.ammesso, f"passato come ricordo: {tentativo['testo']!r}"
    assert tentativo["motivo"] in esito.motivi, f"scartato per {esito.motivi}, atteso {tentativo['motivo']}"


@pytest.mark.parametrize("ricordo", RICORDI, ids=lambda r: r["id"])
def test_i_ricordi_veri_della_casa_passano(ricordo):
    """Una guardia che scarta anche i fatti veri e' peggio di nessuna: la casa smetterebbe di imparare."""
    for lingua in lingue_disponibili():
        esito = verdetto(ricordo["testo"], lingua)
        assert esito.ammesso, f"{lingua}: scartato {ricordo['testo']!r} per {esito.motivi}"


def test_ogni_lingua_ha_le_sue_espressioni():
    for lingua in lingue_disponibili():
        assert len(schemi(lingua).sospetto) >= 8, lingua


def test_un_testo_normale_di_pochi_caratteri_passa():
    assert verdetto("Il gatto si chiama Milo", "it").ammesso
    assert verdetto("The cat is called Milo", "en").ammesso


def test_il_dominio_non_contiene_parole_di_una_lingua():
    """Le parole che tradiscono un ordine stanno nei file delle lingue, non nel dominio."""
    import inspect
    import re

    sorgente = inspect.getsource(avvelenamento).lower()
    for parola in ("ignora", "dimentica", "da ora", "ignore", "forget", "from now on"):
        assert not re.search(rf"{re.escape(parola)}", sorgente.split('"""', 2)[-1]), parola
