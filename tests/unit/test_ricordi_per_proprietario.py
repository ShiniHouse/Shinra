"""Ognuno vede solo i propri ricordi privati (ADR 0009, scelta del proprietario del 2026-10-14).

Un ricordo della casa lo vede chiunque; uno privato solo il suo proprietario: nemmeno un amministratore legge quelli di un
altro, e un adulto non legge quelli di un minore. Un ricordo solo *proposto* o archiviato non entra mai nel prompt.

Le prove sono tutte dalla parte di chi **non** deve vedere: il testo di un ricordo privato non compare nel prompt, nell'elenco,
nelle rotte, nel grafo, nell'intervista, nei plugin di nessun altro. Ognuna e' provata anche col recupero a molti fatti
(vettori), che e' un percorso diverso da «si mandano tutti».
"""

from __future__ import annotations

import json

import pytest

from shinra.api import routes_conoscenza, routes_impostazioni
from shinra.domain import ricordi
from shinra.infra.data_store import data_store
from shinra.infra.db import depositi
from shinra.services.conoscenza import ServizioConoscenza, servizio_conoscenza
from shinra.services.user_manager import UserProfile

SEGRETO_DI_ALESSIO = "Alessio prende la medicina alle sette"
SEGRETO_DI_MARCO = "Marco ha paura del buio"
DELLA_CASA = "La caldaia e' in cantina"


@pytest.fixture(autouse=True)
def tre_ricordi():
    depositi.fatti.sostituisci_tutto([])
    depositi.fatti.aggiungi({"id": "k_casa", "text": DELLA_CASA, "category": "casa", "enabled": True})
    depositi.fatti.aggiungi(
        {
            "id": "k_alessio",
            "text": SEGRETO_DI_ALESSIO,
            "category": "salute",
            "enabled": True,
            "proprietario": "alessio",
        }
    )
    depositi.fatti.aggiungi(
        {
            "id": "k_marco",
            "text": SEGRETO_DI_MARCO,
            "category": "famiglia",
            "enabled": True,
            "proprietario": "marco",
        }
    )
    yield
    depositi.fatti.sostituisci_tutto([])


# ----------------------------------------------------------------------- il dominio


def test_un_ricordo_della_casa_lo_vedono_tutti_e_senza_profilo_solo_quelli():
    casa = {"id": "k", "text": "x", "proprietario": ""}
    assert (
        ricordi.e_visibile_a(casa, "alessio")
        and ricordi.e_visibile_a(casa, "marco")
        and ricordi.e_visibile_a(casa, "")
    )
    assert ricordi.e_visibile_a({"proprietario": None}, "alessio"), "un proprietario nullo e' la casa"


def test_un_ricordo_privato_lo_vede_solo_il_suo_proprietario():
    mio = {"id": "k", "text": "x", "proprietario": "alessio"}
    assert ricordi.e_visibile_a(mio, "alessio")
    assert not ricordi.e_visibile_a(mio, "marco")
    assert not ricordi.e_visibile_a(mio, ""), "senza profilo non si vede il privato di nessuno"
    assert not ricordi.e_visibile_a(mio, None)


def test_solo_un_ricordo_attivo_e_non_spento_entra_nel_prompt():
    assert ricordi.entra_nel_prompt({"enabled": True, "stato": "attivo"})
    assert ricordi.entra_nel_prompt({"enabled": True}), "senza stato (dati vecchi) vale attivo"
    assert not ricordi.entra_nel_prompt({"enabled": False, "stato": "attivo"})
    assert not ricordi.entra_nel_prompt({"enabled": True, "stato": "proposto"})
    assert not ricordi.entra_nel_prompt({"enabled": True, "stato": "archiviato"})


def test_chi_puo_cambiare_un_ricordo():
    casa = {"proprietario": ""}
    privato = {"proprietario": "alessio"}
    assert ricordi.puo_modificare(casa, "marco", puo_scrivere_la_casa=True)
    assert not ricordi.puo_modificare(casa, "marco", puo_scrivere_la_casa=False)
    assert ricordi.puo_modificare(
        privato, "alessio", puo_scrivere_la_casa=False
    ), "il proprio lo cambia chi lo possiede"
    assert not ricordi.puo_modificare(
        privato, "marco", puo_scrivere_la_casa=True
    ), "nemmeno con il permesso sulla casa"


# ------------------------------------------------------------------ il prompt


async def test_il_prompt_di_alessio_ha_i_suoi_ricordi_e_quelli_della_casa_non_quelli_di_marco():
    testo = (await ServizioConoscenza().recupera("che cosa sai", "alessio")).testo
    assert DELLA_CASA in testo and SEGRETO_DI_ALESSIO in testo
    assert SEGRETO_DI_MARCO not in testo, "il ricordo privato di Marco e' nel prompt di Alessio"


async def test_nemmeno_un_amministratore_legge_il_privato_di_un_altro():
    """L'amministratore e' un profilo come gli altri per la memoria: vede la casa e i propri."""
    depositi.utenti.salva({"id": "admin_x", "name": "Admin", "role": "admin"})
    try:
        testo = (await ServizioConoscenza().recupera("che cosa sai", "admin_x")).testo
        assert DELLA_CASA in testo
        assert SEGRETO_DI_ALESSIO not in testo and SEGRETO_DI_MARCO not in testo
    finally:
        depositi.utenti.cancella("admin_x")


async def test_senza_profilo_o_da_ospite_si_vede_solo_la_casa():
    for chi in ("", "guest"):
        testo = (await ServizioConoscenza().recupera("che cosa sai", chi)).testo
        assert DELLA_CASA in testo and "Alessio" not in testo and "Marco" not in testo, chi


async def test_lo_stesso_vale_col_recupero_a_molti_fatti(monkeypatch):
    """Sopra la soglia il percorso e' un altro (vettori e punteggi): la regola deve valere anche li'."""
    from shinra.infra.llm import embedding

    async def finto(testi):
        return [[1.0, 0.0] for _ in testi]

    monkeypatch.setattr(embedding, "calcola", finto)
    monkeypatch.setattr(embedding, "modello", lambda: "finto")
    for i in range(40):
        depositi.fatti.aggiungi(
            {
                "id": f"k_x{i}",
                "text": f"Il fatto numero {i} riguarda la casa",
                "category": "x",
                "enabled": True,
            }
        )
    servizio = ServizioConoscenza()
    await servizio.aggiorna_indice()

    di_alessio = await servizio.recupera("alessio medicina buio", "alessio")
    di_marco = await servizio.recupera("alessio medicina buio", "marco")

    assert SEGRETO_DI_MARCO not in di_alessio.testo and SEGRETO_DI_ALESSIO not in di_marco.testo
    assert all(SEGRETO_DI_MARCO not in e["estratto"] for e in di_alessio.entrati)
    assert all(SEGRETO_DI_ALESSIO not in e["estratto"] for e in di_marco.entrati)


async def test_un_ricordo_proposto_o_archiviato_non_entra_nel_prompt_di_nessuno():
    depositi.fatti.aggiorna("k_casa", {"stato": "proposto"})
    depositi.fatti.aggiorna("k_alessio", {"stato": "archiviato"})
    testo = (await ServizioConoscenza().recupera("che cosa sai", "alessio")).testo
    assert DELLA_CASA not in testo and SEGRETO_DI_ALESSIO not in testo


async def test_i_ricordi_usati_mostrati_a_chi_ha_chiesto_sono_solo_i_suoi():
    esito = await ServizioConoscenza().recupera("che cosa sai", "marco")
    assert {e["id"] for e in esito.entrati} == {"k_casa", "k_marco"}


# ------------------------------------------------------------------- le rotte


class Finta:
    def __init__(self, id_):
        self.id = id_


@pytest.fixture
def come(monkeypatch):
    corrente = {"u": UserProfile(id="alessio", name="Alessio")}
    monkeypatch.setattr(routes_impostazioni, "utente_corrente", lambda request: corrente["u"])
    monkeypatch.setattr(routes_conoscenza, "utente_corrente", lambda request: corrente["u"])
    return corrente


async def test_l_elenco_dei_ricordi_mostra_la_casa_e_i_propri(come):
    ids = {f["id"] for f in await routes_impostazioni.list_knowledge(None)}
    assert ids == {"k_casa", "k_alessio"}
    come["u"] = UserProfile(id="marco", name="Marco")
    assert {f["id"] for f in await routes_impostazioni.list_knowledge(None)} == {"k_casa", "k_marco"}
    assert SEGRETO_DI_ALESSIO not in json.dumps(await routes_impostazioni.list_knowledge(None))


async def test_non_si_cambia_ne_si_scopre_il_privato_di_un_altro(come):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_impostazioni.save_knowledge({"id": "k_marco", "text": "riscritto"}, None)
    assert errore.value.status_code == 404, "ha confermato che il ricordo di un altro esiste"
    assert depositi.fatti.per_id("k_marco")["text"] == SEGRETO_DI_MARCO


async def test_non_si_scrive_un_ricordo_privato_a_nome_di_un_altro(come):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_impostazioni.save_knowledge(
            {"id": "k_nuovo", "text": "x", "proprietario": "marco"}, None
        )
    assert errore.value.status_code == 403 and depositi.fatti.per_id("k_nuovo") is None


async def test_il_proprietario_di_un_ricordo_non_si_cambia(come):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as errore:
        await routes_impostazioni.save_knowledge({"id": "k_alessio", "text": "x", "proprietario": ""}, None)
    assert errore.value.status_code == 403
    assert (
        depositi.fatti.per_id("k_alessio")["proprietario"] == "alessio"
    ), "un privato e' diventato della casa"


async def test_si_scrive_il_proprio_ricordo_privato_e_uno_della_casa(come):
    mio = await routes_impostazioni.save_knowledge(
        {"id": "k_mio", "text": "Mi piace il te'", "proprietario": "alessio"}, None
    )
    assert mio["item"]["proprietario"] == "alessio"
    casa = await routes_impostazioni.save_knowledge({"id": "k_casa2", "text": "Il bagno e' a destra"}, None)
    assert casa["item"]["proprietario"] == ""


async def test_non_si_cancella_il_privato_di_un_altro_e_si_cancella_il_proprio(come):
    assert (await routes_impostazioni.delete_knowledge("k_marco", None)) == {"success": False}
    assert depositi.fatti.per_id("k_marco") is not None
    assert (await routes_impostazioni.delete_knowledge("k_alessio", None)) == {"success": True}
    assert depositi.fatti.per_id("k_alessio") is None


async def test_i_fatti_usati_di_debug_sono_quelli_di_chi_guarda(come):
    await servizio_conoscenza.per_la_domanda("che cosa sai", "marco")
    await servizio_conoscenza.per_la_domanda("che cosa sai", "alessio")
    # (sotto la soglia il recupero non sceglie: l'elenco e' vuoto per tutti, ma per profilo e senza scambi)
    assert (
        routes_conoscenza.servizio_conoscenza.fatti_usati("marco")
        == servizio_conoscenza.ultimo_recupero["marco"]
    )
    esito = await routes_conoscenza.fatti_usati(None)
    assert esito["fatti"] == servizio_conoscenza.ultimo_recupero["alessio"]


# ------------------------------------------------- grafo, intervista, plugin


async def test_il_grafo_del_cervello_non_ha_un_nodo_per_un_ricordo_privato(monkeypatch):
    from shinra.services import cervello as servizio

    visti: list = []

    async def modello_finto():
        return {"id": "modello", "nome": "x", "stato": "online"}

    monkeypatch.setattr(servizio, "_stato_del_modello", modello_finto)
    originale = servizio.dominio.costruisci

    def costruisci(**kwargs):
        visti.extend(kwargs["fatti"])
        return originale(**kwargs)

    monkeypatch.setattr(servizio.dominio, "costruisci", costruisci)
    try:
        grafo = await servizio.genera(UserProfile(id="alessio", name="Alessio", role="admin"))
    except Exception:  # il grafo intero dipende da altro: qui conta cio' che riceve
        grafo = {}
    assert [f["id"] for f in visti] == ["k_casa"], "un ricordo privato e' arrivato al grafo"
    assert "k_alessio" not in json.dumps(grafo, default=str) and "k_marco" not in json.dumps(
        grafo, default=str
    )


async def test_l_intervista_non_conosce_i_ricordi_privati_di_nessuno():
    from shinra.services import intervista_noto

    dati = intervista_noto.dati_della_casa(data_store)
    assert [f["id"] for f in dati["fatti"]] == ["k_casa"]
    assert SEGRETO_DI_ALESSIO not in json.dumps(dati, default=str)


def test_un_plugin_legge_solo_i_ricordi_della_casa():
    from shinra.services.plugin import Contesto, Manifesto, Permessi

    manifesto = Manifesto(
        nome="prova",
        versione="1",
        descrizione="x",
        permessi=Permessi(conoscenza=True),
        strumenti=[],
        parole=[],
    )
    letti = Contesto(manifesto).conoscenza()
    assert letti == [DELLA_CASA]


# ----------------------------------------------------------- il conteggio degli usi (#247)


async def test_il_conteggio_degli_usi_cresce_di_uno_per_risposta_e_solo_per_chi_e_entrato(monkeypatch):
    from shinra.services.agent import ShinraAgent

    async def chat(self, messages, tools=None, temperature=None, **k):
        return {"success": True, "message": {"content": "Ecco.", "tool_calls": []}}

    monkeypatch.setattr("shinra.infra.llm.ollama.OllamaClient.chat", chat)
    depositi.utenti.salva({"id": "alessio", "name": "Alessio", "role": "adult"})
    try:
        agente = ShinraAgent()
        profilo = UserProfile(id="alessio", name="Alessio")
        await agente.process_user_input(
            "racconta tutto quello che sai di me e della casa", user_profile=profilo
        )

        casa = depositi.fatti.per_id("k_casa")
        mio = depositi.fatti.per_id("k_alessio")
        di_marco = depositi.fatti.per_id("k_marco")
        assert (casa["usi"], mio["usi"]) == (1, 1), "ogni ricordo entrato conta una volta per risposta"
        assert casa["ultimo_uso"] is not None and mio["ultimo_uso"] is not None
        assert (di_marco["usi"], di_marco["ultimo_uso"]) == (
            0,
            None,
        ), "ha contato un ricordo che non e' entrato"

        await agente.process_user_input("e adesso cosa ricordi di me e della casa", user_profile=profilo)
        assert depositi.fatti.per_id("k_casa")["usi"] == 2
    finally:
        depositi.utenti.cancella("alessio")


def test_segna_usati_ignora_il_vuoto_e_un_id_che_non_c_e_non_rompe_niente():
    assert servizio_conoscenza.segna_usati([]) == 0
    servizio_conoscenza.segna_usati(["k_che_non_esiste"])  # nessuna eccezione
    assert depositi.fatti.per_id("k_casa")["usi"] == 0
