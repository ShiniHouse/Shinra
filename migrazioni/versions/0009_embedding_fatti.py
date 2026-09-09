"""Embedding dei fatti (issue #32).

L'impronta del testo e il nome del modello stanno accanto al vettore: un
vettore vecchio non da' errore, da' risposte sbagliate, e confrontare vettori
di due modelli diversi produce numeri che sembrano punteggi e non lo sono.

Revision ID: c7e1a95f2b64
Revises: 9f4b2c8e5d31
Create Date: 2026-09-09 17:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e1a95f2b64"
down_revision: Union[str, Sequence[str], None] = "9f4b2c8e5d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea la tabella. Nasce vuota: i vettori si calcolano al primo avvio."""
    op.create_table(
        "embedding_fatti",
        sa.Column("fatto_id", sa.String(length=64), nullable=False),
        sa.Column("vettore", sa.JSON(), nullable=False),
        sa.Column("modello", sa.String(length=120), nullable=False),
        sa.Column("impronta", sa.String(length=64), nullable=False),
        sa.Column("calcolato_il", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("fatto_id"),
    )
    with op.batch_alter_table("embedding_fatti", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_embedding_fatti_impronta"), ["impronta"], unique=False)


def downgrade() -> None:
    """La rimuove: il recupero torna solo testuale, i fatti restano."""
    with op.batch_alter_table("embedding_fatti", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_embedding_fatti_impronta"))

    op.drop_table("embedding_fatti")
