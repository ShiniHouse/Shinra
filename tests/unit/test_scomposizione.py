"""Spezzare una frase in una cosa per pezzo, col codice (#432): `shinra.domain.scomposizione`, con i dati delle lingue vere."""

from __future__ import annotations

import pytest

from shinra.domain import scomposizione as sc
from shinra.infra.lingue import schemi


def pezzi(frase, lingua="it", **extra):
    s = schemi(lingua)
    return sc.spezza(frase, s.parole_azione, {**s.scomposizione, **extra})


@pytest.mark.parametrize(
    ("frase", "attesi"),
    [
        (
            "chiudi la tapparella del salotto e accendi la luce del salotto",
            ["chiudi la tapparella del salotto", "accendi la luce del salotto"],
        ),
        (
            "dimmi che tempo fa a Roma e ricordami di chiamare il dentista",
            ["dimmi che tempo fa a Roma", "ricordami di chiamare il dentista"],
        ),
        (
            "accendi le luci del bagno e della camera e porta il clima del salotto a 22",
            ["accendi le luci del bagno e della camera", "porta il clima del salotto a 22"],
        ),
        (
            "vado a dormire: spegni le luci di salotto e cucina e attiva l'allarme",
            ["vado a dormire spegni le luci di salotto e cucina", "attiva l'allarme"],
        ),
        ("spegni la luce, poi apri la tapparella", ["spegni la luce", "apri la tapparella"]),
        ("accendi la luce della cucina", ["accendi la luce della cucina"]),
    ],
)
def test_il_codice_spezza_una_frase_in_una_cosa_per_pezzo(frase, attesi):
    assert pezzi(frase) == attesi


def test_un_pezzo_senza_azione_si_riattacca_al_vicino():
    assert pezzi("accendi le luci del bagno e della camera") == ["accendi le luci del bagno e della camera"]


def test_una_e_con_l_apostrofo_o_dentro_una_parola_non_taglia():
    assert len(pezzi("guarda com'e' il clima del salotto")) == 1
    assert len(pezzi("accendi la tv e basta")) == 1


@pytest.mark.parametrize("frase", ["ciao come stai", "e e e", ", ,"])
def test_senza_azioni_riconoscibili_non_si_inventa_niente(frase):
    assert pezzi(frase) == [frase] or pezzi(frase) == [frase.strip()]


@pytest.mark.parametrize("vuota", ["", "   ", None])
def test_una_frase_vuota_non_ha_pezzi(vuota):
    assert pezzi(vuota) == []


def test_i_pezzi_hanno_un_tetto():
    frase = " e ".join(f"accendi la luce {n}" for n in range(30))
    assert len(pezzi(frase)) == sc.MASSIMO_PEZZI


def test_il_pronome_prende_il_nome_dell_ultimo_dispositivo_detto():
    assert pezzi("spegni la luce del salotto e accendi quella del corridoio") == [
        "spegni la luce del salotto",
        "accendi la luce del corridoio",
    ]
    assert (
        pezzi("chiudi le tapparelle e spegni la luce e accendi quella del bagno")[-1]
        == "accendi la luce del bagno"
    )


def test_senza_un_nome_prima_il_pronome_resta_com_e():
    assert pezzi("accendi quella del corridoio") == ["accendi quella del corridoio"]


def test_ventila_e_una_parola_d_azione():
    assert pezzi("spegni la luce del salotto e ventila lo studio") == [
        "spegni la luce del salotto",
        "ventila lo studio",
    ]


def test_funziona_anche_in_inglese_con_le_sue_parole():
    assert pezzi("turn off the kitchen light and turn on the fan, then close the blinds", "en") == [
        "turn off the kitchen light",
        "turn on the fan",
        "close the blinds",
    ]
    assert pezzi("turn off the living room light and switch on that one", "en")[-1].startswith("switch on")


def test_senza_i_dati_della_lingua_la_frase_resta_intera():
    assert sc.spezza("accendi la luce e spegni la tv", ("accend", "spegn"), {}) == [
        "accendi la luce e spegni la tv"
    ]


def test_la_lingua_ha_tutti_i_dati_della_scomposizione():
    for lingua in ("it", "en"):
        lessico = schemi(lingua).scomposizione
        assert (
            lessico["separatori"] and lessico["pronomi"] and lessico["nomi"] and "parole_in_piu" in lessico
        ), lingua
