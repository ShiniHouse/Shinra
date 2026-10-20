"""I ricordi hanno un luogo (#345): un fatto della casa al mare non finisce fra quelli della casa principale.

La regola: un ricordo senza luogo vale ovunque; uno legato a un luogo entra nel prompt solo quando si parla di quel luogo
(nominato nella frase, dove si trova chi parla, la casa principale). Se non si sa di quale luogo si parla, un ricordo legato a un
luogo non entra. Cancellare un luogo archivia i suoi ricordi: non diventano ricordi «di ovunque».
"""

from __future__ import annotations

import pytest

from shinra.domain import ricordi as regole
from shinra.infra.db import depositi
from shinra.infra.db.luoghi import luoghi as deposito
from shinra.services import luoghi, permessi, posizione, registro, ricordi
from shinra.services.conoscenza import ServizioConoscenza
from shinra.services.user_manager import UserProfile

ALESSIO = UserProfile(id="alessio", name="Alessio", role="admin")
CASA = (41.902784, 12.496366)
MARE = (44.123456, 12.234567)


@pytest.fixture(autouse=True)
def archivio():
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    deposito.sostituisci_tutto([])
    depositi.fatti.sostituisci_tutto([])
    casa = luoghi.registra(
        {"nome": "Casa", "latitudine": CASA[0], "longitudine": CASA[1], "origine": "telefono"}
    )
    mare = luoghi.registra(
        {"nome": "Casa al mare", "latitudine": MARE[0], "longitudine": MARE[1], "origine": "telefono"}
    )
    yield {"casa": casa["id"], "mare": mare["id"]}
    deposito.sostituisci_tutto([])
    depositi.fatti.sostituisci_tutto([])


def fatto(id_, testo, luogo="", chi=""):
    depositi.fatti.aggiungi(
        {"id": id_, "text": testo, "category": "x", "enabled": True, "proprietario": chi, "luogo_id": luogo}
    )


# ------------------------------------------------------------------ la regola


def test_un_ricordo_senza_luogo_vale_ovunque():
    assert regole.vale_per_il_luogo({"luogo_id": ""}, "L1") and regole.vale_per_il_luogo({}, "")


def test_un_ricordo_di_un_luogo_vale_solo_per_quel_luogo():
    assert regole.vale_per_il_luogo({"luogo_id": "L1"}, "L1")
    assert not regole.vale_per_il_luogo({"luogo_id": "L1"}, "L2")


def test_se_non_si_sa_di_che_luogo_si_parla_un_ricordo_di_luogo_non_entra():
    assert not regole.vale_per_il_luogo({"luogo_id": "L1"}, "")


# ------------------------------------------------------------------ il prompt


async def test_un_fatto_della_casa_al_mare_non_compare_parlando_della_casa_principale(archivio):
    fatto("k_c", "La caldaia della casa e' in cantina")
    fatto("k_m", "Le chiavi della casa al mare sono sotto il vaso", luogo=archivio["mare"])
    s = ServizioConoscenza()
    della_casa = await s.recupera("dove sono le chiavi", "alessio", archivio["casa"])
    del_mare = await s.recupera("dove sono le chiavi", "alessio", archivio["mare"])
    assert "sotto il vaso" not in della_casa.testo and "caldaia" in della_casa.testo
    assert (
        "sotto il vaso" in del_mare.testo and "caldaia" in del_mare.testo
    ), "i ricordi senza luogo valgono ovunque"
    assert [r["id"] for r in della_casa.entrati] == ["k_c"]


async def test_senza_un_luogo_del_discorso_i_ricordi_di_luogo_restano_fuori(archivio):
    fatto("k_m", "Le chiavi della casa al mare sono sotto il vaso", luogo=archivio["mare"])
    assert (await ServizioConoscenza().recupera("chiavi", "alessio", "")).entrati == []


def test_il_luogo_del_discorso_e_il_nominato_poi_dove_sei_poi_la_principale(archivio):
    assert posizione.luogo_del_discorso("com'e' la casa al mare", None)["id"] == archivio["mare"]
    assert (
        posizione.luogo_del_discorso("che fai", None)["id"] == archivio["casa"]
    ), "la casa principale e' il ripiego"


async def test_l_agente_sceglie_il_luogo_del_discorso(archivio):
    from shinra.services.agent import ShinraAgent

    assert ShinraAgent._luogo_del_discorso("com'e' la casa al mare", None) == archivio["mare"]
    assert ShinraAgent._luogo_del_discorso("che fai", None) == archivio["casa"]
    deposito.sostituisci_tutto([])
    assert ShinraAgent._luogo_del_discorso("che fai", None) == "", "senza luoghi registrati non c'e' un luogo"


# ------------------------------------------------------------------ scrivere e correggere


def test_si_scrive_un_ricordo_con_un_luogo_e_se_ne_mostra_il_nome_non_le_coordinate(archivio):
    r = ricordi.crea(ALESSIO, "Le chiavi sono sotto il vaso", ambito="mio", luogo_id=archivio["mare"])
    assert r["luogo_id"] == archivio["mare"] and r["luogo"] == "Casa al mare"
    assert "44.12" not in str(r)


def test_un_luogo_inventato_e_un_errore(archivio):
    with pytest.raises(ricordi.DatoNonValido):
        ricordi.crea(ALESSIO, "Un ricordo", luogo_id="l_inventato")
    assert depositi.fatti.elenco() == []


def test_si_cambia_e_si_toglie_il_luogo_di_un_ricordo(archivio):
    r = ricordi.crea(ALESSIO, "Le chiavi sono sotto il vaso")
    assert r["luogo_id"] == ""
    assert ricordi.modifica(ALESSIO, r["id"], {"luogo_id": archivio["mare"]})["luogo"] == "Casa al mare"
    assert ricordi.modifica(ALESSIO, r["id"], {"luogo_id": ""})["luogo_id"] == ""
    with pytest.raises(ricordi.DatoNonValido):
        ricordi.modifica(ALESSIO, r["id"], {"luogo_id": "l_inventato"})


# ------------------------------------------------------------------ cancellare un luogo


async def test_cancellare_un_luogo_archivia_i_suoi_ricordi_e_non_li_rende_di_ovunque(archivio):
    fatto("k_m", "Le chiavi della casa al mare sono sotto il vaso", luogo=archivio["mare"])
    fatto("k_c", "La caldaia della casa e' in cantina")

    assert luoghi.cancella(archivio["mare"])

    assert (
        depositi.fatti.per_id("k_m")["stato"] == "archiviato"
    ), "il ricordo del luogo cancellato e' ancora attivo"
    assert depositi.fatti.per_id("k_m")["text"] == "Le chiavi della casa al mare sono sotto il vaso"
    assert depositi.fatti.per_id("k_c")["stato"] == "attivo"
    nuovo = await ServizioConoscenza().recupera("chiavi", "alessio", archivio["casa"])
    assert "vaso" not in nuovo.testo


def test_il_registro_dice_quanti_ricordi_ha_archiviato_non_quali(archivio):
    fatto("k_m", "Le chiavi della casa al mare sono sotto il vaso", luogo=archivio["mare"])
    luoghi.cancella(archivio["mare"])
    voce = registro.voci(limite=1)[0]
    assert voce["azione"] == "luogo.cancellato" and voce["dettagli"]["ricordi_archiviati"] == 1
    assert "vaso" not in str(voce)


async def test_l_agente_chiede_il_recupero_per_il_luogo_del_discorso(archivio, monkeypatch):
    """Non basta che la funzione esista: la richiesta del modello deve arrivare al recupero con il luogo giusto."""
    from shinra.services.agent import ShinraAgent
    from shinra.services.conoscenza import Recuperati, servizio_conoscenza

    viste: list[str] = []

    async def recupera(domanda, profilo_id="", luogo_id=""):
        viste.append(luogo_id)
        return Recuperati("", [], [])

    async def chat(self, messages, tools=None, temperature=None, **k):
        return {"success": True, "message": {"content": "Ok.", "tool_calls": []}}

    monkeypatch.setattr(servizio_conoscenza, "recupera", recupera)
    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)

    await ShinraAgent().process_user_input("racconta una storia sulla casa al mare")
    await ShinraAgent().process_user_input("racconta una storia lunga e senza luoghi")

    assert viste == [archivio["mare"], archivio["casa"]]
