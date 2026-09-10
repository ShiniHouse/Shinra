"""Credenziali WebAuthn (issue #48).

Qui non finisce niente di segreto: la chiave privata resta
nell'autenticatore e non ne esce mai. Quella salvata e' la pubblica, con cui
si verificano le firme e con cui, da sola, non si apre niente.

Revision ID: b6e3d18a4c72
Revises: a2f7c4d90e15
Create Date: 2026-09-10 10:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6e3d18a4c72"
down_revision: Union[str, Sequence[str], None] = "a2f7c4d90e15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "passkey",
        sa.Column("id", sa.String(length=500), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("chiave_pubblica", sa.Text(), nullable=False),
        sa.Column("contatore", sa.Integer(), nullable=False),
        sa.Column("rp_id", sa.String(length=255), nullable=False),
        sa.Column("tipo_dispositivo", sa.String(length=32), nullable=False),
        sa.Column("creata_il", sa.DateTime(), nullable=False),
        sa.Column("ultimo_uso", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("passkey", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_passkey_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    """Toglie le credenziali. Il PIN resta e continua a funzionare: e' per
    questo che non e' mai stato sostituito, solo affiancato."""
    with op.batch_alter_table("passkey", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_passkey_user_id"))

    op.drop_table("passkey")
