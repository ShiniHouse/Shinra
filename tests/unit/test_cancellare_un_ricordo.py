"""Cancellare un ricordo lo cancella davvero, dappertutto (#253, prima parte).

Un ricordo non vive in un posto solo: ha un vettore, e la voce di registro che dice che e' stato cancellato non deve
riportarlo. «Dimentica» che lascia copie e' peggio di niente, perche' fa credere il contrario.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from shinra.api import routes_impostazioni
from shinra.infra.data_store import data_store
from shinra.infra.db import depositi
from shinra.infra.db.motore import sessione
from shinra.infra.db.vettori_in_cache import vettori_in_cache
from shinra.services import registro

SEGRETO = "Il codice della cassaforte e' 7391-ZEBRA"


def _in_tutto_il_database(cercato: str) -> list[str]:
    """Le tabelle in cui compare `cercato`, scandendo ogni colonna di ogni tabella."""
    trovate = []
    with sessione() as s:
        tabelle = [r[0] for r in s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all()]
        for tabella in tabelle:
            colonne = [r[1] for r in s.execute(text(f'PRAGMA table_info("{tabella}")')).all()]
            for colonna in colonne:
                # nomi di tabella e di colonna letti dal database stesso, non da un utente
                interrogazione = (
                    f'SELECT COUNT(*) FROM "{tabella}" WHERE CAST("{colonna}" AS TEXT) LIKE :q'  # noqa: S608
                )
                n = s.execute(text(interrogazione), {"q": f"%{cercato}%"}).scalar()
                if n:
                    trovate.append(f"{tabella}.{colonna}")
    return trovate


def _ricordo_con_vettore() -> str:
    fatto = data_store.add_knowledge_item(SEGRETO, "casa")
    depositi.embedding.salva(fatto["id"], [0.1, 0.2, 0.3], "m", "impronta")
    return str(fatto["id"])


def test_cancellare_un_ricordo_cancella_anche_il_suo_vettore():
    identificativo = _ricordo_con_vettore()
    assert identificativo in depositi.embedding.tutti()

    assert data_store.cancella_fatto(identificativo) is True

    assert identificativo not in depositi.embedding.tutti(), "il vettore e' rimasto dopo «dimentica»"
    assert identificativo not in vettori_in_cache.tutti(), "la cache ha ancora il vettore"


def test_dopo_la_cancellazione_il_testo_non_compare_in_nessuna_tabella():
    identificativo = _ricordo_con_vettore()
    assert _in_tutto_il_database(
        "7391-ZEBRA"
    ), "la scansione non vede nemmeno il ricordo vivo: la prova non prova"

    data_store.cancella_fatto(identificativo)

    assert _in_tutto_il_database("7391-ZEBRA") == []


async def test_la_rotta_scrive_nel_registro_che_e_avvenuto_non_cosa():
    identificativo = _ricordo_con_vettore()

    esito = await routes_impostazioni.delete_knowledge(identificativo)

    assert esito == {"success": True}
    voci = registro.voci(azione="ricordo.cancellato")
    assert voci and voci[0]["dettagli"] == {"id": identificativo}
    assert "7391" not in json.dumps(
        voci, default=str
    ), "il registro riporta il contenuto del ricordo cancellato"
    assert _in_tutto_il_database("7391-ZEBRA") == [], "il registro ha riportato il testo nel database"


async def test_cancellare_un_ricordo_che_non_c_e_non_scrive_nel_registro():
    prima = len(registro.voci(azione="ricordo.cancellato"))
    esito = await routes_impostazioni.delete_knowledge("k_inesistente")
    assert esito == {"success": False}
    assert len(registro.voci(azione="ricordo.cancellato")) == prima
