"""Voci sentite dagli Echo, e a chi corrispondono (issue #48).

Nasce vuota e si riempie da sola: ogni richiesta vocale che porta un
`personId` lascia una riga, non associata. Associarla e' un gesto
esplicito dalle impostazioni — nessuna euristica indovina di chi e' una
voce, perche' indovinare male qui significa dare a uno i permessi di un
altro.

Revision ID: a2f7c4d90e15
Revises: c7e1a95f2b64
Create Date: 2026-09-09 18:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2f7c4d90e15"
down_revision: Union[str, Sequence[str], None] = "c7e1a95f2b64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voci_sentite",
        sa.Column("person_id", sa.String(length=200), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("nota", sa.String(length=200), nullable=False),
        sa.Column("prima_volta", sa.DateTime(), nullable=False),
        sa.Column("ultima_volta", sa.DateTime(), nullable=False),
        sa.Column("quante_volte", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("person_id"),
    )
    with op.batch_alter_table("voci_sentite", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_voci_sentite_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """La rimuove. Il canale vocale torna senza identita': e con essa torna
    il buco che questa migrazione serve a chiudere."""
    with op.batch_alter_table("voci_sentite", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_voci_sentite_user_id"))

    op.drop_table("voci_sentite")
