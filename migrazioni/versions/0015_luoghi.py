"""I luoghi: la casa principale e le altre abitazioni (issue #342).

Una tabella di luoghi con coordinate vere, prese dalla posizione di un telefono o di un PC. **Nessuna traccia degli
spostamenti**: qui sta solo dove sono i luoghi, non dove sono le persone. Il luogo principale nasce dalla citta' gia'
configurata solo quando una persona lo registra: la migrazione non inventa coordinate.

Revision ID: e4b8c20a71d3
Revises: d8a3f61c2b07
Create Date: 2026-10-14 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b8c20a71d3"
down_revision: Union[str, Sequence[str], None] = "d8a3f61c2b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "luoghi",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=16), nullable=False, server_default="abitazione"),
        sa.Column("principale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latitudine", sa.Float(), nullable=False),
        sa.Column("longitudine", sa.Float(), nullable=False),
        sa.Column("raggio_m", sa.Integer(), nullable=False, server_default="150"),
        sa.Column("citta", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("origine", sa.String(length=16), nullable=False, server_default="browser"),
        sa.Column("precisione_m", sa.Integer(), nullable=True),
        sa.Column("creato_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Toglie la tabella: con lei se ne vanno le coordinate."""
    op.drop_table("luoghi")
