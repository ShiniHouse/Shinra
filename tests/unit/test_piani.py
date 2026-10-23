"""Il controllo dei piani di un modello (#191, `shinra.domain.piani`): il modello non e' fidato, e il codice dice cosa si esegue e perche' no."""

from __future__ import annotations

import pytest

from shinra.domain import piani
from shinra.skills.registry import TOOLS_SCHEMA

FUNZIONI = {s["function"]["name"]: s["function"] for s in TOOLS_SCHEMA}
DISPOSITIVI = {"light.cucina", "light.salotto", "climate.camera", "cover.salotto", "tapparella salotto"}


def passo(nome, **argomenti):
    return {"strumento": nome, "argomenti": argomenti}


# ------------------------------------------------------------------ completare cio' che e' ovvio


def test_un_obbligatorio_ovvio_si_completa():
    completato, mancanti = piani.completa_argomenti(
        {"entity_id": "climate.camera", "temperatura": 20}, FUNZIONI["comanda_clima"]
    )
    assert completato["azione"] == "temperatura" and mancanti == []


def test_un_obbligatorio_che_non_si_puo_dedurre_resta_mancante():
    _, mancanti = piani.completa_argomenti({"entity_id": "climate.camera"}, FUNZIONI["comanda_clima"])
    assert mancanti == ["azione"]


def test_fra_due_scelte_non_si_indovina():
    """`temperatura` e `umidita` sono entrambi valori di `azione`: la frase non dice quale."""
    completato, mancanti = piani.completa_argomenti(
        {"entity_id": "climate.camera", "temperatura": 20, "umidita": 40}, FUNZIONI["comanda_clima"]
    )
    assert mancanti == ["azione"] and "azione" not in completato


def test_un_parametro_dato_non_si_tocca_nemmeno_se_c_e_un_altro_candidato():
    completato, mancanti = piani.completa_argomenti(
        {"entity_id": "climate.camera", "azione": "spegni", "temperatura": 20}, FUNZIONI["comanda_clima"]
    )
    assert completato["azione"] == "spegni" and mancanti == []


@pytest.mark.parametrize("vuoto", [None, ""])
def test_un_valore_vuoto_vale_come_mancante(vuoto):
    completato, _ = piani.completa_argomenti(
        {"entity_id": "climate.camera", "azione": vuoto, "temperatura": 20}, FUNZIONI["comanda_clima"]
    )
    assert completato["azione"] == "temperatura"


def test_non_si_completa_con_un_valore_che_non_e_una_scelta():
    """Un obbligatorio senza `enum` (un testo libero) non si deduce mai: non c'e' una lista da cui scegliere."""
    funzione = {"parameters": {"properties": {"text": {"type": "string"}}, "required": ["text"]}}
    assert piani.completa_argomenti({"time_info": "domani"}, funzione) == ({"time_info": "domani"}, ["text"])


def test_gli_argomenti_di_partenza_non_si_modificano():
    originale = {"entity_id": "climate.camera", "temperatura": 20}
    piani.completa_argomenti(originale, FUNZIONI["comanda_clima"])
    assert originale == {"entity_id": "climate.camera", "temperatura": 20}


# ------------------------------------------------------------------ validare i passi


def codici(scarti):
    return [(s.numero, s.codice) for s in scarti]


def test_un_piano_giusto_passa_intero_anche_con_un_alias():
    accettati, scarti = piani.valida_passi(
        [
            passo("control_device", entity_id="light.cucina", action="turn_off"),
            passo(
                "comanda_tapparella", entity_id="Tapparella Salotto", azione="chiudi"
            ),  # un alias, maiuscole comprese
        ],
        FUNZIONI,
        DISPOSITIVI,
    )
    assert [p.nome for p in accettati] == ["control_device", "comanda_tapparella"] and scarti == []


def test_il_modello_non_e_fidato():
    accettati, scarti = piani.valida_passi(
        [
            passo("apri_il_garage", entity_id="cover.garage"),
            passo("control_device", entity_id="light.mansarda", action="turn_on"),
            passo("control_device", entity_id="light.cucina", action="turn_on"),
        ],
        FUNZIONI,
        DISPOSITIVI,
    )
    assert [p.argomenti["entity_id"] for p in accettati] == ["light.cucina"]
    assert codici(scarti) == [(1, piani.STRUMENTO_INESISTENTE), (2, piani.DISPOSITIVO_INESISTENTE)]
    assert scarti[0].dettaglio == "apri_il_garage" and scarti[1].dettaglio == "light.mansarda"


def test_un_passo_senza_i_suoi_obbligatori_si_scarta_e_dice_cosa_manca():
    accettati, scarti = piani.valida_passi(
        [
            passo("comanda_clima", entity_id="climate.camera"),
            passo("comanda_clima", entity_id="climate.camera", temperatura=20),
        ],
        FUNZIONI,
        DISPOSITIVI,
    )
    assert [p.argomenti["azione"] for p in accettati] == ["temperatura"], "il secondo passo si completa"
    assert (
        codici(scarti) == [(1, piani.OBBLIGATORIO_MANCANTE)] and scarti[0].dettaglio == "comanda_clima:azione"
    )


@pytest.mark.parametrize("cattivo", ["accendi", 7, None, ["x"], {"argomenti": {}}, {"strumento": 5}])
def test_un_passo_malformato_si_scarta_senza_rompere_i_vicini(cattivo):
    accettati, scarti = piani.valida_passi([cattivo, passo("stato_aperture")], FUNZIONI, DISPOSITIVI)
    assert [p.nome for p in accettati] == ["stato_aperture"] and len(scarti) == 1


def test_gli_argomenti_che_non_sono_un_oggetto_si_scartano():
    accettati, scarti = piani.valida_passi(
        [{"strumento": "stato_aperture", "argomenti": "tutte"}], FUNZIONI, DISPOSITIVI
    )
    assert accettati == [] and codici(scarti) == [(1, piani.ARGOMENTI_NON_VALIDI)]


def test_argomenti_assenti_valgono_come_vuoti():
    accettati, _ = piani.valida_passi([{"strumento": "stato_aperture"}], FUNZIONI, DISPOSITIVI)
    assert [p.argomenti for p in accettati] == [{}]


def test_un_modello_che_continua_ad_aggiungere_passi_si_ferma_al_tetto():
    molti = [passo("control_device", entity_id="light.cucina", action="turn_on")] * 30
    accettati, scarti = piani.valida_passi(molti, FUNZIONI, DISPOSITIVI)
    assert len(accettati) == piani.MASSIMO_PASSI
    assert codici(scarti) == [(piani.MASSIMO_PASSI + 1, piani.OLTRE_IL_TETTO)]


@pytest.mark.parametrize("non_un_elenco", [None, "piano", {"passi": []}, 5])
def test_qualunque_cosa_che_non_e_un_elenco_e_nessun_passo(non_un_elenco):
    assert piani.valida_passi(non_un_elenco, FUNZIONI, DISPOSITIVI) == ([], [])


def test_senza_dispositivi_noti_nessun_entity_id_passa():
    """Una casa vuota non ha dispositivi: un `entity_id` e' sempre un'invenzione. Gli strumenti senza `entity_id` passano."""
    accettati, scarti = piani.valida_passi(
        [passo("control_device", entity_id="light.cucina", action="turn_on"), passo("stato_aperture")],
        FUNZIONI,
        set(),
    )
    assert [p.nome for p in accettati] == ["stato_aperture"] and codici(scarti) == [
        (1, piani.DISPOSITIVO_INESISTENTE)
    ]
