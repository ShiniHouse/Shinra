"""Il materiale del sogno (#258): per profilo, con un tetto, e mai niente di un altro.

Le prove che contano: righe di registro, riassunti e ricordi di piu' profili **mescolati** non finiscono nel materiale di chi
non c'entra (salvo la casa condivisa); del registro si prende solo il nome dell'azione, mai i dettagli; dei ricordi mai il testo;
e con mesi di registro il materiale resta dentro i tetti.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from shinra.domain import sogno as dominio
from shinra.infra.db import depositi
from shinra.infra.db.riassunti import riassunti as deposito_riassunti
from shinra.services import registro, sogno

ADESSO = datetime(2026, 10, 14, 3, 0, tzinfo=timezone.utc)


def voce(attore, azione, esito="ok", dettagli=None):
    return {"attore": attore, "azione": azione, "esito": esito, "dettagli": dettagli or {}}


# ------------------------------------------------------------------ il dominio


def test_il_materiale_di_un_profilo_non_contiene_righe_di_un_altro():
    voci = [
        voce("alessio", "tool.control_device"),
        voce("alessio", "tool.control_device"),
        voce("sonia", "tool.comanda_serratura"),
        voce("marco", "tool.get_weather"),
        voce(None, "regola.scattata"),
    ]
    riassunti = [
        {"profilo": "alessio", "testo": "Hai chiesto: «la luce»."},
        {"profilo": "sonia", "testo": "SEGRETO di Sonia"},
    ]
    ricordi = [
        {"proprietario": "", "category": "casa"},
        {"proprietario": "alessio", "category": "salute"},
        {"proprietario": "sonia", "category": "sorpresa"},
    ]
    m = dominio.raccogli("alessio", voci, riassunti, ricordi)

    assert m.azioni == {"tool.control_device": {"riuscite": 2, "fallite": 0}}
    assert m.azioni_della_casa == {"regola.scattata": 1}
    assert m.riassunti == ["Hai chiesto: «la luce»."]
    assert m.ricordi_toccati == 2 and set(m.categorie) == {"casa", "salute"}
    testo = m.come_testo()
    for altrui in ("comanda_serratura", "get_weather", "SEGRETO", "sorpresa"):
        assert altrui not in testo, f"nel materiale di Alessio c'e' qualcosa di un altro: {altrui}"


def test_per_ogni_profilo_il_suo_materiale_e_solo_suo():
    voci = [voce(c, f"tool.{c}") for c in ("alessio", "sonia", "marco")]
    for chi in ("alessio", "sonia", "marco"):
        m = dominio.raccogli(chi, voci, [], [])
        assert list(m.azioni) == [f"tool.{chi}"]


def test_senza_profilo_non_c_e_niente_di_proprio():
    m = dominio.raccogli(
        "", [voce("alessio", "tool.x"), voce(None, "regola.y")], [{"profilo": "", "testo": "x"}], []
    )
    assert (
        m.azioni == {} and m.riassunti == []
    ), "un profilo vuoto non deve prendersi le righe senza attore come proprie"
    assert m.azioni_della_casa == {"regola.y": 1}


def test_del_registro_si_prende_il_nome_non_i_dettagli_e_dei_ricordi_non_il_testo():
    voci = [voce("alessio", "tool.comanda_serratura", dettagli={"codice": "4471", "nome": "Porta di Mario"})]
    ricordi = [{"proprietario": "alessio", "category": "salute", "text": "Prendo la medicina alle sette"}]
    testo = dominio.raccogli("alessio", voci, [], ricordi).come_testo()
    assert "4471" not in testo and "Mario" not in testo and "medicina" not in testo


def test_le_azioni_riuscite_e_fallite_si_contano_a_parte():
    voci = [voce("alessio", "tool.get_weather"), voce("alessio", "tool.get_weather", esito="errore")] * 3
    assert dominio.raccogli("alessio", voci, [], []).azioni["tool.get_weather"] == {
        "riuscite": 3,
        "fallite": 3,
    }


def test_le_azioni_piu_frequenti_vengono_per_prime_e_il_resto_si_taglia_dicendolo():
    voci = [voce("alessio", f"tool.rara_{i:02d}") for i in range(30)]
    voci += [voce("alessio", "tool.frequente")] * 5
    m = dominio.raccogli("alessio", voci, [], [])
    assert len(m.azioni) == dominio.AZIONI_MASSIME and next(iter(m.azioni)) == "tool.frequente"
    assert m.troncato is True


def test_con_mesi_di_registro_il_materiale_resta_dentro_il_tetto():
    voci = [voce("alessio", f"tool.azione_{i % 400}") for i in range(20000)]
    voci += [voce(None, f"regola.{i % 300}") for i in range(5000)]
    riassunti = [
        {"profilo": "alessio", "testo": "Hai chiesto: " + "una richiesta molto lunga " * 20}
        for _ in range(50)
    ]
    ricordi = [{"proprietario": "alessio", "category": f"categoria_{i}"} for i in range(200)]
    m = dominio.raccogli("alessio", voci, riassunti, ricordi)
    assert m.caratteri() <= dominio.CARATTERI_MASSIMI, f"il materiale e' di {m.caratteri()} caratteri"
    assert len(m.azioni) <= dominio.AZIONI_MASSIME and len(m.riassunti) <= dominio.RIASSUNTI_MASSIMI
    assert len(m.categorie) <= dominio.CATEGORIE_MASSIME
    assert m.troncato is True


def test_un_giorno_tranquillo_e_un_materiale_vuoto():
    assert dominio.raccogli("alessio", [], [], []).vuoto


# ------------------------------------------------------------------ il servizio


@pytest.fixture(autouse=True)
def pulito():
    for chi in ("alessio", "sonia"):
        deposito_riassunti.dimentica_profilo(chi)
    depositi.fatti.sostituisci_tutto([])
    yield
    for chi in ("alessio", "sonia"):
        deposito_riassunti.dimentica_profilo(chi)
    depositi.fatti.sostituisci_tutto([])


def scrivi_registro(attore, azione, quando, esito="ok"):
    from shinra.infra.db.modelli import VoceRegistro
    from shinra.infra.db.motore import sessione

    with sessione() as s:
        s.add(
            VoceRegistro(
                momento=quando.replace(tzinfo=None),
                attore=attore,
                canale="web",
                azione=azione,
                dettagli={},
                esito=esito,
            )
        )


def test_il_servizio_legge_il_periodo_giusto_e_solo_il_proprio_profilo():
    ieri_sera = ADESSO - timedelta(hours=5)
    scrivi_registro("alessio", "tool.prova_a", ieri_sera)
    scrivi_registro("alessio", "tool.prova_vecchia", ADESSO - timedelta(days=3))
    scrivi_registro("sonia", "tool.prova_b", ieri_sera)
    scrivi_registro(None, "regola.prova_casa", ieri_sera)
    scrivi_registro("", "regola.prova_casa_vuota", ieri_sera)

    m = sogno.materiali_del_periodo("alessio", ADESSO)

    assert set(m.azioni) == {"tool.prova_a"}, "ha preso un'azione fuori periodo o di un altro profilo"
    assert set(m.azioni_della_casa) == {"regola.prova_casa", "regola.prova_casa_vuota"}


def test_il_servizio_prende_i_riassunti_e_i_ricordi_del_periodo_e_solo_visibili():
    ora = ADESSO.replace(tzinfo=None)
    deposito_riassunti.aggiungi(
        "alessio", "Hai chiesto: «la luce».", 1, ora - timedelta(hours=2), ora + timedelta(days=30)
    )
    deposito_riassunti.aggiungi(
        "sonia", "Hai chiesto: «un segreto».", 1, ora - timedelta(hours=2), ora + timedelta(days=30)
    )
    deposito_riassunti.aggiungi("alessio", "Vecchio.", 1, ora - timedelta(days=5), ora + timedelta(days=30))
    depositi.fatti.aggiungi(
        {"id": "k_a", "text": "x", "category": "salute", "enabled": True, "proprietario": "alessio"}
    )
    depositi.fatti.aggiungi(
        {"id": "k_s", "text": "y", "category": "sorpresa", "enabled": True, "proprietario": "sonia"}
    )
    depositi.fatti.aggiungi({"id": "k_c", "text": "z", "category": "casa", "enabled": True})
    for k in ("k_a", "k_s", "k_c"):
        depositi.fatti.aggiorna(k, {"aggiornato_il": ora - timedelta(hours=1)})

    m = sogno.materiali_del_periodo("alessio", ADESSO)

    assert m.riassunti == ["Hai chiesto: «la luce»."]
    assert m.ricordi_toccati == 2 and set(m.categorie) == {"salute", "casa"}
    assert "sorpresa" not in json.dumps(m.categorie) and "segreto" not in m.come_testo()


def test_senza_profilo_il_servizio_non_prende_niente_di_proprio():
    ora = ADESSO - timedelta(hours=1)
    scrivi_registro("alessio", "tool.x", ora)
    scrivi_registro(None, "regola.y", ora)
    m = sogno.materiali_del_periodo("", ADESSO)
    assert m.azioni == {} and m.azioni_della_casa == {"regola.y": 1}


def test_registro_senza_attore_filtra_solo_le_voci_di_sistema():
    ora = ADESSO - timedelta(hours=1)
    scrivi_registro("alessio", "tool.x", ora)
    scrivi_registro(None, "regola.y", ora)
    azioni = {
        v["azione"]
        for v in registro.voci(
            limite=50, senza_attore=True, dal=ADESSO.replace(tzinfo=None) - timedelta(hours=2)
        )
    }
    assert "regola.y" in azioni and "tool.x" not in azioni
