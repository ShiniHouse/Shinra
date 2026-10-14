"""Il banco della memoria misura quello che dice di misurare (#269).

Gira in CI senza rete: il corpus e' valido, il conteggio e' giusto (provato con un finto modello perfetto e con uno
che sbaglia di proposito), e il recupero **solo testuale** di oggi non peggiora sotto il suo livello misurato.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def banco():
    spec = importlib.util.spec_from_file_location("banco_memoria", RADICE / "scripts" / "banco_memoria.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def corpus(banco):
    return banco.carica()


def test_il_corpus_e_valido(corpus) -> None:
    ids = [r["id"] for r in corpus["ricordi"]]
    assert len(ids) == len(set(ids)), "ricordi con lo stesso id"
    domande = [d["id"] for d in corpus["domande"]]
    assert len(domande) == len(set(domande)), "domande con lo stesso id"
    for d in corpus["domande"]:
        assert set(d["attesi"]) <= set(ids), f"{d['id']}: attende un ricordo che non esiste"
    assert any(not d["attesi"] for d in corpus["domande"]), "servono domande senza risposta"
    assert {d["tipo"] for d in corpus["domande"]} >= {"diretta", "parafrasi", "numero", "senza_risposta"}


def test_un_modello_perfetto_trova_tutto_e_non_fa_rumore(banco, corpus) -> None:
    r = banco.misura(corpus, banco.vettori_perfetti(corpus))
    assert r["recall_3"] == 1.0 and r["recall_k"] == 1.0
    assert r["mrr"] == 1.0
    assert r["silenzio"] == 1.0
    assert r["con_vettori"] is True


def test_un_modello_che_sbaglia_di_proposito_si_vede(banco, corpus) -> None:
    """Se ogni domanda punta al ricordo sbagliato, il banco deve dirlo, non premiarlo."""
    ricordi, _ = banco.vettori_perfetti(corpus)
    ids = [r["id"] for r in corpus["ricordi"]]
    sbagliati = {}
    for d in corpus["domande"]:
        if d["attesi"]:
            fuori = next(i for i in ids if i not in d["attesi"])
            sbagliati[d["id"]] = [1.0 if i == fuori else 0.0 for i in ids]
        else:
            sbagliati[d["id"]] = [0.0] * len(ids)
    r = banco.misura(corpus, (ricordi, sbagliati))
    assert r["recall_3"] < 0.5, "il banco premia un modello che sbaglia"


def test_il_rumore_nelle_domande_senza_risposta_non_conta_come_silenzio(banco, corpus) -> None:
    ricordi, domande = banco.vettori_perfetti(corpus)
    ids = [r["id"] for r in corpus["ricordi"]]
    rumorosi = dict(domande)
    senza = next(d["id"] for d in corpus["domande"] if not d["attesi"])
    rumorosi[senza] = [1.0] + [0.0] * (len(ids) - 1)  # somiglia a un ricordo che non c'entra
    r = banco.misura(corpus, (ricordi, rumorosi))
    assert r["silenzio"] < 1.0


def test_il_recupero_solo_testuale_non_scende_sotto_il_livello_misurato(banco, corpus) -> None:
    """Il 2026-10-13: solo testo, le domande con le parole del ricordo e quelle coi numeri si trovano tutte;
    le parafrasi quasi mai (e' il motivo dei vettori). E senza risposta non esce rumore."""
    r = banco.misura(corpus)
    assert r["con_vettori"] is False
    assert r["per_tipo"]["diretta"]["recall_3"] == 1.0
    assert r["per_tipo"]["numero"]["recall_3"] == 1.0
    assert r["silenzio"] == 1.0
    assert r["recall_3"] >= 0.6, "il recupero testuale e' peggiorato"


def test_il_rapporto_si_scrive(banco, corpus) -> None:
    testo = banco.rapporto(banco.misura(corpus), "prova")
    assert "recall@3" in testo and "MRR" in testo and "solo testo" in testo


# ----------------------------------------------- l'ablazione della storia dei ricordi (#246)


def test_con_i_pesi_a_zero_la_misura_e_quella_di_prima(banco, corpus):
    from shinra.domain import recupero

    assert banco.misura(corpus, pesi=recupero.Pesi()) == banco.misura(corpus)


def test_l_ablazione_misura_un_fattore_alla_volta(banco, corpus):
    a = banco.ablazione(corpus)
    assert list(a) == ["nessuno (oggi)", "solo importanza", "solo recenza", "solo uso", "tutti e tre"]
    assert all({"recall_3", "mrr", "silenzio"} <= set(v) for v in a.values())


def test_la_storia_non_peggiora_il_recupero_e_non_fa_rumore(banco, corpus):
    """Il criterio della scheda: recall e MRR non peggiorano, e il silenzio sulle domande senza risposta resta intero."""
    a = banco.ablazione(corpus)
    base = a["nessuno (oggi)"]
    for nome, v in a.items():
        assert v["recall_3"] >= base["recall_3"], nome
        assert v["mrr"] >= base["mrr"], nome
        assert (
            v["silenzio"] == 1.0
        ), f"{nome}: la storia ha fatto uscire rumore dove non c'era niente da trovare"


def test_la_recenza_risolve_il_conflitto_fra_il_ricordo_vecchio_e_quello_nuovo(banco, corpus):
    """Due ricordi dicono la stessa cosa (la password del wifi): oggi vince chi viene prima nel file, con la storia chi vale oggi."""
    from shinra.domain import recupero

    senza = banco.misura(corpus)["per_tipo"]["conflitto"]["mrr"]
    con = banco.misura(corpus, pesi=recupero.Pesi(recenza=0.1))["per_tipo"]["conflitto"]["mrr"]
    assert senza == 0.5 and con == 1.0, (senza, con)


def test_il_rapporto_dell_ablazione_si_scrive(banco, corpus):
    testo = banco.rapporto_ablazione(banco.ablazione(corpus), 0.1)
    assert "Ablazione" in testo and "solo recenza" in testo and "(+0." in testo
