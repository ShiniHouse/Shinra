"""Dimenticare lascia davvero niente (#253, seconda parte): proposte, riassunti, vettori e backup.

Un ricordo non vive in un posto solo. Dopo «elimina» o «dimentica tutto di me» una scansione di tutte le tabelle non trova piu' il
testo, le proposte del sogno che lo citavano sono sparite, e un backup fatto dopo non lo contiene. I backup fatti **prima** non
vengono riscritti: e' un limite dichiarato nella guida, non un difetto.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from shinra.infra.data_store import data_store
from shinra.infra.db import depositi
from shinra.infra.db.proposte import proposte
from shinra.infra.db.riassunti import riassunti
from shinra.services import ricordi, salvataggio
from shinra.services.user_manager import UserProfile
from tests.unit.test_cancellare_un_ricordo import _in_tutto_il_database

ALESSIO = UserProfile(id="alessio", name="Alessio", role="admin")
SEGRETO = "ZEBRA-4417-cassaforte"
ORA = datetime(2026, 10, 20, 3, 0)


@pytest.fixture(autouse=True)
def pulito():
    depositi.fatti.sostituisci_tutto([])
    for chi in ("alessio", "sonia"):
        proposte.dimentica_profilo(chi)
        riassunti.dimentica_profilo(chi)
    yield
    depositi.fatti.sostituisci_tutto([])
    for chi in ("alessio", "sonia"):
        proposte.dimentica_profilo(chi)
        riassunti.dimentica_profilo(chi)


def _ricordo(id_, testo, chi="alessio"):
    depositi.fatti.aggiungi({"id": id_, "text": testo, "category": "x", "enabled": True, "proprietario": chi})
    depositi.embedding.salva(id_, [0.1, 0.2], "m", "i")


def _proposta(chi, chiave, dati):
    return proposte.proponi(chi, "ricordo_doppio", chiave, dati, ORA, ORA + timedelta(days=14))


def test_cancellare_un_ricordo_toglie_le_proposte_che_lo_citano():
    _ricordo("k1", f"Il codice {SEGRETO} sta nel cassetto")
    _ricordo("k2", f"Il codice {SEGRETO} e' nel cassetto")
    _ricordo("k3", "Un ricordo che non c'entra niente con gli altri")
    citante = _proposta("alessio", "a", {"ids": ["k1", "k2"]})
    estranea = _proposta("alessio", "b", {"ids": ["k3", "k9"]})

    assert ricordi.cancella(ALESSIO, "k1")

    assert proposte.trova(citante["id"]) is None, "la proposta che indicava il ricordo cancellato e' rimasta"
    assert proposte.trova(estranea["id"]) is not None, "una proposta che non lo citava non si tocca"


def test_dimentica_tutto_di_me_toglie_ricordi_riassunti_proposte_e_vettori():
    _ricordo("k1", f"Il codice {SEGRETO} sta nel cassetto")
    riassunti.aggiungi("alessio", f"Hai chiesto: «il codice {SEGRETO}».", 1, ORA, ORA + timedelta(days=30))
    _proposta("alessio", "a", {"ids": ["k1", "k2"], "nota": SEGRETO})
    assert _in_tutto_il_database(SEGRETO), "la scansione non vede niente: la prova non prova"

    ricordi.dimentica_tutto_di_me(ALESSIO)

    assert _in_tutto_il_database(SEGRETO) == []
    assert "k1" not in depositi.embedding.tutti(), "il vettore e' rimasto"
    assert proposte.del_profilo("alessio") == []


def test_dimenticare_me_non_tocca_le_cose_di_un_altro():
    _ricordo("s1", "Sonia ama il te verde", chi="sonia")
    riassunti.aggiungi("sonia", "Hai chiesto: «la luce».", 1, ORA, ORA + timedelta(days=30))
    _proposta("sonia", "s", {"ids": ["s1", "s2"]})
    _ricordo("k1", "Un ricordo di Alessio da dimenticare")

    ricordi.dimentica_tutto_di_me(ALESSIO)

    assert depositi.fatti.per_id("s1") is not None
    assert riassunti.del_profilo("sonia")
    assert proposte.del_profilo("sonia")


def test_il_registro_dice_quante_proposte_non_quali():
    from shinra.services import registro

    _ricordo("k1", f"Il codice {SEGRETO}")
    _proposta("alessio", "a", {"ids": ["k8", "k9"]})  # non cita k1: resta finche' non si dimentica tutto
    ricordi.dimentica_tutto_di_me(ALESSIO)
    voce = registro.voci(limite=1)[0]
    assert voce["azione"] == "ricordi.dimenticati" and voce["dettagli"]["proposte"] == 1
    assert SEGRETO not in json.dumps(voce, default=str)


def test_un_backup_fatto_dopo_non_contiene_piu_il_testo_e_uno_prima_si():
    _ricordo("k1", f"Il codice {SEGRETO} sta nel cassetto")
    prima = json.dumps(salvataggio.esporta(), default=str, ensure_ascii=False)
    assert SEGRETO in prima, "il backup non vede nemmeno il ricordo vivo: la prova non prova"

    data_store.cancella_fatto("k1")

    dopo = json.dumps(salvataggio.esporta(), default=str, ensure_ascii=False)
    assert SEGRETO not in dopo
    assert SEGRETO in prima, "i backup gia' fatti restano com'erano: lo dice la guida"
