"""Configurazione di Alembic.

L'indirizzo del database non e' scritto in alembic.ini: viene da
`shinra.infra.db.motore`, che e' l'unico posto che sa dove vive l'archivio.
Duplicarlo significherebbe, prima o poi, migrare un file e usarne un altro.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

# Alembic si lancia anche da una copia di lavoro dove il pacchetto non e'
# stato installato: senza questo, `import shinra` fallirebbe. In
# un'installazione la riga non fa danno, perche' il percorso c'e' gia'.
SORGENTI = Path(__file__).resolve().parent.parent / "src"
if SORGENTI.is_dir() and str(SORGENTI) not in sys.path:
    sys.path.insert(0, str(SORGENTI))

from shinra.infra.db.modelli import Base  # noqa: E402
from shinra.infra.db.motore import motore  # noqa: E402

config = context.config

# `fileConfig` non aggiunge: **sostituisce**. Riporta il logger radice al
# livello scritto in `alembic.ini` (WARNING) e, per difetto, spegne uno per
# uno tutti i logger che esistevano gia'.
#
# Da riga di comando va benissimo: quel processo fa solo migrazioni. Ma le
# migrazioni girano anche dentro l'applicazione, all'avvio e prima di
# qualunque altra cosa — e da quel momento in poi tutto l'INFO dell'hub
# spariva dal journal. Ogni riga scritta con cura per raccontare cosa sta
# succedendo in casa («Carico il modello di trascrizione», «Ripresi 3
# timer», «Trascrizione completata») e' stata invisibile in produzione da
# quando esistono le migrazioni. Restavano solo gli avvisi, che e' il
# motivo per cui sembrava che il servizio non dicesse niente.
#
# Chi chiama le migrazioni dall'interno mette `configure_logger` a falso:
# il logging se lo e' gia' configurato per conto suo.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    from shinra.infra.db.motore import percorso_archivio

    context.configure(
        url=f"sqlite:///{percorso_archivio()}",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with motore().connect() as connessione:
        context.configure(
            connection=connessione,
            target_metadata=target_metadata,
            # SQLite non sa modificare una colonna esistente: Alembic aggira
            # il limite ricreando la tabella e ricopiandone il contenuto.
            # Senza questo, la prima migrazione che cambia un campo fallisce
            # sul server e lascia lo schema a meta'.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
