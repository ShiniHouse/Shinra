"""Le fasce italiane, i contatori che si comportano male, e il non inventare.

Tre gruppi di test, per tre modi diversi di sbagliare.

**Le fasce** sono una regola pubblica di ARERA, quindi qui si verifica una
trascrizione: giorno per giorno, ora per ora, festivi compresi. Il caso che
si sbaglia piu' spesso non e' l'orario, e' il fuso: Home Assistant scrive i
suoi timestamp in UTC, e una fascia calcolata sull'ora UTC sbaglia di un'ora
d'inverno e di due d'estate — cioe' quasi sempre, e proprio nelle ore in cui
le fasce cambiano.

**I contatori** salgono e non si azzerano mai, tranne quando si azzerano. Il
consumo di un'ora e' una differenza fra due letture, e una differenza
negativa non e' un consumo negativo: e' un dispositivo riavviato.

**Il non inventare.** «Zero kilowattora» e «non lo so» sono risposte diverse,
e la prima detta al posto della seconda e' il modo piu' rapido per far
perdere fiducia a un conto in bolletta.

Riferimento: issue #24.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shinra.domain import energia as dominio
from shinra.domain import fasce

ROMA = fasce.FUSO
UTC = ZoneInfo("UTC")


def momento(anno, mese, giorno, ora, minuto=0):
    return datetime(anno, mese, giorno, ora, minuto, tzinfo=ROMA)


# ======================================================= le fasce


# Le date di Pasqua sono verificabili contro qualunque calendario: se
# l'algoritmo gregoriano fosse trascritto male, sbaglierebbe Pasquetta e con
# lei un giorno di tariffa all'anno.
@pytest.mark.parametrize(
    "anno,attesa",
    [
        (2020, date(2020, 4, 12)),
        (2021, date(2021, 4, 4)),
        (2022, date(2022, 4, 17)),
        (2023, date(2023, 4, 9)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2028, date(2028, 4, 16)),
        (2030, date(2030, 4, 21)),
        (2000, date(2000, 4, 23)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_pasqua_su_dodici_anni(anno, attesa):
    assert fasce.pasqua(anno) == attesa


def test_pasquetta_e_il_giorno_dopo_pasqua():
    assert fasce.pasquetta(2026) == date(2026, 4, 6)
    assert fasce.e_festivo(date(2026, 4, 6))


# 2026-09-07 e' un lunedi'. Da li' si costruisce tutta la settimana.
LUNEDI = 7


@pytest.mark.parametrize(
    "ora,attesa",
    [
        (0, fasce.F3),
        (6, fasce.F3),
        (7, fasce.F2),
        (8, fasce.F1),
        (12, fasce.F1),
        (18, fasce.F1),
        (19, fasce.F2),
        (22, fasce.F2),
        (23, fasce.F3),
    ],
)
def test_un_giorno_feriale_ora_per_ora(ora, attesa):
    assert fasce.fascia(momento(2026, 9, LUNEDI, ora)) == attesa


@pytest.mark.parametrize("giorno", range(LUNEDI, LUNEDI + 5))
def test_dal_lunedi_al_venerdi_le_ore_di_punta_ci_sono(giorno):
    assert fasce.fascia(momento(2026, 9, giorno, 10)) == fasce.F1


@pytest.mark.parametrize(
    "ora,attesa", [(6, fasce.F3), (7, fasce.F2), (12, fasce.F2), (22, fasce.F2), (23, fasce.F3)]
)
def test_il_sabato_non_ha_ore_di_punta(ora, attesa):
    """Dalle 7 alle 23 e' tutto intermedio: e' la regola che distingue il
    sabato dagli altri giorni lavorativi."""
    assert fasce.fascia(momento(2026, 9, LUNEDI + 5, ora)) == attesa


@pytest.mark.parametrize("ora", range(0, 24))
def test_la_domenica_e_fuori_punta_dalle_zero_alle_ventiquattro(ora):
    assert fasce.fascia(momento(2026, 9, LUNEDI + 6, ora)) == fasce.F3


# I dieci festivi fissi piu' Pasquetta. Ne bastano alcuni scelti nei giorni
# della settimana in cui la regola conta: un festivo di mercoledi' e' il caso
# che un calcolo basato solo sul giorno della settimana sbaglierebbe.
@pytest.mark.parametrize(
    "giorno",
    [
        date(2026, 1, 1),  # giovedi'
        date(2026, 1, 6),  # martedi'
        date(2026, 4, 6),  # Pasquetta, lunedi'
        date(2026, 4, 25),  # sabato
        date(2026, 5, 1),  # venerdi'
        date(2026, 6, 2),  # martedi'
        date(2026, 8, 15),  # sabato
        date(2026, 11, 1),  # domenica
        date(2026, 12, 8),  # martedi'
        date(2026, 12, 25),  # venerdi'
        date(2026, 12, 26),  # sabato
    ],
)
def test_i_festivi_sono_fuori_punta_tutto_il_giorno(giorno):
    """Undici giorni all'anno che un calcolo basato sul solo giorno della
    settimana sbaglierebbe."""
    alle_dieci = datetime(giorno.year, giorno.month, giorno.day, 10, tzinfo=ROMA)

    assert fasce.fascia(alle_dieci) == fasce.F3


def test_un_giorno_feriale_qualunque_non_e_festivo():
    """Il rovescio: senza, «tutto e' festivo» passerebbe i test sopra."""
    assert not fasce.e_festivo(date(2026, 9, 9))
    assert fasce.fascia(momento(2026, 9, 9, 10)) == fasce.F1


def test_le_feste_patronali_non_contano():
    """Valgono in un comune solo, e la tariffa e' nazionale."""
    assert not fasce.e_festivo(date(2026, 6, 24))  # San Giovanni, Torino
    assert not fasce.e_festivo(date(2026, 12, 7))  # Sant'Ambrogio, Milano


# ------------------------------------------------ il fuso, che si sbaglia


def test_un_momento_in_utc_viene_riportato_all_ora_italiana():
    """D'estate Roma e' due ore avanti: le 06:30 UTC di un lunedi' di luglio
    sono le 08:30, cioe' ore di punta. Senza conversione sarebbero F2."""
    estivo = datetime(2026, 7, 6, 6, 30, tzinfo=UTC)

    assert fasce.fascia(estivo) == fasce.F1


def test_anche_d_inverno_quando_l_ora_di_scarto_e_una():
    """Le 07:30 UTC di un lunedi' di gennaio sono le 08:30 a Roma."""
    invernale = datetime(2026, 1, 12, 7, 30, tzinfo=UTC)

    assert fasce.fascia(invernale) == fasce.F1


def test_un_momento_senza_fuso_e_creduto_sulla_parola():
    """Chi passa un orario senza fuso sta gia' parlando dell'ora di casa."""
    assert fasce.fascia(datetime(2026, 9, 9, 10)) == fasce.F1


# ------------------------------------------------ il prossimo cambio


def test_il_prossimo_cambio_di_un_feriale_e_la_sera():
    cambio = fasce.prossimo_cambio(momento(2026, 9, 9, 10))

    assert (cambio.hour, cambio.day) == (19, 9)
    assert fasce.fascia(cambio) == fasce.F2


def test_da_domenica_sera_si_salta_al_lunedi_mattina():
    """La domenica e' F3 per intero: il cambio non e' fra qualche ora, e'
    domani alle sette."""
    cambio = fasce.prossimo_cambio(momento(2026, 9, LUNEDI + 6, 20))

    assert (cambio.day, cambio.hour) == (14, 7)


def test_il_cambio_non_dissente_mai_dalla_fascia():
    """`prossimo_cambio` riattraversa le stesse regole invece di
    riscriverle: qui si verifica che il momento restituito sia davvero il
    primo diverso."""
    partenza = momento(2026, 12, 24, 20)
    cambio = fasce.prossimo_cambio(partenza)

    assert fasce.fascia(cambio) != fasce.fascia(partenza)
    assert fasce.fascia(cambio - timedelta(hours=1)) == fasce.fascia(partenza)


# ======================================================= i contatori


def L(ora, valore):
    return dominio.Lettura(momento(2026, 9, 9, ora), valore)


def test_il_consumo_e_la_differenza_fra_due_letture():
    """Un contatore dice a che punto e', non quanto e' passato."""
    letture = [L(8, 100.0), L(9, 101.5), L(10, 103.0)]

    assert [v for _, v in dominio.differenze(letture)] == [1.5, 1.5]


def test_un_contatore_azzerato_non_sottrae_consumo_mai_avvenuto():
    """Il dispositivo e' stato riavviato o il sensore ricreato: la
    differenza verrebbe -99, e toglierebbe dalla giornata un consumo che non
    e' mai stato annullato."""
    letture = [L(8, 100.0), L(9, 0.5), L(10, 1.5)]

    valori = [v for _, v in dominio.differenze(letture)]

    assert valori == [0.5, 1.0]
    assert all(v >= 0 for v in valori)


def test_un_salto_indietro_piccolo_e_un_guasto_non_un_consumo_negativo():
    letture = [L(8, 100.0), L(9, 99.0), L(10, 101.0)]

    assert [v for _, v in dominio.differenze(letture)] == [0.0, 2.0]


def test_le_letture_fuori_ordine_vengono_rimesse_in_fila():
    letture = [L(10, 103.0), L(8, 100.0), L(9, 101.5)]

    assert [v for _, v in dominio.differenze(letture)] == [1.5, 1.5]


def test_una_lettura_sola_non_e_un_consumo():
    """Il criterio della scheda in forma di dominio: senza abbastanza dati
    si solleva, non si restituisce zero."""
    with pytest.raises(dominio.SenzaDati):
        dominio.consumo_da_letture([L(8, 100.0)])

    with pytest.raises(dominio.SenzaDati):
        dominio.consumo_da_letture([])


def test_i_consumi_finiscono_nella_fascia_del_loro_momento():
    # Le 7 sono F2, le 10 sono F1, le 23 sono F3.
    letture = [L(6, 0.0), L(7, 1.0), L(10, 3.0), L(23, 6.0)]

    consumo = dominio.consumo_da_letture(letture)

    assert consumo.per_fascia[fasce.F2] == 1.0
    assert consumo.per_fascia[fasce.F1] == 2.0
    assert consumo.per_fascia[fasce.F3] == 3.0
    assert consumo.totale == 6.0


# ======================================================= le tariffe


def test_la_monoraria_ha_un_prezzo_solo():
    t = dominio.tariffa_monoraria(0.30)

    assert {t.prezzo(f) for f in fasce.FASCE} == {0.30}


def test_la_bioraria_mette_f2_e_f3_insieme():
    """E' come la scrivono i contratti italiani: le due si chiamano insieme
    «ore fuori punta»."""
    t = dominio.tariffa_bioraria(punta=0.35, fuori_punta=0.22)

    assert t.prezzo(fasce.F1) == 0.35
    assert t.prezzo(fasce.F2) == 0.22
    assert t.prezzo(fasce.F3) == 0.22


def test_la_trioraria_le_separa():
    t = dominio.tariffa_trioraria(0.35, 0.28, 0.20)

    assert (t.prezzo(fasce.F1), t.prezzo(fasce.F2), t.prezzo(fasce.F3)) == (0.35, 0.28, 0.20)


def test_il_costo_e_la_somma_per_fascia():
    consumo = dominio.Consumo({fasce.F1: 2.0, fasce.F2: 1.0, fasce.F3: 4.0})
    t = dominio.tariffa_trioraria(0.35, 0.28, 0.20)

    assert consumo.costo(t) == round(2 * 0.35 + 1 * 0.28 + 4 * 0.20, 2)


def test_una_fascia_senza_prezzo_ricade_sulla_piu_cara():
    """Sbagliare per eccesso in una stima di spesa e' meno dannoso che
    promettere un risparmio che non c'e'."""
    t = dominio.Tariffa(dominio.TRIORARIA, {fasce.F1: 0.40})

    assert t.prezzo(fasce.F3) == 0.40


def test_la_tariffa_di_ripiego_si_dichiara_stimata():
    """Un ordine di grandezza spacciato per un conto e' peggio di nessun
    conto."""
    assert dominio.tariffa_di_ripiego().stimata is True
    assert dominio.tariffa_monoraria(0.30).stimata is False


def test_la_fascia_dominante_e_dove_conviene_agire():
    consumo = dominio.Consumo({fasce.F1: 5.0, fasce.F2: 1.0, fasce.F3: 2.0})

    assert consumo.dominante() == fasce.F1


def test_il_costo_orario_di_un_carico():
    """Mille watt per un'ora e' un kilowattora."""
    t = dominio.tariffa_monoraria(0.30)

    assert dominio.costo_orario(1000, t, momento(2026, 9, 9, 10)) == 0.3
    assert dominio.costo_orario(60, t, momento(2026, 9, 9, 10)) == 0.018


@pytest.mark.parametrize(
    "valore,atteso",
    [(0.01, "1 centesimo"), (0.38, "38 centesimi"), (1.0, "1,00 euro"), (12.5, "12,50 euro")],
)
def test_gli_euro_come_li_direbbe_una_persona(valore, atteso):
    assert dominio.in_euro(valore) == atteso
