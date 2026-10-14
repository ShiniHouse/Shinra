"""Un ricordo ha un proprietario, un'origine, un'importanza e una storia (#245).

Le prove che contano: la migrazione sale e scende **su un database che ha gia' dei ricordi** (e nessuno cambia di visibilita'),
un archivio di backup vecchio rientra e riceve i valori predefiniti, uno nuovo torna com'e' (date comprese), e il grafo del
Cervello continua a non mostrare mai il testo di un ricordo.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config

from shinra import percorsi
from shinra.infra.db import depositi, importazione, motore
from shinra.services import salvataggio

PRECEDENTE = "f19c4d7a3b82"
ULTIMA = "a52e7d9c1f40"


def _alembic() -> Config:
    cfg = Config(str(percorsi.RADICE / "alembic.ini"))
    cfg.set_main_option("script_location", str(percorsi.MIGRAZIONI))
    cfg.attributes["configure_logger"] = False
    return cfg


def _colonne(percorso, tabella="knowledge") -> list[str]:
    conn = sqlite3.connect(percorso)
    try:
        return [r[1] for r in conn.execute(f'PRAGMA table_info("{tabella}")')]
    finally:
        conn.close()


NUOVE = ["proprietario", "origine", "importanza", "ultimo_uso", "usi", "stato", "aggiornato_il", "luogo_id"]


def test_la_migrazione_sale_su_un_database_che_ha_gia_dei_ricordi(tmp_path):
    percorso = tmp_path / "vecchio.db"
    motore.reimposta(percorso)
    command.upgrade(_alembic(), PRECEDENTE)
    assert not set(NUOVE) & set(
        _colonne(percorso)
    ), "il punto di partenza doveva essere prima della migrazione"

    conn = sqlite3.connect(percorso)
    conn.executemany(
        "INSERT INTO knowledge (id, text, category, enabled, creato_il) VALUES (?, ?, ?, ?, ?)",
        [
            ("k_attivo", "Il wifi e' sul router", "casa", 1, "2026-09-01 10:00:00.000000"),
            ("k_spento", "Un ricordo disattivato", "casa", 0, "2026-09-02 11:30:00.000000"),
        ],
    )
    conn.commit()
    conn.close()

    command.upgrade(_alembic(), ULTIMA)

    assert set(NUOVE) <= set(_colonne(percorso))
    attivo = depositi.fatti.per_id("k_attivo")
    spento = depositi.fatti.per_id("k_spento")
    for ricordo in (attivo, spento):
        assert ricordo["proprietario"] == "", "un ricordo esistente ha cambiato di visibilita'"
        assert (ricordo["origine"], ricordo["importanza"], ricordo["usi"]) == ("manuale", 3, 0)
        assert ricordo["ultimo_uso"] is None and ricordo["luogo_id"] == ""
    assert attivo["stato"] == "attivo" and attivo["enabled"] is True
    assert (
        spento["stato"] == "archiviato" and spento["enabled"] is False
    ), "un ricordo spento deve risultare archiviato"
    assert attivo["aggiornato_il"] == datetime(
        2026, 9, 1, 10, 0, 0
    ), "aggiornato_il deve partire da creato_il"


def test_la_migrazione_scende_e_i_ricordi_restano(tmp_path):
    percorso = tmp_path / "giu.db"
    motore.reimposta(percorso)
    command.upgrade(_alembic(), ULTIMA)
    depositi.fatti.aggiungi(
        {"id": "k_1", "text": "Il gatto si chiama Milo", "category": "famiglia", "enabled": True}
    )

    command.downgrade(_alembic(), PRECEDENTE)

    assert not set(NUOVE) & set(_colonne(percorso)), "le colonne sono rimaste"
    conn = sqlite3.connect(percorso)
    try:
        assert conn.execute("SELECT text FROM knowledge WHERE id='k_1'").fetchone() == (
            "Il gatto si chiama Milo",
        )
    finally:
        conn.close()


def test_un_archivio_di_backup_vecchio_rientra_con_i_valori_predefiniti(tmp_path):
    importazione.crea_vuoto(tmp_path / "nuovo.db")
    vecchio = {
        "shinra": {"schema": 1, "creato_il": "2026-09-01T00:00:00+00:00", "versione": "0.6.0"},
        "configurazione": {},
        "tabelle": {
            "knowledge": [
                {
                    "id": "k_v",
                    "text": "Un ricordo di una versione vecchia",
                    "category": "casa",
                    "enabled": True,
                }
            ]
        },
    }
    salvataggio.ripristina(vecchio)

    ricordo = depositi.fatti.per_id("k_v")
    assert ricordo["text"] == "Un ricordo di una versione vecchia"
    assert (ricordo["proprietario"], ricordo["origine"], ricordo["importanza"], ricordo["stato"]) == (
        "",
        "manuale",
        3,
        "attivo",
    )


def test_un_ricordo_con_la_sua_storia_torna_com_e_dal_backup(tmp_path):
    importazione.crea_vuoto(tmp_path / "giro.db")
    quando = datetime(2026, 10, 14, 9, 30, 0)
    depositi.fatti.aggiungi(
        {
            "id": "k_s",
            "text": "Il codice del cancello",
            "category": "casa",
            "enabled": True,
            "proprietario": "alessio",
            "origine": "intervista",
            "importanza": 5,
            "usi": 7,
            "ultimo_uso": quando,
            "stato": "attivo",
        }
    )

    archivio = json.loads(json.dumps(salvataggio.esporta(), default=str))
    assert archivio["tabelle"]["knowledge"][0]["importanza"] == 5
    depositi.fatti.sostituisci_tutto([])
    assert depositi.fatti.per_id("k_s") is None
    salvataggio.ripristina(archivio)

    tornato = depositi.fatti.per_id("k_s")
    assert (tornato["proprietario"], tornato["origine"], tornato["importanza"], tornato["usi"]) == (
        "alessio",
        "intervista",
        5,
        7,
    )
    assert tornato["ultimo_uso"] == quando, "la data e' tornata come testo o e' cambiata"


def test_un_ricordo_scritto_come_prima_nasce_della_casa(tmp_path):
    importazione.crea_vuoto(tmp_path / "casa.db")
    from shinra.infra.data_store import data_store

    ricordo = data_store.add_knowledge_item("La caldaia e' in cantina", "casa")
    assert (ricordo["proprietario"], ricordo["stato"], ricordo["importanza"]) == ("", "attivo", 3)


def test_il_grafo_del_cervello_non_mostra_il_testo_di_un_ricordo():
    """Regola della #188, che il nuovo schema non deve incrinare: nel grafo vanno identificativi, mai testo."""
    from shinra.domain import eventi_agente as ev

    nodi = ev.nodi_dei_fatti([{"id": "k_1", "testo": "Il codice del cancello e' 4471", "categoria": "casa"}])
    assert nodi and "4471" not in json.dumps(nodi, default=str)


def test_la_data_in_testo_si_legge_anche_con_la_zeta():
    from shinra.infra.db.base import DataOra

    assert DataOra().process_bind_param("2026-10-14T09:30:00Z", None) == datetime(
        2026, 10, 14, 9, 30, tzinfo=timezone.utc
    )
    assert DataOra().process_bind_param("", None) is None
    assert DataOra().process_bind_param(None, None) is None
