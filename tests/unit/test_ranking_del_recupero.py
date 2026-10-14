"""Il recupero pesa anche l'importanza, la recenza e l'uso (#246): la formula, deterministica, e i casi limite.

I pesi partono da zero (il recupero di oggi) e si accendono solo con una misura. Qui si prova che a zero non cambia niente,
che ogni fattore fa cio' che dice e solo quello, e che la storia **riordina** senza far entrare cio' che non c'entra con la
domanda: l'unica eccezione dichiarata sono i ricordi fissati (importanza 5).
"""

from __future__ import annotations

import math

import pytest

from shinra.domain import recupero as r
from shinra.domain.recupero import Fatto, Pesi

GIORNO = 86400.0
ADESSO = 1_800_000_000.0


def fatto(id_, testo="la password del wifi e' nuova", **storia) -> Fatto:
    return Fatto(id_, testo, **storia)


def ordine(trovati) -> list[str]:
    return [t.fatto.identificativo for t in trovati]


# ------------------------------------------------------------- pesi a zero: come oggi


def test_con_i_pesi_a_zero_il_recupero_e_quello_di_prima():
    fatti = [
        fatto("a", "la password del wifi e' Girasole", importanza=5, usi=50, ultimo=ADESSO),
        fatto("b", "la password del wifi e' vecchia", importanza=1, usi=0, ultimo=ADESSO - 900 * GIORNO),
        fatto("c", "il gatto si chiama Milo"),
    ]
    senza = r.cerca("password wifi", fatti)
    con_zero = r.cerca("password wifi", fatti, pesi=Pesi(), adesso=ADESSO)
    assert [(t.fatto.identificativo, t.punteggio) for t in senza] == [
        (t.fatto.identificativo, t.punteggio) for t in con_zero
    ]
    assert all(not t.fattori for t in con_zero)


# --------------------------------------------------------------- l'importanza


def test_a_parita_di_somiglianza_conta_di_piu_chi_e_piu_importante():
    fatti = [fatto("basso", importanza=1), fatto("medio", importanza=3), fatto("alto", importanza=4)]
    trovati = r.cerca("password wifi", fatti, pesi=Pesi(importanza=0.1), adesso=ADESSO)
    assert ordine(trovati) == ["alto", "medio", "basso"]
    by = {t.fatto.identificativo: t for t in trovati}
    assert by["medio"].fattori["importanza"] == 0.0, "il 3 e' il valore di chi non ha detto niente"
    assert by["alto"].fattori["importanza"] == pytest.approx(0.05) and by["basso"].fattori[
        "importanza"
    ] == pytest.approx(-0.1)


def test_un_valore_fuori_scala_si_riporta_nella_scala():
    trovati = r.cerca(
        "password wifi",
        [fatto("x", importanza=99), fatto("y", importanza=-4)],
        pesi=Pesi(importanza=0.1),
        adesso=ADESSO,
    )
    by = {t.fatto.identificativo: t.fattori["importanza"] for t in trovati}
    assert by["y"] == pytest.approx(-0.1)


# ----------------------------------------------------------------- la recenza


def test_la_recenza_si_dimezza_a_ogni_emivita():
    pesi = Pesi(recenza=0.2, emivita_giorni=30)
    oggi = r.fattori_della_storia(fatto("a", ultimo=ADESSO), pesi, ADESSO)["recenza"]
    un_mese = r.fattori_della_storia(fatto("a", ultimo=ADESSO - 30 * GIORNO), pesi, ADESSO)["recenza"]
    due_mesi = r.fattori_della_storia(fatto("a", ultimo=ADESSO - 60 * GIORNO), pesi, ADESSO)["recenza"]
    assert oggi == pytest.approx(0.2) and un_mese == pytest.approx(0.1) and due_mesi == pytest.approx(0.05)


def test_il_piu_recente_vince_a_parita_di_somiglianza():
    fatti = [
        fatto("vecchio", "la password del wifi era Primavera", ultimo=ADESSO - 400 * GIORNO),
        fatto("nuovo", "la password del wifi e' Girasole", ultimo=ADESSO - 2 * GIORNO),
    ]
    assert ordine(r.cerca("password wifi", fatti, pesi=Pesi(recenza=0.1), adesso=ADESSO)) == [
        "nuovo",
        "vecchio",
    ]


def test_senza_data_la_recenza_pesa_zero_e_non_e_vecchio():
    f = r.fattori_della_storia(fatto("a", ultimo=None), Pesi(recenza=0.2), ADESSO)
    assert f == {}, "un ricordo senza data e' stato trattato come vecchio o come nuovo"
    assert (
        r.fattori_della_storia(fatto("a", ultimo=ADESSO), Pesi(recenza=0.2), None) == {}
    ), "senza un adesso non si puo' dire"


def test_una_data_nel_futuro_non_da_piu_del_massimo():
    f = r.fattori_della_storia(fatto("a", ultimo=ADESSO + 5 * GIORNO), Pesi(recenza=0.2), ADESSO)
    assert f["recenza"] == pytest.approx(0.2)


def test_un_emivita_nulla_non_divide_per_zero():
    assert (
        r.fattori_della_storia(fatto("a", ultimo=ADESSO), Pesi(recenza=0.2, emivita_giorni=0), ADESSO) == {}
    )


# -------------------------------------------------------------------- l'uso


def test_l_uso_e_logaritmico_e_ha_un_tetto():
    pesi = Pesi(uso=0.1)
    uno = r.fattori_della_storia(fatto("a", usi=1), pesi, ADESSO)["uso"]
    dieci = r.fattori_della_storia(fatto("a", usi=10), pesi, ADESSO)["uso"]
    venti = r.fattori_della_storia(fatto("a", usi=r.USI_DI_RIFERIMENTO), pesi, ADESSO)["uso"]
    mille = r.fattori_della_storia(fatto("a", usi=1000), pesi, ADESSO)["uso"]
    assert 0 < uno < dieci < venti == pytest.approx(0.1)
    assert mille == pytest.approx(0.1), "senza un tetto un ricordo vince solo perche' e' stato usato tanto"
    assert dieci - uno < venti - dieci + 0.05, "il decimo uso deve contare meno del primo"
    assert uno == pytest.approx(0.1 * math.log1p(1) / math.log1p(20))


def test_nessun_uso_nessun_rinforzo():
    assert r.fattori_della_storia(fatto("a", usi=0), Pesi(uso=0.1), ADESSO) == {}


# ------------------------------------------- la storia riordina, non fa entrare


def test_la_storia_non_fa_entrare_cio_che_non_c_entra_con_la_domanda():
    fatti = [
        fatto("giusto", "la password del wifi e' Girasole"),
        fatto("fuori_tema", "il gatto mangia alle sette", importanza=4, usi=500, ultimo=ADESSO),
    ]
    pesi = Pesi(importanza=1.0, recenza=1.0, uso=1.0)
    assert ordine(r.cerca("password wifi", fatti, pesi=pesi, adesso=ADESSO)) == ["giusto"]


def test_la_storia_non_ribalta_una_corrispondenza_molto_migliore_con_pesi_piccoli():
    fatti = [
        fatto("preciso", "la password del wifi di casa e' Girasole"),
        fatto("vago", "wifi", importanza=4, usi=20, ultimo=ADESSO),
    ]
    assert (
        ordine(
            r.cerca(
                "password wifi di casa",
                fatti,
                pesi=Pesi(importanza=0.02, recenza=0.02, uso=0.02),
                adesso=ADESSO,
            )
        )[0]
        == "preciso"
    )


# ------------------------------------------------------------------ i fissati


def test_un_ricordo_fissato_entra_sempre_e_in_testa():
    fatti = [
        fatto("giusto", "la password del wifi e' Girasole"),
        fatto("fissato", "in caso di incendio chiama il 115", importanza=5),
    ]
    trovati = r.cerca("password wifi", fatti)
    assert ordine(trovati) == ["fissato", "giusto"]
    assert trovati[0].fissato is True and trovati[1].fissato is False


def test_i_fissati_stanno_dentro_il_massimo():
    fatti = [fatto(f"f{i}", f"promemoria importante numero {i}", importanza=5) for i in range(12)]
    fatti += [fatto("g", "la password del wifi e' Girasole")]
    trovati = r.cerca("password wifi", fatti, massimo=8)
    assert len(trovati) == 8, "i fissati hanno sforato il budget"
    assert all(t.fissato for t in trovati), "i fissati vengono prima di tutto il resto"


def test_senza_fissati_non_cambia_niente():
    fatti = [fatto("a", "la password del wifi e' Girasole"), fatto("b", "il gatto mangia alle sette")]
    assert ordine(r.cerca("password wifi", fatti)) == ["a"]


# ------------------------------------------------------------------- spiegare


def test_spiega_dice_quanto_ha_pesato_ogni_fattore():
    fatti = [fatto("a", importanza=4, usi=5, ultimo=ADESSO - 30 * GIORNO), fatto("f", "x", importanza=5)]
    spiegati = r.spiega(
        r.cerca("password wifi", fatti, pesi=Pesi(importanza=0.1, recenza=0.2, uso=0.1), adesso=ADESSO)
    )
    per_id = {s["id"]: s for s in spiegati}
    assert set(per_id["a"]["storia"]) == {"importanza", "recenza", "uso"}
    assert per_id["a"]["storia"]["recenza"] == pytest.approx(0.1, abs=1e-3)
    assert per_id["f"]["fissato"] is True and per_id["a"]["fissato"] is False


# ------------------------------------------------- il servizio: sotto la soglia non cambia


async def test_sotto_la_soglia_si_mandano_tutti_qualunque_sia_il_peso(monkeypatch):
    from shinra.infra.db import depositi
    from shinra.services import conoscenza
    from shinra.services.conoscenza import ServizioConoscenza

    depositi.fatti.sostituisci_tutto([])
    depositi.fatti.aggiungi(
        {"id": "k_1", "text": "Il gatto si chiama Milo", "category": "casa", "enabled": True, "importanza": 1}
    )
    depositi.fatti.aggiungi(
        {
            "id": "k_2",
            "text": "La caldaia e' in cantina",
            "category": "casa",
            "enabled": True,
            "importanza": 5,
        }
    )
    monkeypatch.setattr(conoscenza, "PESI_DEL_RECUPERO", Pesi(importanza=1.0, recenza=1.0, uso=1.0))
    try:
        esito = await ServizioConoscenza().recupera("qualunque cosa")
        assert "Milo" in esito.testo and "caldaia" in esito.testo
        assert len(esito.entrati) == 2
    finally:
        depositi.fatti.sostituisci_tutto([])


async def test_il_servizio_passa_la_storia_al_recupero(monkeypatch):
    """Sopra la soglia, importanza e uso dei ricordi arrivano alla formula."""
    from shinra.infra.db import depositi
    from shinra.infra.llm import embedding
    from shinra.services import conoscenza
    from shinra.services.conoscenza import ServizioConoscenza

    async def senza_vettori(testi):
        return [None for _ in testi]

    monkeypatch.setattr(embedding, "calcola", senza_vettori)
    depositi.fatti.sostituisci_tutto([])
    for i in range(30):
        depositi.fatti.aggiungi(
            {"id": f"k_r{i}", "text": f"Un fatto di riempimento numero {i}", "category": "x", "enabled": True}
        )
    depositi.fatti.aggiungi(
        {
            "id": "k_poco",
            "text": "La password del wifi e' vecchia",
            "category": "casa",
            "enabled": True,
            "importanza": 1,
        }
    )
    depositi.fatti.aggiungi(
        {
            "id": "k_molto",
            "text": "La password del wifi e' nuova",
            "category": "casa",
            "enabled": True,
            "importanza": 4,
            "usi": 12,
        }
    )
    monkeypatch.setattr(conoscenza, "PESI_DEL_RECUPERO", Pesi(importanza=0.2, uso=0.2))
    try:
        esito = await ServizioConoscenza().recupera("password wifi")
        ids = [e["id"] for e in esito.entrati]
        assert ids[:2] == ["k_molto", "k_poco"], ids
        assert esito.fatti[0]["storia"]["importanza"] > 0 and esito.fatti[0]["storia"]["uso"] > 0
    finally:
        depositi.fatti.sostituisci_tutto([])
