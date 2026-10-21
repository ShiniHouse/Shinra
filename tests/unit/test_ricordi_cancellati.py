"""Un ricordo cancellato non torna con un ripristino vecchio (ADR 0009, punto 6).

Il caso: si fa un salvataggio, poi si cancella un ricordo («dimentica»), poi si ripristina quel salvataggio. Senza una memoria di
cio' che e' stato cancellato, il ricordo rientra in casa — e chi aveva chiesto di dimenticarlo se lo ritrova.
"""

from __future__ import annotations

import json

import pytest

from shinra.infra.data_store import DataStore
from shinra.infra.db import depositi, lapidi
from shinra.services import salvataggio


@pytest.fixture()
def casa():
    depositi.fatti.sostituisci_tutto(
        [
            {"id": "k_tiene", "text": "Il cane si chiama Kira", "category": "famiglia", "enabled": True},
            {"id": "k_via", "text": "La caldaia e' in cantina", "category": "casa", "enabled": True},
        ]
    )
    return DataStore()


def _archivio_adesso(tmp_path):
    percorso = tmp_path / "vecchio.json"
    salvataggio.scrivi(percorso)
    return salvataggio.leggi(percorso)


def test_cancellare_un_ricordo_ne_ricorda_solo_l_identificativo(casa):
    assert casa.cancella_fatto("k_via") is True
    assert lapidi.cancellati() == {"k_via"}
    # Mai il testo: la tabella ha solo id e momento.
    from shinra.infra.db.modelli_ricordi import RicordoCancellato

    assert set(RicordoCancellato.__table__.columns.keys()) == {"id", "cancellato_il"}


def test_cancellare_due_volte_o_un_inesistente_non_fa_danni(casa):
    assert casa.cancella_fatto("k_via") is True
    assert casa.cancella_fatto("k_via") is False
    assert casa.cancella_fatto("non_c_e") is False
    assert lapidi.cancellati() == {"k_via"}


def test_un_ripristino_vecchio_non_riporta_il_ricordo_cancellato(casa, tmp_path):
    vecchio = _archivio_adesso(tmp_path)  # contiene entrambi
    assert {r["id"] for r in vecchio["tabelle"]["knowledge"]} == {"k_tiene", "k_via"}

    casa.cancella_fatto("k_via")
    salvataggio.ripristina(vecchio)

    assert {r["id"] for r in depositi.fatti.elenco()} == {"k_tiene"}


def test_l_anteprima_dice_quanti_ricordi_non_rientrano(casa, tmp_path):
    vecchio = _archivio_adesso(tmp_path)
    assert salvataggio.anteprima(vecchio)["knowledge"]["da_non_rimettere"] == 0
    casa.cancella_fatto("k_via")
    quadro = salvataggio.anteprima(vecchio)["knowledge"]
    assert quadro["da_non_rimettere"] == 1 and quadro["nell_archivio"] == 2


def test_un_ripristino_senza_cancellazioni_rimette_tutto(casa, tmp_path):
    vecchio = _archivio_adesso(tmp_path)
    depositi.fatti.sostituisci_tutto([])
    salvataggio.ripristina(vecchio)
    assert {r["id"] for r in depositi.fatti.elenco()} == {"k_tiene", "k_via"}


def test_la_lista_dei_cancellati_non_esce_nel_salvataggio(casa, tmp_path):
    """Non e' nell'archivio: sta nel database vivo, e un ripristino la usa senza portarla in giro."""
    casa.cancella_fatto("k_via")
    testo = json.dumps(_archivio_adesso(tmp_path))
    assert "ricordi_cancellati" not in testo and "k_via" not in testo


def test_dimenticare_tutto_di_se_segna_tutti_i_ricordi_privati(casa):
    from shinra.services import ricordi

    class Profilo:
        id = "alessio"

    privato = casa.salva_fatto(
        {"text": "Prendo una pillola la sera", "category": "salute", "proprietario": "alessio"}
    )
    assert ricordi.dimentica_tutto_di_me(Profilo()) >= 1
    assert privato["id"] in lapidi.cancellati()
