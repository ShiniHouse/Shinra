"""Sottoscrizioni push e preferenze di notifica (issue #29).

Le preferenze stanno una per riga invece di una colonna per categoria: le
categorie cambiano a ogni funzione nuova, e una tabella che cambia forma a
ogni funzione nuova e' una migrazione a ogni funzione nuova.

Revision ID: 5d9a3e6c14b8
Revises: 8c2e4b1a7f30
Create Date: 2026-09-09 14:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d9a3e6c14b8"
down_revision: Union[str, Sequence[str], None] = "8c2e4b1a7f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea le due tabelle."""
    op.create_table(
        "sottoscrizioni_push",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("p256dh", sa.String(length=200), nullable=False),
        sa.Column("auth", sa.String(length=100), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("creata_il", sa.DateTime(), nullable=False),
        sa.Column("ultimo_invio", sa.DateTime(), nullable=True),
        sa.Column("fallimenti", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    with op.batch_alter_table("sottoscrizioni_push", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sottoscrizioni_push_user_id"), ["user_id"], unique=False)

    op.create_table(
        "preferenze_notifiche",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("chiave", sa.String(length=64), nullable=False),
        sa.Column("valore", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("preferenze_notifiche", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_preferenze_notifiche_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """Le rimuove: i telefoni tornano a non ricevere niente."""
    with op.batch_alter_table("preferenze_notifiche", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_preferenze_notifiche_user_id"))
    op.drop_table("preferenze_notifiche")

    with op.batch_alter_table("sottoscrizioni_push", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sottoscrizioni_push_user_id"))
    op.drop_table("sottoscrizioni_push")
