"""Configurazione di Alembic.

L'indirizzo del database non e' scritto in alembic.ini: viene da
`core/archivio/motore.py`, che e' l'unico posto che sa dove vive l'archivio.
Duplicarlo significherebbe, prima o poi, migrare un file e usarne un altro.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

RADICE = Path(__file__).resolve().parent.parent
if str(RADICE) not in sys.path:
    sys.path.insert(0, str(RADICE))

from core.archivio.modelli import Base  # noqa: E402
from core.archivio.motore import motore  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    from core.archivio.motore import percorso_archivio

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
