"""Ricordi doppi o in contraddizione (#260): il codice li trova, solo dello stesso proprietario, e non porta fuori nessun testo."""

from __future__ import annotations

from shinra.domain import fusione


def r(id_, testo, chi="alessio", stato="attivo", **extra):
    return {"id": id_, "text": testo, "proprietario": chi, "stato": stato, **extra}


def test_due_frasi_quasi_uguali_sono_doppie():
    coppie = fusione.trova_coppie(
        [r("a", "La caldaia della casa sta in cantina"), r("b", "la caldaia della casa sta in cantina.")]
    )
    assert [(c.tipo, c.a, c.b) for c in coppie] == [(fusione.DOPPIO, "a", "b")]


def test_stessa_frase_con_un_numero_diverso_e_una_contraddizione_sospetta():
    coppie = fusione.trova_coppie(
        [
            r("a", "La sveglia di Alessio suona alle 7 nei giorni feriali"),
            r("b", "La sveglia di Alessio suona alle 8 nei giorni feriali"),
        ]
    )
    assert [c.tipo for c in coppie] == [fusione.CONTRADDITTORIO]


def test_frasi_diverse_non_sono_niente():
    assert (
        fusione.trova_coppie([r("a", "Mi piace il tè verde al mattino"), r("b", "La caldaia sta in cantina")])
        == []
    )


def test_mai_un_ricordo_di_uno_con_quello_di_un_altro():
    uguali = "La caldaia della casa sta in cantina"
    assert fusione.trova_coppie([r("a", uguali, chi="alessio"), r("b", uguali, chi="sonia")]) == []


def test_i_ricordi_della_casa_non_hanno_a_chi_proporli():
    uguali = "La caldaia della casa sta in cantina"
    assert fusione.trova_coppie([r("a", uguali, chi=""), r("b", uguali, chi="")]) == []


def test_archiviati_o_spenti_non_si_confrontano():
    uguali = "La caldaia della casa sta in cantina"
    assert fusione.trova_coppie([r("a", uguali), r("b", uguali, stato="archiviato")]) == []
    assert fusione.trova_coppie([r("a", uguali), r("b", uguali, enabled=False)]) == []


def test_le_frasi_troppo_corte_non_si_confrontano():
    assert fusione.trova_coppie([r("a", "Ciao"), r("b", "Ciao")]) == []


def test_la_chiave_non_dipende_dall_ordine_ne_dalla_notte():
    a = fusione.Coppia(fusione.DOPPIO, "alessio", "x", "y", 0.9)
    b = fusione.Coppia(fusione.DOPPIO, "alessio", "y", "x", 0.95)
    assert a.chiave == b.chiave
    assert a.chiave != fusione.Coppia(fusione.CONTRADDITTORIO, "alessio", "x", "y", 0.9).chiave


def test_c_e_un_tetto_per_notte_e_per_proprietario():
    ricordi = [r(f"k{i}", f"La lampada numero {i} della stanza grande va tenuta accesa") for i in range(40)]
    assert len(fusione.trova_coppie(ricordi)) <= fusione.COPPIE_MASSIME


def test_il_risultato_porta_solo_identificativi():
    (c,) = fusione.trova_coppie(
        [
            r("a", "Il segreto di Alessio e' nel cassetto blu"),
            r("b", "Il segreto di Alessio e' nel cassetto blu"),
        ]
    )
    assert "segreto" not in repr(c) and "cassetto" not in repr(c)


def test_con_molti_ricordi_il_confronto_resta_limitato():
    ricordi = [r(f"k{i}", f"Ricordo distinto numero {i} {chr(97 + i % 26) * 5}") for i in range(2000)]
    fusione.trova_coppie(ricordi)  # non deve metterci un'eternita'
