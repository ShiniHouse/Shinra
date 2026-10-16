"""Le abitudini contate dal codice (#261): solo dal registro, solo proprie, mai su azioni sensibili o di sola lettura."""

from __future__ import annotations

from datetime import datetime, timedelta

from shinra.domain import abitudini

ADESSO = datetime(2026, 10, 14, 23, 0)


def voce(attore, strumento, parametri, giorni_fa, ora=7, minuto=30, esito="ok"):
    quando = (ADESSO - timedelta(days=giorni_fa)).replace(hour=ora, minute=minuto)
    return {
        "attore": attore,
        "azione": f"tool.{strumento}",
        "esito": esito,
        "momento": quando.isoformat(),
        "dettagli": {"parametri": parametri},
    }


LUCE = {"entity_id": "light.cucina", "action": "turn_on"}


def luce_per(attore, giorni, **extra):
    return [voce(attore, "control_device", LUCE, g, **extra) for g in giorni]


def test_quattro_giorni_alla_stessa_ora_sono_un_abitudine_con_le_prove():
    trovate = abitudini.trova(luce_per("alessio", [1, 2, 3, 5]), ADESSO)
    assert len(trovate) == 1
    a = trovate[0]
    assert (a.profilo, a.bersaglio, a.verbo, a.orario) == ("alessio", "light.cucina", "turn_on", "07:30")
    assert len(a.giorni) == 4


def test_tre_giorni_non_bastano():
    assert abitudini.trova(luce_per("alessio", [1, 2, 3]), ADESSO) == []


def test_lo_stesso_giorno_ripetuto_conta_una_volta():
    voci = luce_per("alessio", [1, 1, 1, 1, 1, 2, 3])
    assert abitudini.trova(voci, ADESSO) == []


def test_ore_diverse_non_fanno_un_abitudine():
    voci = [voce("alessio", "control_device", LUCE, g, ora=h) for g, h in [(1, 7), (2, 12), (3, 18), (4, 22)]]
    assert abitudini.trova(voci, ADESSO) == []


def test_fuori_dalla_finestra_non_conta():
    assert abitudini.trova(luce_per("alessio", [20, 21, 22, 23]), ADESSO) == []


def test_le_abitudini_di_un_profilo_non_sono_di_un_altro():
    voci = luce_per("alessio", [1, 2]) + luce_per("sonia", [3, 4])
    assert abitudini.trova(voci, ADESSO) == [], "due giorni di Alessio e due di Sonia non fanno quattro"


def test_le_voci_senza_attore_non_sono_abitudini_di_nessuno():
    assert abitudini.trova(luce_per(None, [1, 2, 3, 4]) + luce_per("", [5, 6]), ADESSO) == []


def test_le_azioni_fallite_non_contano():
    assert abitudini.trova(luce_per("alessio", [1, 2, 3, 4], esito="errore"), ADESSO) == []


def test_le_azioni_di_sola_lettura_non_si_propongono():
    voci = [voce("alessio", "get_weather", {"city": "Roma"}, g) for g in (1, 2, 3, 4, 5)]
    voci += [
        voce("alessio", "control_device", {"entity_id": "light.x", "action": "stato"}, g)
        for g in (1, 2, 3, 4)
    ]
    assert abitudini.trova(voci, ADESSO) == []


def test_le_azioni_sensibili_non_si_propongono_mai():
    porta = {"entity_id": "lock.ingresso", "azione": "sblocca"}
    garage = {"entity_id": "cover.garage", "azione": "apri"}
    voci = [voce("alessio", "comanda_serratura", porta, g) for g in (1, 2, 3, 4, 5)]
    voci += [voce("alessio", "comanda_tapparella", garage, g) for g in (1, 2, 3, 4, 5)]
    voci += [
        voce("alessio", "control_device", {"entity_id": "script.notte", "action": "turn_on"}, g)
        for g in (1, 2, 3, 4)
    ]
    assert abitudini.trova(voci, ADESSO) == []


def test_uno_strumento_sconosciuto_non_e_un_abitudine():
    voci = [voce("alessio", "strumento_nuovo", {"entity_id": "light.x"}, g) for g in (1, 2, 3, 4)]
    assert abitudini.trova(voci, ADESSO) == []


def test_senza_bersaglio_non_c_e_niente_da_proporre():
    voci = [voce("alessio", "control_device", {"action": "turn_on"}, g) for g in (1, 2, 3, 4)]
    assert abitudini.trova(voci, ADESSO) == []


def test_le_piu_solide_vengono_per_prime_e_c_e_un_tetto():
    voci = []
    for i in range(10):
        voci += [
            voce("alessio", "control_device", {"entity_id": f"light.l{i}", "action": "turn_on"}, g)
            for g in range(1, 5 + (i % 3))
        ]
    trovate = abitudini.trova(voci, ADESSO)
    assert len(trovate) == abitudini.ABITUDINI_MASSIME
    giorni = [len(a.giorni) for a in trovate]
    assert giorni == sorted(giorni, reverse=True)


def test_la_chiave_non_dipende_dai_giorni():
    a = abitudini.trova(luce_per("alessio", [1, 2, 3, 5]), ADESSO)[0]
    b = abitudini.trova(luce_per("alessio", [2, 3, 4, 6]), ADESSO + timedelta(days=0))[0]
    assert a.chiave == b.chiave


def test_righe_senza_momento_valido_si_ignorano():
    voci = luce_per("alessio", [1, 2, 3, 4])
    voci.append(
        {"attore": "alessio", "azione": "tool.control_device", "momento": "non e' una data", "dettagli": {}}
    )
    assert len(abitudini.trova(voci, ADESSO)) == 1
