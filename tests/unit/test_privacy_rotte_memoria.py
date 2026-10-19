"""La privacy della memoria, su tutte le rotte (#270): un profilo non legge, non cambia e non cancella le cose di un altro.

Non e' un test di comportamento di una rotta: e' una guardia sull'insieme. Due persone entrano davvero (sessione, cookie, PIN), una
ha un ricordo privato, un riassunto, una proposta del sogno e delle azioni nel registro, tutti con un segno riconoscibile; l'altra
chiede **ogni** rotta della memoria e il segno non deve comparire da nessuna parte. Per gli identificativi si prova a leggere,
cambiare e cancellare quello altrui: sempre «non trovato», come se non esistesse.

Due difese contro la dimenticanza:
- **elenco chiuso**: ogni rotta sotto un prefisso della memoria deve essere dichiarata qui; una rotta nuova fa fallire il test
  finche' qualcuno non decide come provarla;
- **prova della prova**: il proprietario, con le stesse richieste, vede il segno. Se non lo vedesse, la guardia sarebbe cieca.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from shinra.api import sicurezza
from shinra.api.app import app
from shinra.config.settings import settings
from shinra.infra.db import depositi
from shinra.infra.db.proposte import proposte
from shinra.infra.db.riassunti import riassunti
from shinra.services import permessi
from shinra.services.user_manager import UserProfile, user_manager

PIN_DI_PROVA = "482913"
SEGNO = "ZEBRA-ARANCIONE-9931"
ORA = datetime(2026, 10, 20, 3, 0)

PREFISSI = (
    "/api/ricordi",
    "/api/sogno",
    "/api/knowledge",
    "/api/conoscenza",
    "/api/cervello",
    "/api/registro",
)

# Ogni rotta della memoria, dichiarata. LETTURE: si chiedono come l'altro e il segno non deve comparire. PER_ID: si prova su un
# identificativo altrui (e deve rispondere «non trovato»). ALTRE: non portano contenuto altrui, con il perche'.
LETTURE = [
    "/api/ricordi",
    "/api/ricordi/miei",
    "/api/knowledge",
    "/api/conoscenza/fatti-usati",
    "/api/conoscenza/stato",
    "/api/sogno/proposte",
    "/api/cervello",
]
PER_ID = [
    ("PATCH", "/api/ricordi/{ricordo}", {"text": "sovrascritto"}),
    ("DELETE", "/api/ricordi/{ricordo}", None),
    (
        "DELETE",
        "/api/knowledge/{ricordo}",
        None,
    ),  # risponde 200 {"success": false}, uguale a un id inesistente
    ("POST", "/api/sogno/proposte/{proposta}/scarta", None),
    ("POST", "/api/sogno/proposte/{proposta}/accetta", {"tieni": "k_altrui"}),
]
ALTRE = {
    ("POST", "/api/ricordi"): "scrive un ricordo di chi chiede, non legge quelli altrui",
    (
        "POST",
        "/api/ricordi/dimentica-tutto-di-me",
    ): "agisce solo sui ricordi di chi chiede (provata in test_api_dei_ricordi)",
    (
        "POST",
        "/api/knowledge",
    ): "scrive di chi chiede; il permesso e la proprieta' sono controllati dal servizio",
    ("POST", "/api/conoscenza/reindicizza"): "non restituisce contenuto: ricalcola l'indice",
}


@pytest.fixture
def due_persone():
    """Due persone che entrano davvero: Alessio (amministratore) e Sonia (adulta)."""
    for ruolo in permessi.RUOLI_PREDEFINITI:
        depositi.ruoli.salva(dict(ruolo))
    esistenti = user_manager.get_users()
    era_attiva = settings.security.auth_enabled
    settings.security.auth_enabled = True
    alessio = UserProfile(id="alessio", name="Alessio", role="admin")
    sonia = UserProfile(id="sonia", name="Sonia", role="adult")
    depositi.utenti.sostituisci_tutto([alessio.model_dump(), sonia.model_dump()])
    user_manager.imposta_pin("alessio", PIN_DI_PROVA)
    user_manager.imposta_pin("sonia", PIN_DI_PROVA)
    sicurezza.azzera_stato()

    depositi.fatti.sostituisci_tutto([])
    depositi.fatti.aggiungi(
        {
            "id": "k_sonia",
            "text": f"Il codice {SEGNO} e' nel cassetto",
            "category": "privato",
            "enabled": True,
            "proprietario": "sonia",
        }
    )
    depositi.fatti.aggiungi(
        {
            "id": "k_sonia2",
            "text": f"Il codice {SEGNO} sta nel cassetto",
            "category": "privato",
            "enabled": True,
            "proprietario": "sonia",
        }
    )
    depositi.fatti.aggiungi(
        {"id": "k_casa", "text": "La caldaia e' in cantina", "category": "casa", "enabled": True}
    )
    riassunti.aggiungi("sonia", f"Hai chiesto: «{SEGNO}».", 1, ORA, ORA + timedelta(days=30))
    p = proposte.proponi(
        "sonia",
        "ricordo_doppio",
        "c",
        {"ids": ["k_sonia", "k_sonia2"], "nota": SEGNO},
        ORA,
        ORA + timedelta(days=14),
    )

    with TestClient(app) as per_alessio, TestClient(app) as per_sonia:
        for cliente, chi in ((per_alessio, "alessio"), (per_sonia, "sonia")):
            entrato = cliente.post("/api/auth/login", json={"pin": PIN_DI_PROVA, "user_id": chi})
            assert entrato.status_code == 200, entrato.text
        yield per_alessio, per_sonia, p["id"]

    depositi.utenti.sostituisci_tutto([u.model_dump() for u in esistenti])
    depositi.fatti.sostituisci_tutto([])
    proposte.dimentica_profilo("sonia")
    riassunti.dimentica_profilo("sonia")
    settings.security.auth_enabled = era_attiva
    sicurezza.azzera_stato()


def _tutte_le_rotte() -> list:
    """Tutte le rotte, scendendo dentro i router inclusi (FastAPI li conserva annidati, in `original_router`)."""
    trovate: list = []
    visti: set = set()

    def scendi(contenitore) -> None:
        if id(contenitore) in visti:
            return
        visti.add(id(contenitore))
        for r in getattr(contenitore, "routes", []) or []:
            if isinstance(r, APIRoute):
                trovate.append(r)
                continue
            interno = getattr(r, "original_router", None)
            if interno is not None:
                scendi(interno)
            elif hasattr(r, "routes"):
                scendi(r)
        annidato = getattr(contenitore, "router", None)
        if annidato is not None and annidato is not contenitore:
            scendi(annidato)

    scendi(app)
    return trovate


def _rotte_della_memoria() -> set:
    return {
        (metodo, r.path)
        for r in _tutte_le_rotte()
        if r.path.startswith(PREFISSI)
        for metodo in r.methods
        if metodo != "HEAD"
    }


def _senza_nomi(percorso: str) -> str:
    return re.sub(r"\{[^}]*\}", "{id}", percorso)


def test_ogni_rotta_della_memoria_e_dichiarata():
    dichiarate = (
        {("GET", p) for p in LETTURE}
        | {(m, _senza_nomi(p)) for m, p, _ in PER_ID}
        | {(m, _senza_nomi(p)) for m, p in ALTRE}
        | {
            ("GET", "/api/registro"),
            ("GET", "/api/registro/azioni"),
        }  # provate sotto: nel registro non c'e' testo di ricordi
    )
    esistenti = {(m, _senza_nomi(p)) for m, p in _rotte_della_memoria()}
    nuove = esistenti - dichiarate
    scomparse = dichiarate - esistenti
    assert nuove == set(), f"rotte della memoria non dichiarate in questa guardia: {sorted(nuove)}"
    assert scomparse == set(), f"rotte dichiarate che non esistono piu': {sorted(scomparse)}"


@pytest.mark.parametrize("percorso", LETTURE)
def test_chi_non_e_il_proprietario_non_vede_il_segno(due_persone, percorso):
    alessio, _, _ = due_persone
    r = alessio.get(percorso)
    assert r.status_code == 200, f"{percorso}: {r.status_code} {r.text[:200]}"
    assert SEGNO not in json.dumps(
        r.json(), ensure_ascii=False
    ), f"{percorso} fa vedere a Alessio una cosa di Sonia"


def test_prova_della_prova_il_proprietario_vede_il_segno(due_persone):
    _, sonia, _ = due_persone
    visto = {
        p
        for p in ("/api/ricordi", "/api/ricordi/miei", "/api/sogno/proposte", "/api/registro")
        if SEGNO in sonia.get(p).text
    }
    assert (
        "/api/ricordi" in visto and "/api/ricordi/miei" in visto
    ), f"il segno non si vede nemmeno dal proprietario: {visto}"
    assert (
        "/api/sogno/proposte" in visto
    ), "la proposta di Sonia non si vede a Sonia: la guardia non prova niente"


@pytest.mark.parametrize("metodo,modello,corpo", PER_ID, ids=lambda x: x if isinstance(x, str) else "")
def test_un_identificativo_altrui_non_si_legge_non_si_cambia_non_si_cancella(
    due_persone, metodo, modello, corpo
):
    alessio, _, id_proposta = due_persone
    percorso = modello.format(ricordo="k_sonia", proposta=id_proposta)
    r = alessio.request(metodo, percorso, json=corpo)
    if percorso.startswith("/api/knowledge/"):
        # La rotta storica non usa il 404: dice «non fatto», lo stesso che per un id che non esiste. L'importante e' che sia uguale.
        inesistente = alessio.request(metodo, percorso.replace("k_sonia", "k_non_esiste"), json=corpo)
        assert (
            (r.status_code, r.json())
            == (inesistente.status_code, inesistente.json())
            == (200, {"success": False})
        )
    else:
        assert r.status_code == 404, f"{metodo} {percorso}: {r.status_code} {r.text[:200]}"
    # E non e' successo niente.
    assert depositi.fatti.per_id("k_sonia")["text"] == f"Il codice {SEGNO} e' nel cassetto"
    assert proposte.trova(id_proposta)["stato"] == "nuova"


def test_il_registro_dice_che_e_successo_non_il_testo_di_un_ricordo(due_persone):
    alessio, sonia, _ = due_persone
    creato = sonia.post("/api/ricordi", json={"testo": f"Nuovo segreto {SEGNO}-B", "ambito": "mio"})
    assert creato.status_code == 200, creato.text
    identificativo = creato.json()["ricordo"]["id"]
    assert (
        sonia.patch(f"/api/ricordi/{identificativo}", json={"text": f"Corretto {SEGNO}-C"}).status_code == 200
    )
    assert sonia.delete(f"/api/ricordi/{identificativo}").status_code == 200
    for chi, cliente in (("alessio", alessio), ("sonia", sonia)):
        for percorso in ("/api/registro", "/api/registro/azioni"):
            testo = cliente.get(percorso).text
            assert SEGNO not in testo, f"{percorso} ({chi}) riporta il testo di un ricordo"
    azioni = (
        {v["azione"] for v in alessio.get("/api/registro").json()["voci"]}
        if "voci" in alessio.get("/api/registro").json()
        else set()
    )
    assert azioni == set() or any(
        a.startswith("ricordo.") for a in azioni
    ), "il registro non dice nemmeno che e' successo"


def test_l_amministratore_non_e_un_caso_speciale(due_persone):
    alessio, _, _ = due_persone
    tutto = json.dumps([alessio.get(p).json() for p in LETTURE], ensure_ascii=False)
    assert SEGNO not in tutto
