"""Motore di regole (issue #27).

Trigger, condizioni e azioni in JSON e non in colonne: le forme che possono
assumere cambiano a ogni tipo di trigger nuovo, e una tabella che cambia forma
a ogni tipo nuovo e' una migrazione a ogni tipo nuovo.

Revision ID: 9f4b2c8e5d31
Revises: 5d9a3e6c14b8
Create Date: 2026-09-09 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f4b2c8e5d31"
down_revision: Union[str, Sequence[str], None] = "5d9a3e6c14b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella."""
    op.create_table(
        "regole",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("nome", sa.String(length=160), nullable=False),
        sa.Column("attiva", sa.Boolean(), nullable=False),
        sa.Column("trigger", sa.JSON(), nullable=False),
        sa.Column("condizioni", sa.JSON(), nullable=False),
        sa.Column("azioni", sa.JSON(), nullable=False),
        sa.Column("creata_il", sa.DateTime(), nullable=False),
        sa.Column("autore", sa.String(length=64), nullable=True),
        sa.Column("ultimo_scatto", sa.DateTime(), nullable=True),
        sa.Column("ultimo_esito", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("regole", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_regole_attiva"), ["attiva"], unique=False)


def downgrade() -> None:
    """La rimuove: la casa torna a rispondere solo quando le si parla."""
    with op.batch_alter_table("regole", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_regole_attiva"))

    op.drop_table("regole")
