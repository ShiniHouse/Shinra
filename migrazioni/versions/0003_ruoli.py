"""Ruoli e permessi (issue #19).

La tabella nasce vuota e viene riempita all'avvio con i cinque ruoli
predefiniti, i cui identificativi coincidono con i valori che il campo `role`
ha gia' nei profili: cosi' l'aggiornamento e' una corrispondenza, non una
riscrittura, e nessuno si ritrova senza ruolo.

Revision ID: 16be1a50615c
Revises: 27755ef706bb
Create Date: 2026-09-07 13:05:46.283735

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16be1a50615c"
down_revision: Union[str, Sequence[str], None] = "27755ef706bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella dei ruoli."""
    op.create_table(
        "ruoli",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("descrizione", sa.Text(), nullable=True),
        sa.Column("permessi", sa.JSON(), nullable=False),
        sa.Column("predefinito", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """La rimuove. I profili conservano il nome del ruolo nel campo `role`."""
    op.drop_table("ruoli")
